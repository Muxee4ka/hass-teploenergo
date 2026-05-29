<div align="center">

<img src="custom_components/teploenergo/brand/logo.png" alt="Теплоэнерго НН" width="400">

# Теплоэнерго НН для Home Assistant

**Неофициальная интеграция личного кабинета Теплоэнерго Нижний Новгород для Home Assistant.**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/Muxee4ka/hass-teploenergo/tests.yml?branch=master&label=tests&style=flat-square)](https://github.com/Muxee4ka/hass-teploenergo/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/Muxee4ka/hass-teploenergo?style=flat-square)](https://github.com/Muxee4ka/hass-teploenergo/releases/latest)

</div>

---

Подключает [личный кабинет Теплоэнерго НН](https://mobilelk.teploenergo-nn.ru) к Home Assistant: отображение задолженности, начислений и показаний приборов учёта, передача показаний счётчиков и скачивание квитанций. Авторизация — по e-mail и паролю от мобильного приложения.

## Что умеет

- **Задолженность** — текущий баланс по лицевому счёту
- **Начисления** — сумма к оплате, итоговое начисление и входящий остаток за последний расчётный период
- **Приборы учёта** — текущие показания счётчиков ГВС (м³) и ИТП Отопления (Гкал)
- **Срок поверки** — дата следующей поверки каждого прибора
- **Передача показаний** — ввод и отправка показаний прямо из Home Assistant
- **Квитанция** — скачивание PDF-квитанции одной кнопкой (сохраняется в `/www/teploenergo/` с уведомлением и ссылкой для скачивания)

Данные обновляются каждый час. Поддерживается несколько лицевых счётов — каждый добавляется как отдельное устройство.

## Установка

### Через HACS (рекомендуется)

1. HACS → **Интеграции** → **⋮** → **Пользовательские репозитории**
2. URL: `https://github.com/Muxee4ka/hass-teploenergo`, категория **Integration**
3. Найти **Теплоэнерго НН** в списке и установить
4. Перезапустить Home Assistant

### Вручную

Скопировать папку `custom_components/teploenergo` из [последнего релиза](https://github.com/Muxee4ka/hass-teploenergo/releases/latest) в `<config>/custom_components/` и перезапустить HA.

## Настройка

[Настройки](https://my.home-assistant.io/redirect/config) → **Устройства и службы** → [**Добавить интеграцию**](https://my.home-assistant.io/redirect/config_flow_start?domain=teploenergo) → найти **Теплоэнерго НН**.

[![Добавить интеграцию](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=teploenergo)

| Поле | Что вводить |
|---|---|
| **E-mail** | Адрес электронной почты от личного кабинета |
| **Пароль** | Пароль от личного кабинета / мобильного приложения |

## Создаваемые объекты

Для каждого лицевого счёта создаётся одно устройство со следующими объектами:

| Платформа | Объект | Описание |
|---|---|---|
| `sensor` | Задолженность | Текущий долг, ₽ |
| `sensor` | Начислено | Итог за последний период, ₽ |
| `sensor` | К оплате | Сумма к оплате, ₽ |
| `sensor` | Входящий остаток | Баланс на начало периода, ₽ |
| `sensor` | Расчётный период | Дата последнего периода (diagnostic) |
| `sensor` | Показание × N | Текущее значение каждого ПУ (Гкал или м³) |
| `sensor` | Срок поверки × N | Дата поверки каждого ПУ (diagnostic) |
| `number` | Ввод показания × N | Передача показаний |
| `button` | Скачать квитанцию | Загрузка PDF в `/www/teploenergo/` |

## Примеры автоматизаций

<details>
<summary><b>Уведомление о задолженности</b></summary>

```yaml
alias: "Уведомление о долге Теплоэнерго"
trigger:
  - platform: numeric_state
    entity_id: sensor.teploenergo_ls_XXXXXXXXXX_debt
    above: 0
action:
  - service: notify.mobile_app
    data:
      title: "Теплоэнерго — задолженность"
      message: >-
        Задолженность: {{ states('sensor.teploenergo_ls_XXXXXXXXXX_debt') }} ₽
```

</details>

<details>
<summary><b>Автоматическая передача показаний</b></summary>

```yaml
alias: "Передача показаний ГВС"
trigger:
  - platform: time
    at: "09:00:00"
  condition:
    - condition: template
      value_template: "{{ now().day == 25 }}"
action:
  - service: number.set_value
    target:
      entity_id: number.teploenergo_ls_XXXXXXXXXX_meter_XXXXXXXX_input
    data:
      value: "{{ states('sensor.teploenergo_ls_XXXXXXXXXX_meter_XXXXXXXX_reading') }}"
```

</details>

<details>
<summary><b>Скачать квитанцию и уведомить</b></summary>

```yaml
alias: "Квитанция Теплоэнерго"
trigger:
  - platform: time
    at: "10:00:00"
  condition:
    - condition: template
      value_template: "{{ now().day == 1 }}"
action:
  - service: button.press
    target:
      entity_id: button.teploenergo_ls_XXXXXXXXXX_download_bill
```

После нажатия Home Assistant создаст уведомление со ссылкой на PDF.

</details>

## Поддержка

- **Баги и пожелания** — [Issues](https://github.com/Muxee4ka/hass-teploenergo/issues)
- **Telegram автора** — [@Muxee4ka](https://github.com/Muxee4ka)

## Лицензия

[MIT](LICENSE) — используйте, форкайте, модифицируйте.
