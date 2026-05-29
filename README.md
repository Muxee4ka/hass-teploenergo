# Теплоэнерго НН — Home Assistant интеграция

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Muxee4ka/hass-teploenergo)](https://github.com/Muxee4ka/hass-teploenergo/releases)
[![CI](https://github.com/Muxee4ka/hass-teploenergo/actions/workflows/tests.yml/badge.svg)](https://github.com/Muxee4ka/hass-teploenergo/actions/workflows/tests.yml)

Интеграция для личного кабинета [Теплоэнерго Нижний Новгород](https://mobilelk.teploenergo-nn.ru): отображение задолженности, начислений и показаний приборов учёта, передача показаний и скачивание квитанций.

## Возможности

- **Задолженность** — текущий баланс по лицевому счёту
- **Начисления** — сумма к оплате, итоговое начисление и остаток за последний расчётный период
- **Приборы учёта** — текущие показания счётчиков ГВС (м³) и ИТП Отопления (Гкал)
- **Срок поверки** — дата следующей поверки каждого прибора
- **Передача показаний** — ввод и отправка показаний прямо из Home Assistant
- **Квитанция** — скачивание PDF-квитанции одной кнопкой (сохраняется в `/www/teploenergo/` с уведомлением и ссылкой)

Данные обновляются каждый час. Поддерживается несколько лицевых счётов — каждый добавляется как отдельное устройство.

## Установка через HACS

1. В HACS выберите **Custom repositories** → вставьте `https://github.com/Muxee4ka/hass-teploenergo` → категория **Integration**.
2. Установите **Теплоэнерго НН** и перезапустите Home Assistant.
3. Перейдите в **Настройки → Устройства и службы → Добавить интеграцию** → найдите **Теплоэнерго НН**.
4. Введите e-mail и пароль от личного кабинета.

## Ручная установка

Скопируйте папку `custom_components/teploenergo` в директорию `custom_components` вашей конфигурации Home Assistant и перезапустите.

## Создаваемые объекты

Для каждого лицевого счёта создаётся одно устройство со следующими объектами:

| Объект | Тип | Описание |
|--------|-----|----------|
| Задолженность | Sensor | Текущий долг, ₽ |
| Начислено | Sensor | Итог за последний период, ₽ |
| К оплате | Sensor | Сумма с учётом перерасчётов, ₽ |
| Входящий остаток | Sensor | Баланс на начало периода, ₽ |
| Расчётный период | Sensor | Дата последнего периода (diagnostic) |
| Показание счётчика × N | Sensor | Текущее значение каждого ПУ |
| Срок поверки × N | Sensor | Дата поверки каждого ПУ (diagnostic) |
| Ввод показания × N | Number | Передача показаний |
| Скачать квитанцию | Button | Загрузка PDF |

## Разработка и тесты

```powershell
# Установка зависимостей
pip install pytest-homeassistant-custom-component pytest-asyncio

# Запуск тестов
pytest tests/ -v
```

Тесты запускаются на Windows и Linux (CI — GitHub Actions, ubuntu-latest, Python 3.12 и 3.13).
