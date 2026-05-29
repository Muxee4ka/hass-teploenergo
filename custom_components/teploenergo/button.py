from __future__ import annotations

import logging
import pathlib

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeploenergoCoordinator
from .entity import TeploenergoEntity
from .exceptions import TeploenergoConnectionError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TeploenergoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TeploenergoSendReadingsButton(coordinator),
            TeploenergoDownloadBillButton(coordinator),
        ]
    )


class TeploenergoSendReadingsButton(TeploenergoEntity, ButtonEntity):
    _attr_icon = "mdi:arrow-top-right"

    def __init__(self, coordinator: TeploenergoCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_send_readings"
        self._attr_name = "Передача показаний"

    async def async_press(self) -> None:
        coordinator = self.coordinator
        sent = 0
        for meter_id, entity in coordinator.meter_inputs.items():
            if entity.native_value is None:
                continue
            try:
                await coordinator.api.send_meter_reading(
                    ls=coordinator.ls,
                    meter_id=meter_id,
                    value=entity.native_value,
                )
                sent += 1
            except TeploenergoConnectionError as exc:
                _LOGGER.error("Failed to send reading for meter %s: %s", meter_id, exc)

        if sent:
            await coordinator.async_request_refresh()


class TeploenergoDownloadBillButton(TeploenergoEntity, ButtonEntity):
    _attr_translation_key = "download_bill"
    _attr_icon = "mdi:file-pdf-box"

    def __init__(self, coordinator: TeploenergoCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_download_bill"

    async def async_press(self) -> None:
        coordinator = self.coordinator
        if not coordinator.postal_index:
            _LOGGER.error("postal_index not yet known, cannot download bill")
            return

        try:
            pdf_bytes = await coordinator.api.download_bill(
                coordinator.postal_index, coordinator.ls
            )
        except TeploenergoConnectionError as exc:
            _LOGGER.error("Bill download failed: %s", exc)
            return

        save_dir = pathlib.Path(self.hass.config.path("www", "teploenergo"))
        filename = f"{coordinator.ls}.pdf"
        save_path = save_dir / filename

        def _write() -> None:
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(pdf_bytes)

        await self.hass.async_add_executor_job(_write)

        local_url = f"/local/teploenergo/{filename}"
        _LOGGER.info("Bill saved to %s (%d bytes)", save_path, len(pdf_bytes))

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Счёт Теплоэнерго",
                "message": (
                    f"Счёт для ЛС {coordinator.ls} сохранён.\n\n[Открыть PDF]({local_url})"
                ),
                "notification_id": f"teploenergo_bill_{coordinator.ls}",
            },
        )
