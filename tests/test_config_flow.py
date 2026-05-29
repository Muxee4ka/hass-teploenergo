"""Tests for config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.teploenergo.const import CONF_ACCOUNT_ID, CONF_LS, DOMAIN
from custom_components.teploenergo.exceptions import (
    TeploenergoAuthError,
    TeploenergoConnectionError,
)

from .conftest import MOCK_ACCOUNT, TEST_LOGIN, TEST_PASSWORD, TEST_LS

USER_INPUT = {CONF_USERNAME: TEST_LOGIN, CONF_PASSWORD: TEST_PASSWORD}


def _patch_api(accounts=None, auth_exc=None, conn_exc=None):
    """Context manager that patches TeploenergoApi in the config_flow module."""
    mock_instance = AsyncMock()
    mock_instance.authenticate = AsyncMock(side_effect=auth_exc)
    mock_instance.get_accounts = AsyncMock(return_value=accounts or [MOCK_ACCOUNT])
    mock_instance.close = AsyncMock()

    if conn_exc:
        mock_instance.authenticate = AsyncMock(side_effect=conn_exc)

    return patch(
        "custom_components.teploenergo.config_flow.TeploenergoApi",
        return_value=mock_instance,
    )


async def test_user_happy_path_creates_entry(hass):
    with _patch_api():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ЛС {TEST_LS}"
    assert result["data"][CONF_LS] == TEST_LS
    assert result["data"][CONF_USERNAME] == TEST_LOGIN


async def test_user_invalid_auth(hass):
    with _patch_api(auth_exc=TeploenergoAuthError("bad password")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_cannot_connect(hass):
    with _patch_api(conn_exc=TeploenergoConnectionError("timeout")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_no_accounts(hass):
    with _patch_api(accounts=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_accounts"


async def test_already_configured_aborts(hass):
    with _patch_api():
        # First setup
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    with _patch_api():
        # Second attempt with same account
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)

    with _patch_api():
        result = await mock_config_entry.start_reauth_flow(hass)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "newpassword"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "newpassword"


async def test_reauth_invalid_auth_keeps_form(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)

    with _patch_api(auth_exc=TeploenergoAuthError("bad")):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrongpassword"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD
