from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "teploenergo"
MANUFACTURER = "Теплоэнерго НН"
BASE_URL = "https://mobilelk.oko-nn.ru"
CONF_LS = "ls"
CONF_ACCOUNT_ID = "account_id"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]
UPDATE_INTERVAL = timedelta(hours=1)

METER_TYPE_GVS = "gvs"
METER_TYPE_OTOP = "otop"
UNIT_GCAL = "Гкал"
