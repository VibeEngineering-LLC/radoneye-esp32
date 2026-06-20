# Firmware changelog — radoneye-esp32

> 🇬🇧 English version: [CHANGELOG.en.md](CHANGELOG.en.md)

Версионирование: semver (`vMAJOR.MINOR.PATCH`) + плата-суффикс через дефис
(например, `v2.1-c3`).

- MAJOR — несовместимое изменение протокола / архитектуры
- MINOR — добавлена функциональность, обратная совместимость не нарушена
- PATCH — bugfix / стабильность / refactor без изменений API

Дата — UTC+3 (Europe/Moscow).
Активные ветки:
- **`xiao-esp32-c3/radon_ha_gateway_c3.yaml`** — XIAO ESP32-C3 (arduino + Bluedroid)
- **`esp32-classic/radon_ha_gateway.yaml`** — ESP32-DevKitC v4 WROOM-32 (arduino)

Все версии валидированы на RadonEye Plus2 (RD200PLUS).

---

## [unreleased] (2026-06-21)

### Changed
- Removed `bluetooth_proxy` from C3 YAML (WiFi 2.4 GHz interference with nearby devices).
- Reduced WiFi TX power from 20 dBm to 8.5 dBm (`output_power: 8.5dB`) on both C3 and classic boards.
- Added LED heartbeat (100 ms flash every 2 s) for visual board-alive indication (GPIO10 inverted on C3, GPIO2 on classic).

---

## 2026-06-19 — реорганизация firmware/ по подпапкам

**Что:** YAML-файлы прошивок переведены из плоской раскладки `firmware/*.yaml`
в раскладку «одна плата = одна подпапка»:

```
firmware/
├── esp32-classic/         radon_ha_gateway.yaml
├── xiao-esp32-c3/         radon_ha_gateway_c3.yaml
├── secrets.example.yaml   (общий)
├── CHANGELOG.md           (этот файл)
└── .gitignore
```

**Почему:** прошивки теперь выкладываются в индивидуальных папках с
названием по типу платы. Унификация с соседним проектом
`atomfast-esp32`, который использует ту же раскладку
(см. [atomfast-esp32 CHANGELOG.md](https://github.com/VibeEngineering-LLC/atomfast-esp32/blob/main/firmware/CHANGELOG.md)
v0.9.0-c3).

**Что НЕ менялось:** содержимое YAML, `secrets.example.yaml`, версии прошивок.
Это структурное изменение — пути в `INSTALL.md` / `README.md` обновлены под
новую раскладку.

**Затронутые документы:**
- [INSTALL.md](../INSTALL.md) — команды `esphome compile`/`upload` теперь с префиксом подпапки.
- [README.md](../README.md) — таблица «Какая прошивка для какой платы», раздел «Структура скилла».
- `secrets.example.yaml` — обновлены пути в комментариях.

---

## v2.1-c3 (2026-06-17) — порт на Seeed Studio XIAO ESP32-C3 + Народмон-инфраструктура

**Что:** второй параллельный baseline — `radon_ha_gateway_c3.yaml` под
**Seeed Studio XIAO ESP32-C3** (`board: seeed_xiao_esp32c3`, variant
`esp32c3`, framework `arduino`). База: `radon_ha_gateway.yaml` v2.0
(ESP32-DevKitC v4). Народмон-инфраструктура добавлена в Web UI, но **по
умолчанию ВЫКЛЮЧЕНА** (HARD-правило `restore_mode: ALWAYS_OFF`).

**Почему C3-ветка:**
- XIAO ESP32-C3 — самая компактная (~22×18 мм) ESP-плата с BLE+WiFi, USB-C, ~$5.
- Подходит для production-шлюза на **один** RadonEye Plus2 (классический DevKitC v4 поддерживает до 3, но в большинстве случаев избыточен).
- `framework: arduino` выбран осознанно — `esp-idf` на C3 в Windows-toolchain ESPHome подтверждённо нестабилен без MSYS2 (build падает на CMake-этапе).

**Изменения от v2.0 DevKitC:**

1. **Плата**: `esp32: variant: esp32c3, board: seeed_xiao_esp32c3`.
2. **Framework**: `arduino` (то же, что v2.0; на C3 esp-idf требует MSYS2 — отложено).
3. **Build path**: отдельный `D:/esp32_radon_build/radon-gw-c3` (чтобы не пересекался с buildом DevKitC).
4. **`device_name`**: `radon-gw` (вместо `radon-ha-gateway` у v2.0) — короче и не путается с другими шлюзами.
5. **Web Server v3 + sorting_groups (5 групп)**:
   - `sg_sensors` — Радон / Peak / Count / средние час/день / температура
   - `sg_ble` — состояние / реконнекты / RSSI / переподключиться / сбросить
   - `sg_actions` — Safe Mode / factory reset / диагностические
   - `sg_narodmon` — switch ALWAYS_OFF / select протокола / имена метрик RR1/T1/H1 / отправить сейчас
   - `sg_diag` — WiFi сигнал/SSID/IP/MAC / API / uptime / версия прошивки
6. **Народмон-инфраструктура (step3, по умолчанию ВЫКЛ)**:
   - `switch.template narodmon_enabled` — `restore_mode: ALWAYS_OFF` (HARD)
   - `select.template narodmon_method` — 4 опции (`HTTP GET`/`HTTP POST`/`HTTPS POST`/`JSON POST`), дефолт `HTTP GET`
   - `button narodmon_send_now` — ручной триггер
   - `text` поля `nm_radon` (RR1), `nm_temp` (T1), `nm_hum` (H1) — имена метрик Народмона
   - `script send_narodmon` — 4 ветки по протоколам, guard'ы `wifi.connected` + `!std::isnan(s_radon.state)`
   - `interval: 600s` — авто-отправка ТОЛЬКО при `narodmon_enabled.state == true`
   - `http_request: verify_ssl: false, timeout: 5s`
   - `time:` SNTP — был ранее, нужен для HTTPS handshake
7. **`web_server.log: true`** — HARD-исключение для C3 (см. INC-RADON-JSON111 в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)). Если пойдут ребуты / `json:111` / OOM — поменять на `false` без переспроса.
8. **`web_server.auth`**: username `radon` (inline), password = `!secret ota_password`. Basic Auth обязателен (INC-PLUS2 INC-10 mitigation — режет фантомные SSE keepalive на 401).
9. **WiFi-watchdog 180s** — `wifi::global_wifi_component->is_connected()` ложно >180 с → `App.safe_reboot()`.
10. **`api.reboot_timeout: 0s`** — плата не ребутится при потере HA-связи (BLE-сбор работает автономно).

