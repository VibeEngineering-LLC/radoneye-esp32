---
name: radoneye-esp32
version: 0.2.0
description: |
  RadonEye Plus2 / RD200P / Plus3 — единый скилл по семейству радон-детекторов.
  Часть 1 — ESPHome BLE-шлюз на ESP32-DevKitC: до 3 устройств → narodmon.ru.
  Часть 2 — Python BLE-клиент V1 (snapshot одного устройства, см.
  references/python_v1_client.md и scripts/radon_snapshot.py).
  Применяй при подключении любого RadonEye по BLE: разовый снимок, периодический
  поллинг, ESPHome-интеграция в Home Assistant, выгрузка на Народмон.
---

# RadonEye ESP32 — BLE-шлюз + Python-клиент V1

## Актуальная прошивка `radon_ha_gateway_c3.yaml` v2.1-step3 (2026-06-17)

**Целевая плата:** Seeed Studio **XIAO ESP32-C3** (board `seeed_xiao_esp32c3`,
variant `esp32c3`, framework **arduino** — esp-idf на Windows без MSYS2 не работает).

Функции:
- BLE-клиент к **RadonEye Plus2** (опкоды whitelist `{0x10, 0x50, 0x51, 0x53, 0x54,
  0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`; опрос шлюзом — только
  `0x50/0x51`, см. `references/plus2_protocol.md` и INC-13);
- `bluetooth_proxy` (HA discovers BLE devices через шлюз);
- Web Server v3 + sorting_groups (`sg_sensors`, `sg_ble`, `sg_actions`, `sg_narodmon`,
  `sg_diag`) + Basic Auth (`user=radon`);
- API encryption для Home Assistant;
- **step3 (2026-06-17): Народмон-инфраструктура, по умолчанию ВЫКЛ**:
  - `http_request` (verify_ssl: false, timeout 5s);
  - `switch narodmon_enabled` — **`restore_mode: ALWAYS_OFF`** (HARD safety: после
    любого reboot / safe-mode / factory_reset switch гарантированно вернётся в OFF);
  - `button narodmon_send_now` — ручной триггер;
  - `select narodmon_method` — `HTTP GET / HTTP POST / HTTPS POST / JSON POST`
    (дефолт `HTTP GET`, `restore_value: true`);
  - `text nm_radon=RR1 / nm_temp=T1 / nm_hum=H1` (имена метрик Народмона);
  - `script send_narodmon` (4 if-ветви по протоколу, guarded by `wifi.connected:` +
    `!std::isnan(s_radon.state)`; ID Народмона = `esphome::get_mac_address()` —
    нативный API, MAC без двоеточий);
  - `interval 600s` — авто-отправка ТОЛЬКО при `narodmon_enabled.state == true`.

**HARD-правило проекта:** в любой ESPHome-прошивке агента, где есть Народмон-инфраструктура,
switch `narodmon_enabled` ОБЯЗАН иметь `restore_mode: ALWAYS_OFF`. Пользователь никогда не
получит сюрприза включённой выгрузки.

