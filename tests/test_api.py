"""Tests for TeploenergoApi."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.teploenergo.exceptions import (
    TeploenergoAuthError,
    TeploenergoConnectionError,
)
from custom_components.teploenergo.teploenergo_api import TeploenergoApi


def _make_response(data: dict, status: int = 200):
    """Build a mock aiohttp response that works as async context manager."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.read = AsyncMock(return_value=b"%PDF mock")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.fixture
def api():
    return TeploenergoApi("user@example.com", "secret")


# ── authenticate ──────────────────────────────────────────────────────────────


async def test_authenticate_extracts_sessid_from_result(api):
    resp = _make_response({"Status": True, "ErrorCode": None, "Text": "", "Result": "abc123"})
    with patch.object(api._ensure_session(), "post", return_value=resp):
        await api.authenticate()
    assert api._sessid == "abc123"
    assert api.is_authenticated


async def test_authenticate_raises_auth_error_on_failure(api):
    resp = _make_response({"Status": False, "ErrorCode": None, "Text": "WRONG_PASSWORD", "Result": None})
    with patch.object(api._ensure_session(), "post", return_value=resp):
        with pytest.raises(TeploenergoAuthError):
            await api.authenticate()


# ── _get / session expired ────────────────────────────────────────────────────


async def test_get_retries_after_session_expired(api):
    api._sessid = "old_sessid"
    expired_resp = _make_response({"Status": False, "Text": "SESSION_EXPIRED", "Result": None})
    ok_resp = _make_response({"Status": True, "Text": "", "Result": [{"number": "123", "UF_LS": "123",
                                                                        "ID": "1", "address": "",
                                                                        "owner": "", "debt": "0",
                                                                        "postalIndex": "603057"}]})
    auth_resp = _make_response({"Status": True, "Text": "", "Result": "new_sessid"})

    session = api._ensure_session()
    call_count = 0

    async def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ok_resp if call_count > 1 else expired_resp

    with patch.object(session, "get", side_effect=fake_get):
        with patch.object(session, "post", return_value=auth_resp):
            result = await api._get("/bills/list/")

    assert api._sessid == "new_sessid"
    assert isinstance(result, list)


# ── get_accounts ──────────────────────────────────────────────────────────────


async def test_get_accounts_parses_fields(api):
    api._sessid = "sessid"
    raw = {
        "Status": True, "Text": "", "Result": [{
            "ID": "115916", "UF_LS": "7024690127", "number": "7024690127",
            "address": "Нижний Новгород", "owner": "%D0%A2%D0%B5%D1%81%D1%82",
            "debt": "12.50", "postalIndex": "603057",
        }]
    }
    resp = _make_response(raw)
    with patch.object(api._ensure_session(), "get", return_value=resp):
        accounts = await api.get_accounts()

    assert len(accounts) == 1
    acc = accounts[0]
    assert acc.ls == "7024690127"
    assert acc.account_id == "115916"
    assert acc.postal_index == "603057"
    assert acc.debt == 12.5
    assert acc.owner == "Тест"


# ── get_meters ────────────────────────────────────────────────────────────────


async def test_get_meters_splits_otop_and_gvs(api):
    api._sessid = "sessid"
    raw = {
        "Status": True, "Text": "", "Result": {
            "otop": [{"id": "u1", "meterId": 1001, "number": "OT-001",
                       "type": "ИТП Отопление", "value1": 23.875, "value2": None,
                       "measureDate": "27.05.2026", "verifyDate": "29.01.2032",
                       "aType": "Отопление", "verifyDateTime": 1958936400, "measureDateTime": 0}],
            "gvs": [{"id": "u2", "meterId": 2001, "number": "GV-001",
                      "type": "ИПУ ГВС", "value1": 17.1, "value2": None,
                      "measureDate": "27.05.2026", "verifyDate": "20.01.2032",
                      "aType": "ГВС", "verifyDateTime": 1958158800, "measureDateTime": 0}],
        }
    }
    resp = _make_response(raw)
    with patch.object(api._ensure_session(), "get", return_value=resp):
        meters = await api.get_meters()

    assert len(meters) == 2
    assert meters[0].meter_type == "otop"
    assert meters[1].meter_type == "gvs"
    assert meters[1].value1 == 17.1


# ── send_meter_reading ────────────────────────────────────────────────────────


async def test_send_meter_reading_posts_correct_body(api):
    api._sessid = "test_sessid"
    resp = _make_response({"Status": True, "Text": "", "Result": None})

    session = api._ensure_session()
    with patch.object(session, "post", return_value=resp) as mock_post:
        await api.send_meter_reading(ls="7024690127", meter_id=70180714, value=18.5)

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["meterId"] == "70180714"
    assert kwargs["data"]["value"] == "18.5"
    assert kwargs["data"]["ls"] == "7024690127"
    assert kwargs["data"]["sessid"] == "test_sessid"
