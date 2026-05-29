from unittest.mock import AsyncMock, patch

import pytest
import pytest_socket
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


# On Windows, ProactorEventLoop creates a TCP socket-pair via socket.socketpair()
# during __init__, which is blocked by pytest-homeassistant-custom-component's
# pytest_runtest_setup hook. We re-enable sockets around every fixture setup so
# the event loop can be created; all actual HTTP calls are mocked so no real
# network traffic escapes.
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    pytest_socket.enable_socket()
    yield
    pytest_socket.disable_socket(allow_unix_socket=True)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teploenergo.const import CONF_ACCOUNT_ID, CONF_LS, DOMAIN
from custom_components.teploenergo.teploenergo_api import (
    AccountInfo,
    AccrualRecord,
    MeterInfo,
)

# ── Shared test data ──────────────────────────────────────────────────────────

TEST_LOGIN = "test@example.com"
TEST_PASSWORD = "testpass"
TEST_LS = "7024690127"
TEST_ACCOUNT_ID = "115916"
TEST_POSTAL_INDEX = "603057"

MOCK_ACCOUNT = AccountInfo(
    ls=TEST_LS,
    account_id=TEST_ACCOUNT_ID,
    address="Нижний Новгород, тестовая, 1/1",
    owner="Тестов Тест Тестович",
    debt=0.0,
    postal_index=TEST_POSTAL_INDEX,
)

MOCK_ACCRUALS = [
    AccrualRecord(
        period="Май 2026",
        period_time=1748743200,
        balance=502.3,
        sum_tariff=2904.99,
        sum_recalculation=-1783.62,
        sum_fine=0.0,
        sum_itog=1121.37,
        sum_pay=1623.67,
    ),
    AccrualRecord(
        period="Апрель 2026",
        period_time=1743462000,
        balance=0.0,
        sum_tariff=2998.69,
        sum_recalculation=0.0,
        sum_fine=0.0,
        sum_itog=2998.69,
        sum_pay=3089.4,
    ),
]

MOCK_METERS = [
    MeterInfo(
        uid="79780663-366f-4076-95c4-c58f1fd68dd4",
        meter_id=70236093,
        number="20-002890",
        meter_type="otop",
        type_label="ИТП Отопление",
        a_type="Отопление",
        value1=23.875,
        value2=None,
        measure_date="27.05.2026",
        verify_date="29.01.2032",
        verify_datetime=1958936400,
    ),
    MeterInfo(
        uid="c424c3a0-3180-4ba1-91ae-52fb3fc1e21c",
        meter_id=70180714,
        number="0102270275",
        meter_type="gvs",
        type_label="ИПУ ГВС",
        a_type="ГВС",
        value1=17.1,
        value2=None,
        measure_date="27.05.2026",
        verify_date="20.01.2032",
        verify_datetime=1958158800,
    ),
]

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"ЛС {TEST_LS}",
        unique_id=f"{DOMAIN}_{TEST_LS}",
        data={
            CONF_USERNAME: TEST_LOGIN,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_LS: TEST_LS,
            CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
        },
    )


@pytest.fixture
def mock_api():
    """Patch TeploenergoApi wherever it is constructed and return the mock instance."""
    with patch(
        "custom_components.teploenergo.teploenergo_api.TeploenergoApi",
        autospec=True,
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.is_authenticated = False
        instance.authenticate = AsyncMock()
        instance.get_accounts = AsyncMock(return_value=[MOCK_ACCOUNT])
        instance.get_debt = AsyncMock(return_value=0.0)
        instance.get_accruals = AsyncMock(return_value=MOCK_ACCRUALS)
        instance.get_meters = AsyncMock(return_value=MOCK_METERS)
        instance.send_meter_reading = AsyncMock()
        instance.download_bill = AsyncMock(return_value=b"%PDF-1.4 mock")
        instance.close = AsyncMock()
        yield instance
