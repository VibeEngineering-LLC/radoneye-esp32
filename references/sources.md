# RadonEye RD200 — реестр источников протокола (provenance)

Реестр всех внешних источников, использованных при реверсе BLE-протокола
RadonEye RD200 / RD200 V2 / RD200PLUS (Plus2). Каждый источник —
с URL, описанием, лицензией и статусом фиксации в скилле.

Дата последнего обновления реестра: **2026-06-15**.

---

## 1. sormy/radoneye — ГЛАВНЫЙ источник истины

- **URL**: https://github.com/sormy/radoneye
- **Knowledge V1**: https://github.com/sormy/radoneye/blob/main/KNOWLEDGE_V1.md
- **Knowledge V2**: https://github.com/sormy/radoneye/blob/main/KNOWLEDGE_V2.md
- **Что**: наиболее полная reverse-engineering документация протокола V1 и V2,
  с опкодами, frame layouts, отличиями ревизий.
- **Используется в**: [v1_protocol.md](v1_protocol.md) (источник истины V1),
  [v2_protocol.md](v2_protocol.md) (KNOWLEDGE_V2 → опкод 0x40, frame layout,
  детекция версии по serial).
- **Статус фиксации**: ✅ зафиксировано 2026-06-15 (KNOWLEDGE_V1 + KNOWLEDGE_V2
  обработаны и разнесены по v1/v2_protocol.md).

## 2. romkey/esp32-arduino-ble-radoneye-rd200 — независимое подтверждение V1

- **URL**: https://github.com/romkey/esp32-arduino-ble-radoneye-rd200
- **Файлы**: `src/radon_eye.h`, `examples/simple/simple.ino`
- **Что**: Arduino-библиотека для ESP32, читает RD200 (классический V1) по BLE.
  Происхождение: авторы «wettermann» (Home Assistant форумы) + spikeygg,
  maintainer romkey. Лицензия — public domain.
- **Подтверждает**: service `1523`, write `1524`, notify `1525`, опкод `0x50`,
  float32 LE offsets 2/6/10 (current/day/month) + uint16 LE offsets 14/16
  (pulse/pulse10). Совпадает byte-в-byte с нашим `scripts/radon_snapshot.py`.
- **Используется в**: [v1_protocol.md](v1_protocol.md) → секция «Независимое
  подтверждение — romkey».
- **Статус фиксации**: ✅ зафиксировано 2026-06-15.

## 3. jdeath/rd200v2 — протокол V2 (Home Assistant интеграция)

- **URL**: https://github.com/jdeath/rd200v2
- **Файлы**: `radon_RD200_V2.py`, `custom_components/rd200_ble/` (`parser.py`,
  `const.py`, `config_flow.py`, `manifest.json`)
- **Лицензия**: MIT.
- **Что**: HACS-интеграция для RD200 **V2**. Ключевое отличие формата: в V2
  `current/day/month` это **uint16 LE сразу в Bq/m³** (offsets 2/4/6), а НЕ
  float32 LE pCi/L как в V1. Опкод `0x40` отдаёт peak (`data[51:53]` uint16 LE
  Bq/m³) + model/firmware/serial; `0x51` — uptime minutes; `0x50` — radon +
  pulse counts. Adv-имя `FR:*` (FR:RU, FR:RE, FR:GI…). V1 = серийники `FR:R2`.
- **Verbatim** (из `radon_RD200_V2.py`): write `00001524-0000-1000-8000-00805f9b34fb`,
  notify `00001525-0000-1000-8000-00805f9b34fb` (стандартная BT-база), опкод
  `b"\x50"`, `struct.unpack('<H', data[2:4])` → uint16 LE Bq/m³, `/37` → pCi/L.
- **Используется в**: [v2_protocol.md](v2_protocol.md) → секция «Verbatim-
  подтверждение UUID и опкода (jdeath)» + таблица расхождений sormy/jdeath.
- **Статус фиксации**: ✅ зафиксировано 2026-06-15 (verbatim UUID + опкод
  подтверждены прямым чтением `radon_RD200_V2.py`).

## 4. sormy/radoneye-reader

- **URL**: https://github.com/sormy/radoneye-reader
- **Что**: Python CLI-toolset того же автора (sormy) — фактически предшественник/
  набор утилит того же семейства, что и `sormy/radoneye`. MIT, на базе `bleak`.
  Тестирован на **RD200N** (производство 2022/Q2). Утилиты:
  `radoneye-reader.py` (основной reader + MQTT/HA-discovery publish),
  `radoneye-scan.py` (поиск устройств), `radoneye-dumper.py` (debug-дамп сырых
  frame'ов), `radoneye-beeper.py` (управление beep — соответствует опкоду `0xA1`
  из V2-таблицы). Происхождение вдохновлено `ceandre/radonreader` +
  `EtoTen/radonreader` (поддерживали старые RD200).
- **Ценность**: `radoneye-dumper.py` — готовый инструмент снять сырые frame'ы с
  V2/V3-прибора, если понадобится сверить наш Plus2; `radoneye-beeper.py`
  подтверждает штатность опкода `0xA1` (beep) на V2.
- **Используется в**: [sources.md](sources.md) (этот реестр), упомянут в
  [v2_protocol.md](v2_protocol.md) как инструментарий снятия frame'ов.