Параллельный пакет на ESP32-S3 для **Radex MR107ion** — см.
[`VibeEngineering-LLC/radex-esp32`](https://github.com/VibeEngineering-LLC/radex-esp32),
прошивка `radex_gateway_s3.yaml` step3.

Старая прошивка `radon_ha_gateway.yaml` (ESP32-DevKitC) — оставлена для совместимости.

---

Скилл объединяет два уровня работы с семейством RadonEye:

- **Часть 1 (основная) — ESPHome шлюз** на ESP32-DevKitC: постоянная служба,
  3× устройства, выгрузка на narodmon.ru. Это содержимое ниже.
- **Часть 2 — Python BLE-клиент V1** для ad-hoc снимков с одного устройства:
  см. [`references/python_v1_client.md`](references/python_v1_client.md)
  и [`scripts/radon_snapshot.py`](scripts/radon_snapshot.py).

Объединение ранее раздельных частей (ESPHome-шлюз + Python BLE-клиент) выполнено
2026-06-13 — историческая справка.

# RadonEye ESPHome Gateway

Проект: три RadonEye Plus2 → ESP32 (ESPHome) → народмон.

## Железо

| Компонент | Спецификация |
|---|---|
| Плата | ESP32-DevKitC, WROOM-32 модуль |
| USB-UART | CH340C |
| Разъём | USB Type-C |
| Пины | 38-pin |
| Питание | 5V через USB Type-C (зарядник от телефона ≥1А) |
| Потребление | ~100–150 мА средн., пики до 240 мА (BLE+WiFi) |
| BLE | Встроенный, Bluetooth 4.2 |
| WiFi | 802.11 b/g/n, 2.4 GHz |

Дополнительного железа не нужно — всё беспроводное.

## Архитектура

```
ESP32-DevKitC (ESPHome)
  │
  ├─ каждые 10 мин:
  │    connect → RadonEye #1 (BLE) → read → disconnect
  │    connect → RadonEye #2 (BLE) → read → disconnect
  │    connect → RadonEye #3 (BLE) → read → disconnect
  │
  └─ HTTP POST → narodmon.ru
```

**Последовательный опрос** — не параллельный. RadonEye обновляет данные раз в 10 минут,
один опрос занимает ~5с, три устройства = ~15с. Параллельные BLE-подключения не нужны.

## RadonEye V1 протокол (краткий)

Полный spec — [`references/v1_protocol.md`](references/v1_protocol.md).

| UUID characteristic | Назначение |
|---|---|
| `00001524-1212-efde-1523-785feabcd123` | TX (write команды) |
| `00001525-1212-efde-1523-785feabcd123` | RX (notify ответы) |

Опрос одного устройства:
1. Connect
2. Subscribe notify на `0x1525`
3. Write `0x50` → notify 20 байт → bytes 2–6 float32 LE = radon текущий (pCi/L)
4. Write `0x51` → notify 20 байт → bytes 4–6 uptime (мин), bytes 12–16 peak (pCi/L)
5. Disconnect

Конвертация: `pCi/L × 37 = Бк/м³`

## ESPHome компоненты

| Компонент | Применение |
|---|---|
| `esp32_ble_tracker` | Обнаружение устройств (опционально) |
| `ble_client` | Активное подключение + read/write/notify |
| `http_request` | Отправка на народмон |
| `interval` | Таймер опроса каждые 10 мин |

ESPHome не имеет готового компонента RadonEye V1 в ядре.
Реализация через `ble_client` + C++ lambda внутри `on_connect`.

## Народмон API

Шлюз отправляет показания на `narodmon.ru` по HTTP GET каждые 10 минут (опционально,
по умолчанию выключено — см. блок про `narodmon_enabled` выше). Полная документация
протокола Народмона (TCP/UDP/HTTP/MQTT/JSON, префиксы метрик, коды ответа, правила
бана) — публичная wiki проекта `narodmon.ru`.

## Web UI (ESPHome web_server v3)

После прошивки доступен на `http://radon-gateway.local/` (mDNS) или по IP. Группы UI:

| Группа | Содержимое |
|---|---|
| Поиск BLE устройств | text-поле фильтра, кнопки «Запустить скан 30s», «Стоп», «Очистить», text_sensor со списком (MAC \| name \| RSSI), счётчик найденных, 3× text «MAC Radon N», кнопка «Применить MAC и перезагрузить» |
| Показания радона | 3× sensor (Bq/m³), accuracy 1 знак |
| Статус BLE | 3× binary_sensor — подключено / нет |
| Имена датчиков | 3× text — настраиваются в UI (NVS) |
| Опрос | number-slider 5–60 мин |
| Народмон | switch вкл/выкл + 3× text имена сенсоров |
| Действия | button: «Опросить сейчас» / «Перезагрузить» / «Сбросить WiFi» |
| RE / Отладка BLE | сырой hex notify, кнопки опкодов 0x50/0x51, поле произвольного hex |
| Диагностика | IP, MAC, SSID, WiFi RSSI, uptime |

### BLE-сканер (без nRF Connect)

Прошивка сама ищет BLE-устройства в окружении. Алгоритм:
1. В Web UI поле «Фильтр имени BLE» — по умолчанию `FR` (RadonEye рекламируется как `FR:R…`). Пусто → показывать все.
2. Нажать «Запустить скан BLE 30s» — за 30 секунд `esp32_ble_tracker.on_ble_advertise` собирает уникальные MAC, имя и RSSI в `g_scan_results` (std::string), text_sensor `found_devices` публикует список.
3. Скопировать нужные MAC в поля «MAC Radon 1/2/3».
4. Нажать «Применить MAC и перезагрузить» — text-поля с `restore_value: true` сохраняются в NVS, ESP уходит в reboot.
5. После загрузки в `on_boot` (priority -300) lambda парсит сохранённые MAC и вызывает `id(ble_radonN).set_address(parsed)` до того как `auto_connect: true` начнёт коннектиться.

⇒ MAC меняются без перекомпиляции и без `secrets.yaml`. Заглушки в `secrets.yaml` остаются — они работают как fallback если поля UI пустые.

### REST API для удалённого реверса (esp_api.py)

`scripts\esp_api.py` (внутри проекта-потребителя) — Python обёртка REST API ESPHome web_server v3. Используется Claude'ом из Bash для дистанционного управления и реверса BLE-протокола без USB и nRF Connect.

```bash
# В сети с шлюзом:
python esp_api.py status                           # JSON состояние всех клиентов
python esp_api.py scan --filter FR --duration 30   # запустить скан + дождаться
python esp_api.py devices                          # JSON списка найденных
python esp_api.py set-mac 1 AA:BB:CC:DD:EE:FF      # задать MAC
python esp_api.py apply                            # применить + reboot
python esp_api.py opcode 1 0x50                    # отправить опкод, прочитать raw
python esp_api.py send-hex 1 5001AABB              # произвольный hex (только Radon 1)
python esp_api.py raw 1                            # последний hex-ответ Radon N
python esp_api.py events                           # SSE стрим всех state changes
```

Endpoint'ы ESPHome web_server v3 (без auth, в локальной сети):
- `GET  /sensor/<id>` / `/text_sensor/<id>` / `/binary_sensor/<id>` — JSON состояние
- `POST /button/<id>/press`
- `POST /text/<id>/set?value=...`
- `POST /switch/<id>/turn_on|turn_off`
- `POST /number/<id>/set?value=N`
- `GET  /events` — Server-Sent Events live стрим

## Captive portal — единственный способ ввода WiFi

**WiFi SSID/password НИКОГДА не вписываются в YAML/`secrets.yaml`.** Только через телефон при первом включении.

В `secrets.yaml` `wifi_ssid`/`wifi_password` стоят как намеренные заглушки `__set_via_phone_captive_portal__`. ESPHome требует эти поля синтаксически, но они никогда не должны быть реальными — они нужны только чтобы YAML парсился. Реальные credentials живут в NVS ESP'шки после первого ввода через captive portal.

Flow первого подключения:
1. ESP стартует, пытается подключиться к заглушечному SSID → fail → таймаут.
2. Поднимает AP **«radon-gateway Fallback»** (пароль из `secrets.yaml: ap_password`).
3. Телефон видит AP → коннектится → ОС сама показывает captive portal (форма SSID/password из списка обнаруженных сетей).
4. После ввода — ESP сохраняет в NVS, перезагружается, подключается к домашней сети.
5. При повторных загрузках — берёт из NVS, AP больше не поднимается (если есть NVS-creds).
6. Чтобы сбросить WiFi и снова попасть в captive portal — кнопка «Сбросить настройки и WiFi [factory-reset]» в группе «Действия».

## OTA

- **USB**: `esphome upload firmware\radon_gateway.yaml --device COMX`
- **По воздуху**: `esphome upload firmware\radon_gateway.yaml --device radon-gateway.local`
- **Через Web UI**: компонент `ota: web_server` даёт форму загрузки `.bin` прямо в браузере

## RE-режим (реверсинжиниринг BLE)

Для каждого RadonEye:
- `text_sensor` «Radon N: сырой ответ (hex)» — последний notify в hex (обновляется автоматически).
- `button` «опкод 0x50 / 0x51» — ручная отправка известных команд.
- `button` «отправить произвольный hex» + `text` поле — для исследования новых опкодов.

Hex-команда задаётся без `0x` и без пробелов, например: `50`, `51`, `5001AABB`.

## Статус

| Шаг | Статус |
|---|---|
| Выбор железа | ✅ ESP32-DevKitC, CH340C, Type-C |
| Архитектура | ✅ последовательный опрос, 3 устройства |
| ESPHome YAML конфиг | ✅ написан, валидация `esphome config` пройдена |
| Web UI v3 + sorting groups | ✅ работает, HTTP 200, ~228 KB |
| RE-режим (hex + опкоды) | ✅ встроен |
| BLE-сканер в UI (без nRF Connect) | ✅ встроен и **подтверждён live** (12 устройств за 30s, включая AtomFast −68 dBm) |
| Runtime MAC через UI (без перекомпиляции) | ✅ встроен |
| REST API helper esp_api.py | ✅ создан |
| **Компиляция и прошивка** | ✅ **2026-06-11**, build через CH340-COM (порт зависит от хоста), IP DHCP в локальной сети |
| **REST API live-тест** | ✅ GET / POST set / POST press подтверждены |
| **RSSI sensor → график в Web UI v3** | ✅ паттерн live, AtomFast −37 dBm обновляется ≈ 1/с |
| **AtomFast как 4-я сущность** | ✅ MAC (placeholder `AA:BB:CC:DD:EE:FF` в публичных файлах), имя редактируется, RSSI-график работает |
| Captive portal | ⚠️ **не отлажен** в ESPHome 2026.5.3 (см. Known issues) |
| MAC-адреса RadonEye | ⬜ задать через UI когда устройства будут в эфире |
| Live-валидация показаний RadonEye | ⬜ ждём включения RadonEye Plus2 в зоне |
| Опрос dose-rate AtomFast | ⬜ нужен реверс service UUID (известна только characteristic UUID) |
| Народмон upload | ⬜ ждёт показаний от любого прибора |

## Ключевые файлы прошивки

Пути относительно корня скилла (`radoneye-esp32/`):

| Файл | Путь |
|---|---|
| Основная прошивка (C3) | `firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml` |
| Базовая прошивка (DevKitC) | `firmware\esp32-classic\radon_ha_gateway.yaml` |
| Секреты | `firmware\secrets.yaml` (gitignored) |
| Шаблон секретов | `firmware\secrets.example.yaml` |
| .gitignore | `firmware\.gitignore` |
| REST helper | `scripts\esp_api.py` |

## Команды (ESPHome 2026.5.3, установлен в Python 3.12)

```powershell
# Подставь свой путь к esphome.exe (типовое расположение: <LocalAppData>\Programs\Python\Python312\Scripts\esphome.exe).
$esp = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\esphome.exe"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"

& $esp version                                                                # 2026.5.3
& $esp config firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml                 # валидация
& $esp compile firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml                # сборка
& $esp upload firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml --device COMX   # USB прошивка
& $esp upload firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml --device radon-gw.local  # OTA
& $esp logs firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml --device COMX     # просмотр логов
```

## Следующий шаг

WiFi SSID/password и MAC RadonEye'ев — **всё через телефон/Web UI**, ничего вписывать в `secrets.yaml` не нужно.

1. `esphome compile firmware\radon_gateway.yaml` — первая сборка ~5 мин (скачивает toolchain).
2. `esphome upload firmware\radon_gateway.yaml --device COMX` — прошивка через USB.
3. Дождаться пока ESP поднимет AP **«radon-gateway Fallback»** (≈30с после старта).
4. На телефоне → подключиться к AP (пароль `radon-fallback-ap` из `secrets.yaml: ap_password`) → ОС автоматически откроет captive portal → выбрать домашний WiFi и ввести пароль → ESP перезагрузится и подключится.
5. Открыть `http://radon-gateway.local/` (или по IP из роутера) → группа «Поиск BLE устройств» → «Запустить скан BLE 30s» → скопировать MAC RadonEye'ев в поля «MAC Radon 1/2/3» → «Применить MAC и перезагрузить».
6. После reboot: проверить «Статус BLE» (3× connected) → опросить вручную «Опросить сейчас [poll]» → проверить «Показания радона».
7. Опционально удалённо: `python scripts\esp_api.py status` / `scan` / `opcode 1 0x50`.

## Текущее состояние прошивки (2026-06-11)

| Параметр | Значение |
|---|---|
| ESPHome | 2026.5.3 (типовой путь `$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\esphome.exe`) |
| Build path | любая ASCII-папка вне проекта, напр. `C:\esp32_build\radon-gateway\` (bypass кириллицы в пути проекта) |
| Целевой YAML | `firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml` (либо `firmware\esp32-classic\radon_ha_gateway.yaml` для DevKitC) |
| COM-порт ESP32 | определяется live (`Get-CimInstance Win32_PnPEntity | Where Name -match 'CH340|CP210|FTDI'`) — не доверять памяти, всегда сканировать заново перед прошивкой |
| IP в домашней сети | DHCP, SSID `!secret wifi_ssid` |
| mDNS | `radon-gateway.local` ✓ |
| Web UI | `http://radon-gateway.local/` или `http://<dhcp-ip>/` |
| Entities | ~45 (после добавления AtomFast + 4 RSSI) |
| Тест-устройство в эфире | AtomFast (MAC в `!secret atomfast_mac`), −37 dBm стабильно |

### AtomFast как 4-я сущность

Для проверки UX переименования и графиков (RadonEye'и могут быть выключены) добавлен 4-й условный slot:

| Поле UI | ID | Дефолт |
|---|---|---|
| MAC AtomFast | `mac_atomfast` | `AA:BB:CC:DD:EE:FF` (вписывается через Web UI) |
| Имя AtomFast | `name_atomfast` | `AtomFast` |
| RSSI AtomFast | `rssi_atomfast` | живой, ≈ 1/с при advert |

Опрос dose-rate AtomFast пока **не реализован** — зафиксирован только characteristic UUID `70BC767E-7A1A-4304-81ED-14B9AF54F7BD` (notify, 0.5 Hz, payload содержит float32 LE dose-rate в архивной записи на offset 15..18). Service UUID не известен — нужен реверс через nRF Connect или `on_connect` lambda с обходом service map. См. отдельный публичный проект [`VibeEngineering-LLC/atomfast-esp32`](https://github.com/VibeEngineering-LLC/atomfast-esp32).

### Паттерн «RSSI-график для каждого BLE-устройства»

Добавляет числовой `template sensor` для каждого настроенного MAC и обновляет его из `esp32_ble_tracker.on_ble_advertise`. ESPHome Web UI v3 рисует sparkline + раскрывает полный график при клике (стандартное поведение для числовых sensor).

```yaml
sensor:
  - platform: template
    name: "RSSI Radon 1"
    id: rssi_radon1
    unit_of_measurement: "dBm"
    accuracy_decimals: 0
    update_interval: never

esp32_ble_tracker:
  on_ble_advertise:
    - then:
        - lambda: |-
            std::string mac = x.address_str();
            int rssi = x.get_rssi();
            auto pub = [&](const std::string &target, esphome::template_::TemplateSensor *s) {
              if (target.length() != 17 || target == "00:00:00:00:00:00") return;
              if (mac == target) s->publish_state((float) rssi);
            };
            pub(id(mac_radon1).state,   id(rssi_radon1));
            pub(id(mac_atomfast).state, id(rssi_atomfast));
```

Цена в трафике — нулевая (advert приходит и так каждые ~1.1с при `scan_parameters.interval/window: 1100ms`).

## Тест-план полного цикла после прошивки

Стандартный прогон после каждого `esphome run`:

```powershell
$ESP  = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\esphome.exe"
$YAML = "firmware\xiao-esp32-c3\radon_ha_gateway_c3.yaml"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"

# 0. Идентифицировать COM (никогда не верить памяти)
Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'CH340|CP210|FTDI' }

# 1. Compile + upload + запуск (НЕ "upload" в одиночку!) — заменить COM<N> на реальный
& $ESP run $YAML --device COM<N> --no-logs

# 2. Дать boot 8 сек, проверить mDNS:
Start-Sleep 8
Test-Connection radon-gateway.local -Count 1

# 3. Web UI HTTP 200:
(Invoke-WebRequest http://radon-gateway.local/ -TimeoutSec 5).StatusCode

# 4. SSE-стрим 6 сек ловит rssi_*:
$req = [System.Net.WebRequest]::Create("http://radon-gateway.local/events")
$resp = $req.GetResponse(); $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
$end = (Get-Date).AddSeconds(6)
while ((Get-Date) -lt $end) {
    $l = $reader.ReadLine()
    if ($l -match '^data: (.+)') { $matches[1] | ConvertFrom-Json | Where-Object { $_.id -like "sensor-rssi_*" } | Format-Table -AutoSize }
}

# 5. BLE-скан 30s + список:
Invoke-RestMethod "http://radon-gateway.local/button/____________________________ble_30s__scan-start_/press" -Method Post
Start-Sleep 32
(Invoke-RestMethod "http://radon-gateway.local/text_sensor/___________________ble______________________mac_name_rssi").state
```

При провале на любом шаге — `esphome logs $YAML --device COM8` для серийных логов.

## Known issues / нюансы

- **ESPHome 2026.1+**: убрали `api: password:` — нужен `api: encryption: key:` (base64 32 байта).
- **ESPHome 2026.x**: для `sensor: ble_client` обязателен `type: characteristic`.
- **`text_sensor: ble_client`** не поддерживает `lambda` — для hex используется `text_sensor: template` + `publish_state` из sensor-lambda.
- **MAC placeholder**: при первом написании в `secrets.yaml` MAC должен быть валидным hex (например `00:00:00:00:00:01`), иначе `esphome config` падает на парсинге.
- **BLE+WiFi одновременно**: `wifi: power_save_mode: none` критично, иначе BLE-разрывы.
- **Уникальность имён entities**: ESPHome нормализует кириллицу и emoji к `_` для ASCII ID. Два entity с именами только из emoji/кириллицы дают одинаковый ID и `Duplicate entity` ошибку. Решение — в каждое имя добавлять уникальный ASCII-токен в `[квадратных скобках]`, напр. `Остановить скан [scan-stop]`.
- **on_boot priority для runtime MAC**: lambda с `set_address()` ставим в `priority: -300` — это после ble_client setup, но желательно до первой попытки auto_connect. Если есть гонка — перейти на `auto_connect: false` и `set_enabled(true)` после set_address.

### Bugs/quirks выявленные в прогоне 2026-06-11

- **Captive portal в ESPHome 2026.5.3 не запускается** в комбинации с placeholder SSID (`__set_via_phone_captive_portal__`). Поведение: ESP уходит в бесконечный `RETRY_HIDDEN` STA-цикл, AP-mode не активируется → телефон ничего не видит. Попытки убрать `ssid:` целиком, чтобы получить AP-only — без `ssid:` wifi-компонент **молча** инактивен, AP тоже не поднимается. Временно работаем через прямой STA с реальными credentials в `secrets.yaml` (NB: эти credentials НЕ должны попасть в публичный repo — `secrets.yaml` в `.gitignore`). Корректный captive-portal flow в ESPHome 2026.5.3 — отдельная задача, варианты: `improv_serial` (BLE-провижининг через ESP Web Tools) либо альтернативный кастомный AP-only код через `external_components`.

- **Кириллица в `name:` сущности** → ESPHome нормализует ID в `text-______________________1` (нечитаемо). Решение — на каждой сущности явный `id:` латиницей, name остаётся для UI. Сейчас в `radon_gateway.yaml` IDs снова сделаны латиницей (`rssi_radon1`, `mac_atomfast`, и т.д.).

- **Не доверять номеру COM-порта по памяти.** На многих Windows-машинах «соседние»
  COM-номера занимают встроенные звуковые карты (Creative SoundBlaster и т.п.),
  Bluetooth-стек или виртуальные модемы — попытка прошить такой порт даст ошибку
  «port is open» или просто молчание. Всегда определять ESP32 живым запросом:
  ```powershell
  Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'CH340|CP210|FTDI' }
  ```
  CH340 = ESP32-DevKitC v4 (VID `1A86&7523`), CP210x = старые DevKit и Heltec/TTGO.

- **`esphome upload` после правки YAML — зальёт старый бинарь.** Использовать только `esphome run` (compile+upload) после Edit. `upload` — только если уверен что .bin не менялся.

- **BLE single-client инвариант** (касается AtomFast и ряда других): если устройство уже подключено к телефонному приложению (AtomSpectra/Mi Home/etc) — ESP32 не сможет подключиться. Перед попыткой connect — закрыть приложение на телефоне.

- **`esp32_ble_tracker.scan_parameters.interval == window`**: при `1100ms/1100ms` — 100% duty (continuous scan). При попытках сильно сократить window к < 50ms — могут пропадать advert редко-«дышащих» устройств (RadonEye Plus2 рекламируется ~ раз в 2с). Текущая настройка работает.

- **HARD: бинарники прошивок (.bin / .factory.bin) НЕ публикуются** в этот репозиторий. После
  `esphome compile` файл `.pioenvs/<device>/firmware.bin` содержит WiFi SSID + пароль,
  MAC устройств, OTA-пароль и API encryption key в виде ASCII-строк (любой может
  скачать и `strings firmware.bin`). Стандарт ESPHome-сообщества — выкладывать **только
  YAML + `secrets.example.yaml`**, пользователь собирает у себя со своими секретами.
  Никаких `firmware/bin/` папок в публичном репозитории быть не должно. То же правило
  действует для соседнего проекта
  [`VibeEngineering-LLC/radex-esp32`](https://github.com/VibeEngineering-LLC/radex-esp32).

- **HARD: switch Народмона ВСЕГДА `restore_mode: ALWAYS_OFF`**. В любой ESPHome-прошивке
  с Народмон-инфраструктурой выключатель управления выгрузкой ОБЯЗАН иметь этот
  restore_mode — после reboot/safe-mode/factory_reset/OTA switch гарантированно
  вернётся в OFF. Никаких `RESTORE_DEFAULT_OFF`, `ALWAYS_ON` или отсутствия `restore_mode`
  (default = `RESTORE_DEFAULT_OFF`, который может восстановить ON если пользователь
  забыл выключить перед reboot). Образец — `radon_ha_gateway_c3.yaml` v2.1-step3.
