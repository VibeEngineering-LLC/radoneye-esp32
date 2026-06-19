# RadonEye V2 / V3 BLE protocol — reference

> ⚠️ **V2/V3 — ДРУГОЙ протокол, чем V1.** Не путать с
> [v1_protocol.md](v1_protocol.md). Главный опкод, формат значений, единицы и
> даже полные UUID отличаются. Наш живой прибор RD200PLUS (Plus2) в сессии
> 2026-06-07 отвечал по **V1-семантике** (опкод `0x50`, float32 LE pCi/L) — см.
> «Какая версия у нашего прибора» внизу.

Источники истины:
- [`sormy/radoneye` KNOWLEDGE_V2.md](https://github.com/sormy/radoneye/blob/main/KNOWLEDGE_V2.md) — главный.
- [`jdeath/rd200v2`](https://github.com/jdeath/rd200v2) — HA-интеграция (альтернативная интерпретация).
- [ESPHome issue #6304](https://github.com/esphome/issues/issues/6304) — нативный компонент + баг V3.

Зафиксировано 2026-06-15.

## Сервис и характеристики (GATT) — V2/V3

V2/V3 использует **стандартную Bluetooth-SIG базу** UUID
(`-0000-1000-8000-00805f9b34fb`), а НЕ кастомную V1-базу
(`-1212-efde-1523-785feabcd123`). 16-битная часть (1523/1524/1525/1526) — та же.

| UUID (V2/V3) | Роль | Direction |
|---|---|---|
| `00001523-0000-1000-8000-00805f9b34fb` | Service | — |
| `00001524-0000-1000-8000-00805f9b34fb` | Command (write) | central → device |
| `00001525-0000-1000-8000-00805f9b34fb` | Status read/notify | device → central |
| `00001526-0000-1000-8000-00805f9b34fb` | History read | device → central |

## Опкоды V2/V3 (по sormy/KNOWLEDGE_V2)

| Opcode | Direction | Назначение |
|---|---|---|
| `0x40` | bidirectional | **Full status** request/response (главный — заменяет V1-шный 0x50) |
| `0x41` | bidirectional | History request/response |
| `0xA1` | outgoing | Beep (звуковой сигнал) |
| `0xA2` | outgoing | Set display unit (pCi/L ↔ Bq/m³) |
| `0xAA` | outgoing | Configure alarm |
| `0xAC` | incoming | Settings confirmation |

> ⚠️ В V1 диапазон `0xA0..0xCF` был DFU-RISK. В V2/V3 опкоды `0xA1/0xA2/0xAA/0xAC`
> документированы как штатные. **На нашем приборе (отвечает по V1!) их НЕ
> пробовать** — для нашего прибора действует V1 whitelist. V2-опкоды
> применимы только к подтверждённо-V2/V3 приборам.

## Frame 0x40 (Full status response) — byte layout по sormy

Значения — **uint16, little endian, в Bq/m³** (не float, не pCi/L):

| Offset (hex) | Поле | Тип | Единица |
|---|---|---|---|
| `0x1C` | Display unit | uint8 | 0x00=pCi/L, 0x01=Bq/m³ |
| `0x1E..0x1F` | Alarm threshold | uint16 LE | Bq/m³ |
| `0x21..0x22` | **Current radon** | uint16 LE | Bq/m³ |
| `0x23..0x24` | **Daily average** | uint16 LE | Bq/m³ |
| `0x25..0x26` | **Monthly average** | uint16 LE | Bq/m³ |
| `0x2B..0x2C` | Uptime | uint16 LE | минуты |
| `0x33..0x34` | **Peak radon** | uint16 LE | Bq/m³ |

## Детекция версии прибора (по serial, sormy)

| Версия | Формат serial | Где |
|---|---|---|
| **V2** | 6 байт: дата производства `YYMMDD` + 3-байтовая серия + 4-значный серийник | offset 0x02+ в status |
| **V3** | 12 байт ASCII, без date-префикса | offset 0x02+ |

Adv-имя (из jdeath): `FR:*` — `FR:RU`, `FR:RE`, `FR:GI` и т.п. V1-приборы —
серийники с префиксом `FR:R2`.

## Расхождение источников по «V2» (важно — две интерпретации)

| | sormy/KNOWLEDGE_V2 | jdeath/rd200v2 |
|---|---|---|
| Главный опкод status | `0x40` | `0x50` |
| Current radon offset | `0x21..0x22` | `2..4` (=0x02) |
| Day / Month offset | `0x23` / `0x25` | `4..6` / `6..8` |
| Тип значения | uint16 LE Bq/m³ | uint16 LE Bq/m³ |
| Peak | `0x33` в 0x40-frame | `data[51:53]` в **0x40**-frame |
| Pulse counts | — | `0x50` offsets 8/10 (pulse now / 10min) |

**Вывод**: jdeath и sormy частично описывают одно семейство, но
расходятся в том, какой опкод и какие offset'ы у «текущего радона». Вероятно
описывают **разные ревизии прошивки** RD200 V2. Оба сходятся в одном: в V2/V3
значения — **uint16 в Bq/m³**, а не float32 в pCi/L как V1. При работе с
реальным V2/V3-прибором — снять оба frame'а (0x40 и 0x50) и сверить, какой
опкод реально отвечает.

### Verbatim-подтверждение UUID и опкода (jdeath, зафиксировано 2026-06-15)

Из [`jdeath/rd200v2`](https://github.com/jdeath/rd200v2) → `radon_RD200_V2.py`
(MIT) — дословно:

```python
# UUID — стандартная Bluetooth-SIG база, НЕ кастомная V1-база:
CHAR_WRITE  = "00001524-0000-1000-8000-00805f9b34fb"   # command/write
CHAR_NOTIFY = "00001525-0000-1000-8000-00805f9b34fb"   # status/notify

write_value = b"\x50"                                   # опкод 0x50

RadonValueBQ  = struct.unpack('<H', data[2:4])[0]       # uint16 LE, СРАЗУ в Bq/m³
RadonValuePCi = (RadonValueBQ / 37)                     # конверсия в pCi/L
```

**Что это подтверждает (verbatim)**:
1. **UUID на стандартной BT-базе** `-0000-1000-8000-00805f9b34fb` (1524 write /
   1525 notify) — подтверждает таблицу GATT выше для V2/V3.
2. **Опкод `0x50`** в V2-варианте jdeath даёт **uint16 LE Bq/m³ в `data[2:4]`** —
   это ключевое отличие от V1, где тот же опкод `0x50` отдаёт **float32 LE pCi/L**
   в `b[2:6]`. Один и тот же байт опкода, РАЗНЫЙ формат payload между поколениями.
3. Конверсия **÷37** (обратная нашей V1-конверсии ×37) — арифметика та же,
   направление обратное, потому что прибор V2 уже хранит Bq/m³.

⚠ **Урок для живого реверса**: нельзя определить поколение прибора по одному
опкоду `0x50` — надо смотреть **длину и формат frame'а**. V1: 20 байт,
`50 10 …`, float32. V2 (jdeath): uint16 в `data[2:4]`. Наш Plus2 в 2026-06-07
ответил float32 → **V1**.

## ESPHome нативный компонент `radon_eye_rd200` (из issue #6304)

В ESPHome **есть встроенный sensor-компонент** для RadonEye:

```yaml
ble_client:
  - mac_address: AA:BB:CC:DD:EE:FF      # наш MAC замаскирован
    id: radon_eye_ble_id

sensor:
  - platform: radon_eye_rd200
    ble_client_id: radon_eye_ble_id
    update_interval: 5min
    radon:
      name: "Radon"
```

**Известный баг (issue #6304, открыт)**: компонент `radon_eye_rd200` **не
коннектится к RD200 V3** (firmware V3.0.1) — бесконечный «Connection in
progress», тогда как Python-библиотека `sormy/radoneye` к тому же прибору
читает данные успешно. ESPHome 2024.9.2, ESP32 Wemos Mini D1. Фикса на момент
фиксации нет.

**Следствие для нашего единого шлюза**: для V1-приборов можно попробовать
готовый `platform: radon_eye_rd200` вместо ручного ble_client-парсинга, но для
V3 он не работает — там нужен наш кастомный путь (как мы делаем для AtomFast).

## Какая версия у нашего прибора (RD200PLUS / Plus2)

- **Live-факт (сессия 2026-06-07)**: на опкод `0x50` прибор отвечал
  20-байтовым frame'ом `50 10 …`, где current/day/month декодировались как
  **float32 LE в pCi/L** (значения 0.0 при низком радоне), а `0x51` —
  uptime u16 @4 + peak f32 @12. Это **V1-семантика**, не V2/V3.
- **Открытый вопрос**: RD200PLUS адвертайзится как `FR:R…` (Plus2). По
  serial-формату sormy (6-байт YYMMDD у V2 / 12-байт ASCII у V3) нужно снять
  serial через `0xA4` (в составе `0x10`-burst) и классифицировать точно. Пока
  рабочая гипотеза — **Plus2 говорит на V1-варианте протокола** (подтверждено
  декодированием), а V2/V3-протокол этого reference относится к более новым
  ревизиям RD200.
- **Практика**: для нашего прибора используем **V1** ([v1_protocol.md](v1_protocol.md))
  и его опкод-whitelist. V2/V3-документ — для будущих/чужих приборов и для
  понимания, почему ESPHome-компонент может не подойти.
