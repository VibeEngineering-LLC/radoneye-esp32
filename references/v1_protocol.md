# RadonEye V1 BLE protocol — reference

Источник истины: [`sormy/radoneye/KNOWLEDGE_V1.md`](https://github.com/sormy/radoneye/blob/main/KNOWLEDGE_V1.md)
+ сверка на живом приборе a RD200PLUS device (Plus2 family) в сессии 2026-06-07.

## Сервис и характеристики (GATT)

V1 использует **кастомный сервис**, НЕ generic Nordic UART:

| UUID | Роль | Direction |
|---|---|---|
| `00001523-1212-efde-1523-785feabcd123` | Service | — |
| `00001524-1212-efde-1523-785feabcd123` | Command (write-no-response) | central → device |
| `00001525-1212-efde-1523-785feabcd123` | Notify (primary) | device → central |
| `00001526-1212-efde-1523-785feabcd123` | Notify (secondary) | device → central — обычно тих |

**Подключение**: bleak `BleakClient(MAC)`, MTU 23 (стандарт). После
`connect()` ОБЯЗАТЕЛЬНО `start_notify` на оба UUID + 200-500 мс на CCCD-settle.

## Опкоды V1 (1 байт записи в Command CHAR)

| Opcode | Имя | Ответ | Статус verify |
|---|---|---|---|
| `0x10` | FULL_STATUS | burst из 6+ frames: 0x50, 0x51, 0xA4, 0xA6, 0xA8, 0xAF | На RD200PLUS rev 2026-06 — **молчит** (0 notifies). Известный V1-baseline вариант: работает на RD200 (классик). |
| `0x50` | RADON | один 20-byte frame `50 10 …` | ✓ VERIFIED on RD200PLUS |
| `0x51` | UPTIME+PEAK | один 20-byte frame `51 12 …` | ✓ VERIFIED on RD200PLUS (Plus2-extended payload_len=0x12, не 0x0E) |
| `0xA4` | SERIAL | ASCII string frame `A4 LL …` | На RD200PLUS rev 2026-06 — direct write молчит, приходит только в составе 0x10 burst |
| `0xA6` | SERIES | ASCII | См. 0xA4 |
| `0xA8` | MODEL NAME | ASCII | См. 0xA4 |
| `0xAF` | SW VERSION | ASCII | См. 0xA4 |
| `0xAC` | SETTINGS | сырой dump (нет публичного декодера) | Use with caution |
| `0xE8` | HISTORY count | u16 count of stored samples | Не покрыто в этом скилле |
| `0xE9` | HISTORY data | burst of samples | Не покрыто в этом скилле |
| `0xA0..0xCF` (вне whitelist) | UNKNOWN | ⚠ DFU-RISK | **НЕ ПРОБОВАТЬ.** В сессии 2026-06-07 probe здесь перевёл прибор в DFU mode. |

## Формат frame

Все frame'ы — фиксированно **20 байт** (по MTU 23 минус headers).

```
[0]   opcode_echo   — повторяет посланный опкод
[1]   payload_len   — длина полезной нагрузки (0x10=16 для radon, 0x12=18 для Plus2-uptime, и т.п.)
[2..2+payload_len]  — данные
[remaining bytes]   — trailer (может быть dynamic — счётчик секунд, padding, CRC; не end-marker)
```

**Важное наблюдение из live diff (Phase 9, 2026-06-07)**: trailer
(`byte 19` в `0x51`) ведёт себя как **seconds counter** — растёт +1 в
секунду с rollover внутри минуты. Это значит `0x51` несёт uptime с точностью
до **секунды**: minutes в bytes 4-5 (u16 LE), seconds в byte 19 (u8).

## Live decoding examples

**0x50 (RADON)** — из Phase 9 при низком радоне:
```
hex:   50 10 00000000 00000000 00000000 0100 0000 0f38
        ^  ^  ^current  ^day     ^month    ^c1  ^c2  ^trailer
bytes:  0  1  2-5       6-9      10-13    14-15 16-17 18-19

current = struct.unpack('<f', b[2:6])[0]   → 0.0 pCi/L
day_avg = struct.unpack('<f', b[6:10])[0]  → 0.0 pCi/L
month   = struct.unpack('<f', b[10:14])[0] → 0.0 pCi/L
c1      = struct.unpack('<H', b[14:16])[0] → 1   (sample counter)
c2      = struct.unpack('<H', b[16:18])[0] → 0   (prev counter)
```

**0x51 (UPTIME+PEAK)** — из Phase 9:
```
hex:   51 12 0100 2200 0000 b1080800 a5181a06 070d0f 38
        ^  ^   ?? ^upt ^?   ^?       ^peak    ^?     ^sec
bytes:  0  1  2-3 4-5  6-7  8-11     12-15    16-18  19

uptime_min = struct.unpack('<H', b[4:6])[0]   → 34   (minutes)
peak       = struct.unpack('<f', b[12:16])[0] → 0.0  (pCi/L)
sec_byte   = b[19]                            → 56   (seconds — live verified)
```

Поля bytes 8-11 (`b1 08 08 00` в одном замере, `28 09 08 00` в другом) и
bytes 16-18 (`07 0d 0f`) — неизвестные. Меняются на медленных таймерах,
не сопоставляются с известным temp/hum от приложения. См.
`temp_humidity_research.md`.

## Конверсии

- **pCi/L → Bq/m³**: умножить на **37.0** (точное значение, не аппроксимация).
- **Bq/m³ → pCi/L**: разделить на 37.0.
- WHO action level: **2.7 pCi/L** (≈ 100 Bq/m³).
- EPA action level: **4.0 pCi/L** (≈ 148 Bq/m³).

## Корректное закрытие сессии

После последнего write — подождать минимум 1 секунду на доставку финального
notify, потом `stop_notify` и выйти из `async with`. Не оставлять
client.disconnect() висеть — bleak в Windows иногда оставляет zombi-handle.

## Независимое подтверждение — romkey/esp32-arduino-ble-radoneye-rd200 (зафиксировано 2026-06-15)

Источник: [`romkey/esp32-arduino-ble-radoneye-rd200`](https://github.com/romkey/esp32-arduino-ble-radoneye-rd200)
(`src/radon_eye.h`, `examples/simple/simple.ino`). Arduino-библиотека для
ESP32, читает **RD200 (классический V1)** по BLE. Происхождение кода:
авторы «wettermann» (Home Assistant форумы) + spikeygg (GitHub), maintainer
romkey. Лицензия — public domain (явного copyright-нотиса нет).
**Дисклеймер автора (цитата ≤15 слов)**: *"the interface to the RD200 is not
documented or guaranteed to work"* — интерфейс недокументирован, может
поменяться без предупреждения.

**Ценность для скилла**: это **второй независимый источник** (помимо
`sormy/radoneye`), который verbatim воспроизводит наш V1-протокол service 1523.
Полностью совпадает с нашими UUID, опкодом 0x50 и offset'ами в
`scripts/radon_snapshot.py` → подтверждает корректность нашего декодера на
независимой кодовой базе.

### UUID (verbatim из `src/radon_eye.h`)

```cpp
static BLEUUID serviceUUID("00001523-1212-efde-1523-785feabcd123");
static BLEUUID charUUID  ("00001525-1212-efde-1523-785feabcd123"); // notify
static BLEUUID char24UUID("00001524-1212-efde-1523-785feabcd123"); // command/write
```

Совпадает с нашей GATT-таблицей: 1523 service, 1524 write, 1525 notify.

### Команда (verbatim)

```cpp
p2RemoteCharacteristic->writeValue(0x50);   // запись 1 байта 0x50 в char 1524
```

Подтверждает: **0x50 — безопасный опкод запроса текущих значений** (он в нашем
whitelist). romkey-библиотека использует ТОЛЬКО 0x50 (0x51 не трогает) и держит
постоянное соединение, «чтобы родное приложение не блокировалось» — это та же
single-central модель, что и у нас.

### Разбор notify-frame (verbatim, union-парсинг через `value[]`)

```cpp
union { char c[4]; uint32_t b; float f; } radonval;
union { char c[2]; uint16_t b; }          pulsval;

radonval.c[0..3] = value[2..5];   _radon_now   = radonval.f;  // float LE
radonval.c[0..3] = value[6..9];   _radon_day   = radonval.f;  // float LE
radonval.c[0..3] = value[10..13]; _radon_month = radonval.f;  // float LE
pulsval.c[0..1]  = value[14..15]; _pulse       = pulsval.b;   // uint16 LE
pulsval.c[0..1]  = value[16..17]; _pulse10     = pulsval.b;   // uint16 LE
```

**Сверка offset-в-offset с нашим `decode_0x50`** (полное совпадение):

| Поле (наше) | Поле (romkey) | Offset | Тип | Совпадение |
|---|---|---|---|---|
| `current` | `_radon_now` | `b[2:6]` | float32 LE | ✓ |
| `day_avg` | `_radon_day` | `b[6:10]` | float32 LE | ✓ |
| `month` | `_radon_month` | `b[10:14]` | float32 LE | ✓ |
| `c1` (sample counter) | `_pulse` | `b[14:16]` | uint16 LE | ✓ |
| `c2` (prev counter) | `_pulse10` | `b[16:18]` | uint16 LE | ✓ |

**Уточнение семантики counters**: romkey именует наши `c1`/`c2` как
`pulse` / `pulse10` — то есть это **счётчики импульсов детектора** (текущий и,
вероятно, накопительный за окно), а не абстрактные «sample counters». Это
уточняет интерпретацию bytes 14-17 frame'а 0x50.

**Расхождение в именовании (не в offset'ах)**: в `simple.ino` аксессоры
названы `radon_now()` / `radon_hour()` / `radon_day()`, тогда как сам разбор в
`.h` пишет `_radon_now`/`_radon_day`/`_radon_month`. Названия «hour»/«day»
смещены на одну позицию относительно внутренних полей — байтовые offset'ы
важнее имён, и они совпадают с нашими `current`/`day`/`month`. Единицы в коде
romkey не указаны явно (печатает `%.2f`) — наш скилл доопределяет: значения в
**pCi/L**, конверсия в Bq/m³ — ×37.0.