**Сохраняется из v2.0:**

- BLE-клиент к одному RadonEye Plus2 (single-central).
- Whitelist опкодов `{0x50, 0x51}` для штатного опроса (см. INC-RADON-UNIT в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)).
- Парсер 20-байтовых notify-кадров `0x50` / `0x51`:
  - `0x50 [2:4]` → uint16 LE Bq/m³ (instant)
  - `0x50 [12:14]` → uint16 LE Peak
  - `0x50 [14:16]` → uint16 LE Count
  - `0x51 [4:8]` → uint32 LE uptime min
  - `0x51 [18:20]` → live mm:ss часы прибора
- `esp32_ble_tracker.scan_parameters: interval: 640ms, window: 32ms, active: false` (duty 5 %, не резонирует с adv-периодом ~1 с).

**Stability target:** длительный прогон в боевой эксплуатации с 2026-06-17.
Конкретных метрик MTBF на момент публикации — нет.

**Файл:** `firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml`.

---

## v2.0 (2026-06-15) — base DevKitC + live-reverse Plus2 protocol

**Что:** baseline `radon_ha_gateway.yaml` под **ESP32-DevKitC v4** (WROOM-32),
`board: esp32dev`, `framework: arduino`. Полный live-реверс BLE-протокола
RadonEye Plus2 (RD200PLUS), опкоды `{0x50, 0x51, 0x54, 0x56, 0x60, 0x61}`
разобраны байт-в-байт. Поддержка до **3 приборов** одновременно (`radon1_mac`,
`radon2_mac`, `radon3_mac`).

**Почему:** до этой ревизии работали с опкодом `0x50` через blind probe — без
понимания структуры байт. Live-реверс 2026-06-15 (прямое чтение через
Bluetooth ПК + HCI-snoop трасса официального приложения RadonEye+² для
Android) дал точные смещения.

**Изменения от ранних версий:**

1. **Парсер 20-байтовых notify-кадров `0x50`** (instant radon):
   - `[0]` — opcode echo (`0x50`)
   - `[1]` — длина payload (`0x10` = 16)
   - **`[2:4]` — Радон current, uint16 LE, Bq/m³** ← главное поле
   - `[12:14]` — Peak (макс радон), uint16 LE, Bq/m³
   - `[14:16]` — Count (номер замера), uint16 LE
   - `[16:18]` — вторичный счётчик
   - `[18:20]` — часы mm:ss (кэш с момента последнего `0x51`)
