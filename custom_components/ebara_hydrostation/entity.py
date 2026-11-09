"""Base entity for Ebara Hydrostation."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HYDRO_MAC, CONF_HYDRO_NAME, DOMAIN, MANUFACTURER, MODEL
from .coordinator import EbaraCoordinator


class EbaraEntity(CoordinatorEntity[EbaraCoordinator]):
    """Entity backed by one entity of the ESP32 gateway.

    Push-based: the coordinator forwards every state the gateway pushes, so
    there is no polling (CoordinatorEntity sets should_poll = False).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: EbaraCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        data = coordinator.config_entry.data
        mac = data[CONF_HYDRO_MAC]
        self._attr_unique_id = f"{mac}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=data.get(CONF_HYDRO_NAME, "Hydrostation"),
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Available while the API connection to the gateway is up.

        Values the gateway cannot read (pump offline) are reported as
        unknown by the individual entities, not as unavailable.
        """
        return self.coordinator.connected