- **Статус фиксации**: ✅ зафиксировано 2026-06-15 (назначение, утилиты,
  лицензия, целевой прибор RD200N записаны).

## 5. ESPHome issue #6304 — RadonEye в ESPHome

- **URL**: https://github.com/esphome/issues/issues/6304
- **Что**: GitHub-issue в трекере ESPHome. В ESPHome **есть нативный sensor-
  компонент** `platform: radon_eye_rd200` (работает поверх `ble_client`). Issue
  фиксирует **баг**: компонент `radon_eye_rd200` **не коннектится к RD200 V3**
  (firmware V3.0.1) — бесконечный «Connection in progress», тогда как
  Python-библиотека `sormy/radoneye` к тому же прибору читает данные успешно.
  Окружение: ESPHome 2024.9.2, ESP32 Wemos Mini D1. Фикса нет (issue открыт).
- **Следствие для нас**: для V1-приборов можно попробовать готовый
  `platform: radon_eye_rd200`; для V3 он не работает → нужен наш кастомный
  ble_client-парсинг (как для AtomFast). Объясняет, почему «просто взять
  ESPHome-компонент» — не универсальное решение.
- **Используется в**: [v2_protocol.md](v2_protocol.md) → секция «ESPHome
  нативный компонент `radon_eye_rd200` (из issue #6304)».
- **Статус фиксации**: ✅ зафиксировано 2026-06-15 (компонент, баг V3,
  следствие для единого шлюза записаны).

## 6. EtoTen/radonreader — таксономия поколений по adv-имени (handle-based)

- **URL**: https://github.com/EtoTen/radonreader
- **Файлы**: `radon_reader.py` (CLI v0.4.0 + MQTT/HA/EmonCMS publish),
  `radon_reader_by_handle.py` (детектор устройства + reader по **handle**, не UUID).
- **Лицензия**: не указана явно (public-style); на базе `bluepy` (Linux/BlueZ).
- **Что**: предшественник семейства radonreader (вдохновил `sormy/radoneye-reader`,
  см. #4). Ключевая ценность — **детекция поколения по префиксу adv-имени** и
  **запись опкода по сырому handle**, а не по UUID:
  | adv-имя | поколение | type | write handle | UUID write | формат ответа 0x50 |
  |---|---|---|---|---|---|
  | `FR:R2…` | RD200 **<2022** | 0 | `0x000b` | `00001524-1212-efde-1523-785feabcd123` | float32 LE pCi/L @ `data[2:6]` |
  | `FR:RU…` | RD200 **≥2022** | 1 | `0x002a` | `00001524-0000-1000-8000-00805f9b34fb` | uint16 LE Bq/m³ @ `data[2:4]`, pCi=Bq/37 |
- **Verbatim** (`radon_reader_by_handle.py`): `bGETValues = b"\x50"`; type1 →
  `intHandle = int.from_bytes(b'\x00\x2a',"big")`; type0 → `b'\x00\x0b'`;
  type1 parse `struct.unpack('<H', raw[2:4])[0]`, type0 `struct.unpack('<f', raw[2:6])[0]`.
  Образец сырого frame (.05 pCi/L): `50 0a 02 00 05 00 00 00 00 00 00 00`.
- **⚠️ КЛЮЧЕВОЙ вывод для НАШЕГО прибора**: наш Plus2 рекламируется как
  **`FR:PD<serial>`** (префикс `FR:PD`) — **НЕ совпадает ни с `FR:R2`, ни с
  `FR:RU`**. Значит EtoTen-таксономия наш прибор **не классифицирует**: Plus2 —
  **отдельное поколение** со своей GATT-картой (service `1523`, write `1524`,
  notify `1525`/`1526`, frame 20B float32 LE pCi/L) — ближе к V1-семейству по
  формату ответа, но с двумя notify-характеристиками. Таксономия EtoTen полезна
  как контраст: подтверждает, что разные RadonEye отличают write handle и формат
  ответа по поколению, и что префикс adv-имени — надёжный дискриминатор.
- **Используется в**: [sources.md](sources.md) (этот реестр); войдёт в
  `plus2_protocol.md` как обоснование «почему Plus2 — отдельное поколение».
- **Статус фиксации**: ✅ зафиксировано 2026-06-15 (таксономия поколений,
  handle/UUID/формат по типам, вывод о непринадлежности нашего `FR:PD`-прибора
  к EtoTen-классам записаны).

---

## Наши собственные данные (live verify)

- **Прибор**: RD200PLUS (Plus2 family), реальный MAC — приватный (в публичных
  артефактах маскируется на `AA:BB:CC:DD:EE:FF`).
- **Live-сверка**: сессия 2026-06-07 — опкоды `0x50`/`0x51` verified на живом
  приборе; декодер `scripts/radon_snapshot.py`.
- **Опкод-whitelist (HARD)**: `{0x10, 0x50, 0x51, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8,
  0xE9}`. Диапазон `0xA0..0xCF` вне whitelist → **DFU-RISK** (инцидент
  2026-06-07: probe перевёл прибор в DFU mode, восстановление — вынуть батарейки
  ~30 с).
- **Конверсия**: pCi/L × 37.0 = Bq/m³ (точно).
