"""Async API client for mobilelk.teploenergo-nn.ru."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import unquote_plus

import aiohttp

from .const import BASE_URL, METER_TYPE_GVS, METER_TYPE_OTOP
from .exceptions import TeploenergoAuthError, TeploenergoConnectionError

_LOGGER = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "okhttp/4.9.0",
    "Accept-Encoding": "gzip",
}


@dataclass
class AccountInfo:
    ls: str
    account_id: str
    address: str
    owner: str
    debt: float
    postal_index: str


@dataclass
class AccrualRecord:
    period: str
    period_time: int
    balance: float
    sum_tariff: float
    sum_recalculation: float
    sum_fine: float
    sum_itog: float
    sum_pay: float


@dataclass
class MeterInfo:
    uid: str
    meter_id: int
    number: str
    meter_type: str        # "otop" or "gvs"
    type_label: str        # human-readable e.g. "ИТП Отопление"
    a_type: str            # "Отопление" / "ГВС"
    value1: float
    value2: float | None
    measure_date: str
    verify_date: str
    verify_datetime: int


class TeploenergoApi:
    def __init__(self, login: str, password: str) -> None:
        self._login = login
        self._password = password
        self._sessid: str = ""
        self._session: aiohttp.ClientSession | None = None
        self._auth_lock = asyncio.Lock()

    # ── Session management ────────────────────────────────────────────────────

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                headers=_HEADERS,
                cookie_jar=aiohttp.CookieJar(),
                connector=connector,
            )
        return self._session

    async def authenticate(self) -> None:
        async with self._auth_lock:
            session = self._ensure_session()
            try:
                async with session.post(
                    f"{BASE_URL}/users/auth/",
                    data={"LOGIN": self._login, "PASSWORD": self._password},
                ) as resp:
                    data = await resp.json(content_type=None)
            except aiohttp.ClientError as exc:
                raise TeploenergoConnectionError(str(exc)) from exc

            if not data.get("Status"):
                raise TeploenergoAuthError(data.get("Text") or "auth_failed")

            self._sessid = data["Result"]
            _LOGGER.debug("Authenticated, sessid=%s…", self._sessid[:8])

    @property
    def is_authenticated(self) -> bool:
        return bool(self._sessid)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Low-level request ─────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None, *, _retried: bool = False):
        session = self._ensure_session()
        full_params = {"sessid": self._sessid, **(params or {})}
        try:
            async with session.get(f"{BASE_URL}{path}", params=full_params) as resp:
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise TeploenergoConnectionError(str(exc)) from exc

        if not data.get("Status"):
            text = data.get("Text", "")
            if text == "SESSION_EXPIRED" and not _retried:
                _LOGGER.debug("Session expired, re-authenticating")
                self._sessid = ""
                await self.authenticate()
                return await self._get(path, params, _retried=True)
            if text == "SESSION_EXPIRED":
                raise TeploenergoAuthError("Session expired after re-auth")
            raise TeploenergoConnectionError(f"{path}: {text}")

        return data["Result"]

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_accounts(self) -> list[AccountInfo]:
        raw: list[dict] = await self._get("/bills/list/")
        result = []
        for item in raw:
            result.append(AccountInfo(
                ls=str(item.get("number") or item.get("UF_LS", "")),
                account_id=str(item.get("ID", "")),
                address=item.get("address", ""),
                owner=unquote_plus(item.get("owner", "")),
                debt=float(item.get("debt") or 0),
                postal_index=str(item.get("postalIndex", "")),
            ))
        return result

    async def get_debt(self, ls: str) -> float:
        raw = await self._get("/bills/getDebt/", {"ls": ls})
        return float(raw) if raw else 0.0

    async def get_accruals(self, ls: str) -> list[AccrualRecord]:
        raw: list[dict] = await self._get("/accruals/listSixMonth/", {"ls": ls})
        return [
            AccrualRecord(
                period=item.get("period", ""),
                period_time=item.get("periodTime", 0),
                balance=float(item.get("balance") or 0),
                sum_tariff=float(item.get("sumTariff") or 0),
                sum_recalculation=float(item.get("sumRecalculation") or 0),
                sum_fine=float(item.get("sumFine") or 0),
                sum_itog=float(item.get("sumItog") or 0),
                sum_pay=float(item.get("sumPay") or 0),
            )
            for item in raw
        ]

    async def send_meter_reading(self, ls: str, meter_id: int, value: float) -> None:
        """Submit a meter reading. sessid goes in POST body per Bitrix convention."""
        session = self._ensure_session()
        body = {
            "sessid": self._sessid,
            "meterId": str(meter_id),
            "value": str(value),
            "ls": ls,
        }
        try:
            async with session.post(
                f"{BASE_URL}/apartmentPu/sendPuValue/",
                data=body,
            ) as resp:
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise TeploenergoConnectionError(str(exc)) from exc

        if not data.get("Status"):
            text = data.get("Text", "")
            if text == "SESSION_EXPIRED":
                await self.authenticate()
                await self.send_meter_reading(ls, meter_id, value)
                return
            raise TeploenergoConnectionError(f"sendPuValue: {text}")

        _LOGGER.debug("Reading submitted: meterId=%s value=%s", meter_id, value)

    async def download_bill(self, postal_index: str, ls: str) -> bytes:
        """Download the current bill PDF. No auth required — static file."""
        url = f"{BASE_URL}/upload/complete/{postal_index}/{ls}.pdf"
        try:
            async with self._ensure_session().get(url) as resp:
                if resp.status != 200:
                    raise TeploenergoConnectionError(
                        f"Bill download failed: HTTP {resp.status}"
                    )
                return await resp.read()
        except aiohttp.ClientError as exc:
            raise TeploenergoConnectionError(str(exc)) from exc

    async def get_meters(self) -> list[MeterInfo]:
        raw: dict = await self._get("/apartmentPu/list/")
        meters: list[MeterInfo] = []
        for meter_type in (METER_TYPE_OTOP, METER_TYPE_GVS):
            for item in raw.get(meter_type, []):
                meters.append(MeterInfo(
                    uid=item.get("id", ""),
                    meter_id=int(item.get("meterId", 0)),
                    number=item.get("number", ""),
                    meter_type=meter_type,
                    type_label=item.get("type", ""),
                    a_type=item.get("aType", ""),
                    value1=float(item.get("value1") or 0),
                    value2=float(item["value2"]) if item.get("value2") is not None else None,
                    measure_date=item.get("measureDate", ""),
                    verify_date=item.get("verifyDate", ""),
                    verify_datetime=int(item.get("verifyDateTime") or 0),
                ))
        return meters
