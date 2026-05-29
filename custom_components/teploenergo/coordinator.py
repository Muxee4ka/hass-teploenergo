from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .exceptions import TeploenergoAuthError, TeploenergoConnectionError
from .teploenergo_api import AccrualRecord, MeterInfo, TeploenergoApi

_LOGGER = logging.getLogger(__name__)


@dataclass
class TeploenergoData:
    debt: float
    accruals: list[AccrualRecord]
    meters: list[MeterInfo]
    latest_accrual: AccrualRecord | None


class TeploenergoCoordinator(DataUpdateCoordinator[TeploenergoData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: TeploenergoApi, ls: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{ls}",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.ls = ls
        self.postal_index: str = ""

    async def _async_update_data(self) -> TeploenergoData:
        try:
            if not self.api.is_authenticated:
                await self.api.authenticate()

            debt, accruals, meters = (
                await self.api.get_debt(self.ls),
                await self.api.get_accruals(self.ls),
                await self.api.get_meters(),
            )

            if not self.postal_index:
                accounts = await self.api.get_accounts()
                for acc in accounts:
                    if acc.ls == self.ls:
                        self.postal_index = acc.postal_index
                        break

            latest = (
                max(accruals, key=lambda a: a.period_time) if accruals else None
            )
            return TeploenergoData(
                debt=debt,
                accruals=accruals,
                meters=meters,
                latest_accrual=latest,
            )

        except TeploenergoAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        except TeploenergoConnectionError as exc:
            raise UpdateFailed(str(exc)) from exc
