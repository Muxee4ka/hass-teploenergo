"""Tests for TeploenergoCoordinator."""
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.teploenergo.coordinator import TeploenergoCoordinator
from custom_components.teploenergo.exceptions import (
    TeploenergoAuthError,
    TeploenergoConnectionError,
)

from .conftest import MOCK_ACCRUALS, MOCK_METERS, TEST_LS


def _make_api(
    debt=0.0,
    accruals=None,
    meters=None,
    auth_exc=None,
    conn_exc=None,
):
    api = AsyncMock()
    api.is_authenticated = False
    api.authenticate = AsyncMock(side_effect=auth_exc)
    api.get_debt = AsyncMock(return_value=debt, side_effect=conn_exc)
    api.get_accruals = AsyncMock(return_value=accruals or MOCK_ACCRUALS)
    api.get_meters = AsyncMock(return_value=meters or MOCK_METERS)
    api.get_accounts = AsyncMock(return_value=[])
    return api


async def test_update_data_returns_correct_structure(hass):
    api = _make_api(debt=123.45)
    coordinator = TeploenergoCoordinator(hass, api, TEST_LS)

    await coordinator.async_refresh()

    assert coordinator.data.debt == 123.45
    assert len(coordinator.data.accruals) == 2
    assert len(coordinator.data.meters) == 2


async def test_latest_accrual_is_most_recent_period(hass):
    api = _make_api()
    coordinator = TeploenergoCoordinator(hass, api, TEST_LS)
    await coordinator.async_refresh()

    # MOCK_ACCRUALS[0].period_time=1748743200 > MOCK_ACCRUALS[1].period_time=1743462000
    assert coordinator.data.latest_accrual is not None
    assert coordinator.data.latest_accrual.period_time == 1748743200


async def test_auth_error_raises_config_entry_auth_failed(hass):
    api = _make_api(auth_exc=TeploenergoAuthError("expired"))
    coordinator = TeploenergoCoordinator(hass, api, TEST_LS)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_refresh()


async def test_connection_error_raises_update_failed(hass):
    api = _make_api(conn_exc=TeploenergoConnectionError("timeout"))
    coordinator = TeploenergoCoordinator(hass, api, TEST_LS)

    with pytest.raises(UpdateFailed):
        await coordinator.async_refresh()


async def test_authenticate_called_when_not_authenticated(hass):
    api = _make_api()
    api.is_authenticated = False
    coordinator = TeploenergoCoordinator(hass, api, TEST_LS)

    await coordinator.async_refresh()

    api.authenticate.assert_called_once()