2. **Парсер `0x51`** (status/uptime/live-часы):
   - **`[4:8]` — Uptime минуты, uint32 LE** (+1/мин)
   - `[12:14]`, `[14:17]` — конфиг прибора, частично разобран
   - **`[18:20]` — Часы mm:ss (live)** ← полезно для синхронизации
3. **Опкоды `0x60` / `0x61` (история)** разобраны:
   - `0x60` → запрос числа доступных записей (на реальном приборе 9600 ≈ 13 мес почасовой истории)
   - `0x61 <N_u16_LE>` → bulk-дамп N свежих записей на NOTIFY-2 (`0x0010`)
   - Формат 8-байтовой записи:
     - `[0:4]` — Unix-таймстамп, uint32 LE
     - `[4:6]` — Радон, uint16 LE, Bq/m³
     - `[6:8]` — Температура, °C × 256 (Q8.8 fixed-point, делить на 256)
4. **Опкод `0x54`** (версия прошивки + конфиг):
   - `[2]` — units (`01` = Bq/m³, `00` = pCi/L)
   - `[5:7]` — порог тревоги (uint16 LE)
   - `[8:14]` — ASCII «V1.0.2»
5. **Опкод `0x56`** (серийник): 17 ASCII байт в формате «ГГГГММДД» + «SN» + «####» + «PD2».
6. **Whitelist опкодов жёсткий** (HARD): `{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`. Все остальные опкоды в диапазоне `0xA0..0xCF` — DFU-risk (см. INC-RADON-DFU в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)).
7. **Опрос шлюзом — ТОЛЬКО `{0x50, 0x51}`**. `0x53` входит в whitelist, но голый `0x53` обнуляет конфиг прибора (см. INC-RADON-UNIT в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)) — НЕ слать в опросе.
8. **GATT-карта** подтверждена:
   - SERVICE `0x0009` `00001523-1212-efde-1523-785feabcd123` (Nordic-base)
   - CHAR `0x000a` `00001524-…` write — opcode WRITE (value-handle `0x000b`)
   - CHAR `0x000c` `00001525-…` notify — NOTIFY-1 (value-handle `0x000d`) — ответы на опкоды
   - CHAR `0x000f` `00001526-…` notify — NOTIFY-2 (value-handle `0x0010`) — канал истории `0x60`/`0x61`
9. **MTU=23 (default)** — Plus2 НЕ запрашивает увеличение, ATT payload 20 байт хватает (см. INC-PLUS2-MTU23 в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)).
10. **Single-central** — пока подключён телефон с FTLAB-app, ESP получает refuse (см. INC-PLUS2-SINGLE-CENTRAL в [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)).

**Что отдаётся в Home Assistant:**

- `sensor.radon_instant` — мгновенный радон, Bq/m³
- `sensor.radon_pci` — то же в pCi/L (= Bq/m³ ÷ 37)
- `sensor.radonye_uptime_min` — uptime прибора, мин
- `text_sensor.radon_last_updated` — метка времени последнего замера
- `text_sensor.radon_device_clock` — часы прибора mm:ss
- `binary_sensor.radon_ble_connected`
- `sensor.radon_rssi`

**Файл:** `firmware/esp32-classic/radon_ha_gateway.yaml`.

---

## Архитектурные ограничения (не баги)

- **MTU=23, не 247.** Plus2 не отвечает на MTU exchange. Не пытаться обходить — потеряешь время. ATT payload 20 байт хватает для всех опкодов.
- **Single-central.** Один BLE-центр одновременно. Закрывать FTLAB-app перед стартом шлюза, либо рассматривать ESP как «эксклюзивный gateway» (телефон не подключать).
- **Максимум 3 `ble_client`** на одной плате (ограничение Bluedroid-стека). Если в доме 4+ RadonEye — поднимать 2+ шлюза.
- **0x53 = config-WRITE** входит в whitelist, но голый — обнуляет конфиг. НИКОГДА не слать в автоматическом опросе, только через ручной payload с трассой официального приложения.
- **0xA0..0xCF вне whitelist = DFU mode.** Восстановление — только разрядка батареек ~30 с.

---

## Источники реверса

См. [references/sources.md](../references/sources.md) и
[references/plus2_protocol.md](../references/plus2_protocol.md). Основные:

- live-чтение через Bluetooth ПК (Python bleak), 2026-06-15
- Android HCI-snoop трасса официального приложения RadonEye+² (FTLAB), 2026-06-15
- открытый код https://github.com/EtoTen/radonreader (RD200 V1)
- ZheTian Lab / GitHub — RD200 V2 + Plus2 опкоды
