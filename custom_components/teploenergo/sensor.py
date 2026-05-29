from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, METER_TYPE_GVS, UNIT_GCAL
from .coordinator import TeploenergoCoordinator, TeploenergoData
from .entity import TeploenergoEntity
from .teploenergo_api import MeterInfo

_LOGGER = logging.getLogger(__name__)

CURRENCY_RUB = "RUB"


# ── Account-level sensor descriptors ─────────────────────────────────────────

@dataclass(frozen=True, kw_only=True)
class TeploenergoSensorDescription(SensorEntityDescription):
    value_fn: ... = None  # Callable[[TeploenergoData], StateType]


ACCOUNT_SENSORS: tuple[TeploenergoSensorDescription, ...] = (
    TeploenergoSensorDescription(
        key="debt",
        translation_key="debt",
        native_unit_of_measurement=CURRENCY_RUB,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.debt,
    ),
    TeploenergoSensorDescription(
        key="sum_itog",
        translation_key="sum_itog",
        native_unit_of_measurement=CURRENCY_RUB,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.latest_accrual.sum_itog if d.latest_accrual else None,
    ),
    TeploenergoSensorDescription(
        key="sum_pay",
        translation_key="sum_pay",
        native_unit_of_measurement=CURRENCY_RUB,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.latest_accrual.sum_pay if d.latest_accrual else None,
    ),
    TeploenergoSensorDescription(
        key="balance",
        translation_key="balance",
        native_unit_of_measurement=CURRENCY_RUB,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.latest_accrual.balance if d.latest_accrual else None,
    ),
    TeploenergoSensorDescription(
        key="last_period",
        translation_key="last_period",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            datetime.fromtimestamp(d.latest_accrual.period_time, tz=UTC)
            if d.latest_accrual else None
        ),
    ),
)


# ── Setup ─────────────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TeploenergoCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        TeploenergoAccountSensor(coordinator, desc) for desc in ACCOUNT_SENSORS
    ]
    for meter in coordinator.data.meters:
        entities.append(TeploenergoMeterReadingSensor(coordinator, meter))
        entities.append(TeploenergoMeterVerifyDateSensor(coordinator, meter))

    async_add_entities(entities)


# ── Account sensor ────────────────────────────────────────────────────────────

class TeploenergoAccountSensor(TeploenergoEntity, SensorEntity):
    entity_description: TeploenergoSensorDescription

    def __init__(
        self,
        coordinator: TeploenergoCoordinator,
        description: TeploenergoSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_{description.key}"

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)


# ── Meter sensors ─────────────────────────────────────────────────────────────

class TeploenergoMeterReadingSensor(TeploenergoEntity, SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: TeploenergoCoordinator, meter: MeterInfo) -> None:
        super().__init__(coordinator)
        self._meter_id = meter.meter_id
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_meter_{meter.meter_id}_reading"
        self._attr_name = f"{meter.type_label} {meter.number}"

        if meter.meter_type == METER_TYPE_GVS:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = "m³"
        else:
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = UNIT_GCAL

    def _get_meter(self) -> MeterInfo | None:
        return next(
            (m for m in self.coordinator.data.meters if m.meter_id == self._meter_id),
            None,
        )

    @property
    def native_value(self) -> float | None:
        meter = self._get_meter()
        return meter.value1 if meter else None

    @property
    def extra_state_attributes(self) -> dict:
        meter = self._get_meter()
        if not meter:
            return {}
        return {"measure_date": meter.measure_date}


class TeploenergoMeterVerifyDateSensor(TeploenergoEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TeploenergoCoordinator, meter: MeterInfo) -> None:
        super().__init__(coordinator)
        self._meter_id = meter.meter_id
        self._attr_unique_id = f"{DOMAIN}_{coordinator.ls}_meter_{meter.meter_id}_verify"
        self._attr_name = f"{meter.type_label} {meter.number} поверка"

    @property
    def native_value(self) -> datetime | None:
        meter = next(
            (m for m in self.coordinator.data.meters if m.meter_id == self._meter_id),
            None,
        )
        if not meter or not meter.verify_datetime:
            return None
        return datetime.fromtimestamp(meter.verify_datetime, tz=UTC)
