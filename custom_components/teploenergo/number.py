from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, METER_TYPE_GVS, UNIT_GCAL
from .coordinator import TeploenergoCoordinator
from .entity import TeploenergoEntity
from .teploenergo_api import MeterInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TeploenergoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TeploenergoMeterInput(coordinator, meter) for meter in coordinator.data.meters
    )


class TeploenergoMeterInput(TeploenergoEntity, RestoreNumber):
    """Pending meter reading — stored locally, sent only via the Send button."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.001

    def __init__(self, coordinator: TeploenergoCoordinator, meter: MeterInfo) -> None:
        super().__init__(coordinator)
        self._meter_id = meter.meter_id
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_meter_{meter.meter_id}_input"
        self._attr_name = f"{meter.type_label} {meter.number} передача"
        self._attr_native_value: float | None = meter.value1

        if meter.meter_type == METER_TYPE_GVS:
            self._attr_device_class = NumberDeviceClass.WATER
            self._attr_native_unit_of_measurement = "m³"
        else:
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = UNIT_GCAL

    def _current_meter(self) -> MeterInfo | None:
        return next(
            (m for m in self.coordinator.data.meters if m.meter_id == self._meter_id),
            None,
        )

    @property
    def native_min_value(self) -> float:
        meter = self._current_meter()
        return meter.value1 if meter else 0.0

    @property
    def native_max_value(self) -> float:
        meter = self._current_meter()
        return (meter.value1 + 99999) if meter else 99999.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = float(last.native_value)
        self.coordinator.meter_inputs[self._meter_id] = self

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.meter_inputs.pop(self._meter_id, None)

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
