"""Tests for TeploenergoApi — all aiohttp is mocked, no real sockets."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.teploenergo.exceptions import (
    TeploenergoAuthError,
    TeploenergoConnectionError,
)
from custom_components.teploenergo.teploenergo_api import TeploenergoApi


def _make_resp(data: dict, status: int = 200):
    """Async-context-manager mock for aiohttp response."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.read = AsyncMock(return_value=b"%PDF mock")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_session(post_resp=None, get_resp=None):
    """Mock aiohttp.ClientSession (no real socket created)."""
    session = MagicMock()
    if post_resp is not None:
        session.post = MagicMock(return_value=post_resp)
    if get_resp is not None:
        session.get = MagicMock(return_value=get_resp)
    session.closed = False
    session.close = AsyncMock()
    return session


AUTH_OK = {"Status": True, "ErrorCode": None, "Text": "", "Result": "test_sessid"}
AUTH_FAIL = {"Status": False, "ErrorCode": None, "Text": "WRONG_PASSWORD", "Result": None}
SESSION_EXPIRED = {"Status": False, "ErrorCode": None, "Text": "SESSION_EXPIRED", "Result": None}


# ── authenticate ──────────────────────────────────────────────────────────────


async def test_authenticate_extracts_sessid_from_result():
    session = _make_session(post_resp=_make_resp(AUTH_OK))
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("user@example.com", "secret")
        await api.authenticate()

    assert api._sessid == "test_sessid"
    assert api.is_authenticated


async def test_authenticate_raises_on_wrong_password():
    session = _make_session(post_resp=_make_resp(AUTH_FAIL))
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("user@example.com", "wrong")
        with pytest.raises(TeploenergoAuthError):
            await api.authenticate()


# ── SESSION_EXPIRED auto-retry ────────────────────────────────────────────────


async def test_get_retries_on_session_expired():
    bills_raw = [
        {
            "number": "123",
            "UF_LS": "123",
            "ID": "1",
            "address": "",
            "owner": "",
            "debt": "0",
            "postalIndex": "000",
        }
    ]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return _make_resp(SESSION_EXPIRED)
        return _make_resp({"Status": True, "Text": "", "Result": bills_raw})

    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    session.get = MagicMock(side_effect=fake_get)
    session.post = MagicMock(return_value=_make_resp(AUTH_OK))

    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        api._sessid = "old"
        result = await api._get("/bills/list/")

    assert api._sessid == "test_sessid"  # re-authed
    assert len(calls) == 2  # first expired, second ok
    assert result == bills_raw


# ── get_accounts ──────────────────────────────────────────────────────────────


async def test_get_accounts_parses_all_fields():
    raw_item = {
        "ID": "115916",
        "UF_LS": "7024690127",
        "number": "7024690127",
        "address": "Нижний Новгород",
        "owner": "%D0%A2%D0%B5%D1%81%D1%82",
        "debt": "12.50",
        "postalIndex": "603057",
    }
    session = _make_session(get_resp=_make_resp({"Status": True, "Text": "", "Result": [raw_item]}))
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        api._sessid = "sessid"
        accounts = await api.get_accounts()

    assert len(accounts) == 1
    acc = accounts[0]
    assert acc.ls == "7024690127"
    assert acc.account_id == "115916"
    assert acc.postal_index == "603057"
    assert acc.debt == 12.5
    assert acc.owner == "Тест"


# ── get_meters ────────────────────────────────────────────────────────────────


async def test_get_meters_returns_otop_and_gvs():
    raw = {
        "otop": [
            {
                "id": "u1",
                "meterId": 1001,
                "number": "OT-001",
                "type": "ИТП Отопление",
                "value1": 23.875,
                "value2": None,
                "measureDate": "27.05.2026",
                "verifyDate": "29.01.2032",
                "aType": "Отопление",
                "verifyDateTime": 1958936400,
                "measureDateTime": 0,
            }
        ],
        "gvs": [
            {
                "id": "u2",
                "meterId": 2001,
                "number": "GV-001",
                "type": "ИПУ ГВС",
                "value1": 17.1,
                "value2": None,
                "measureDate": "27.05.2026",
                "verifyDate": "20.01.2032",
                "aType": "ГВС",
                "verifyDateTime": 1958158800,
                "measureDateTime": 0,
            }
        ],
    }
    session = _make_session(get_resp=_make_resp({"Status": True, "Text": "", "Result": raw}))
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        api._sessid = "sessid"
        meters = await api.get_meters()

    assert len(meters) == 2
    assert meters[0].meter_type == "otop"
    assert meters[0].value1 == 23.875
    assert meters[1].meter_type == "gvs"
    assert meters[1].value1 == 17.1


# ── send_meter_reading ────────────────────────────────────────────────────────


async def test_send_meter_reading_posts_correct_body():
    session = _make_session(post_resp=_make_resp({"Status": True, "Text": "", "Result": None}))
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        api._sessid = "my_sessid"
        await api.send_meter_reading(ls="7024690127", meter_id=70180714, value=18.5)

    _, kwargs = session.post.call_args
    body = kwargs["data"]
    assert body["meterId"] == "70180714"
    assert body["value"] == "18.5"
    assert body["ls"] == "7024690127"
    assert body["sessid"] == "my_sessid"


async def test_send_meter_reading_raises_on_api_error():
    session = _make_session(
        post_resp=_make_resp({"Status": False, "Text": "VALIDATION_ERROR", "Result": None})
    )
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        api._sessid = "sessid"
        with pytest.raises(TeploenergoConnectionError, match="VALIDATION_ERROR"):
            await api.send_meter_reading("123", 999, 1.0)


# ── download_bill ─────────────────────────────────────────────────────────────


async def test_download_bill_returns_bytes():
    resp = MagicMock()
    resp.status = 200
    resp.read = AsyncMock(return_value=b"%PDF-1.4 content")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)

    session = _make_session(get_resp=resp)
    with patch("aiohttp.TCPConnector"), patch("aiohttp.ClientSession", return_value=session):
        api = TeploenergoApi("u@e.com", "p")
        data = await api.download_bill("603057", "7024690127")

    assert data == b"%PDF-1.4 content"
