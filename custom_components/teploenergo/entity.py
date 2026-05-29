from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TeploenergoCoordinator


class TeploenergoEntity(CoordinatorEntity[TeploenergoCoordinator]):
    """Base entity: ties an entity to a specific LS account device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TeploenergoCoordinator) -> None:
        super().__init__(coordinator)
        ls = coordinator.ls
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ls)},
            name=f"Теплоэнерго ЛС {ls}",
            manufacturer=MANUFACTURER,
            configuration_url="https://lk.teploenergo-nn.ru",
        )
