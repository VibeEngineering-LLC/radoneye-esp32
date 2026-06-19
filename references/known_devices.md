# Known devices — что работает по V1, что нет

## Совместимость по V1 BLE protocol (этого скилла)

| Прибор | Внутренняя модель | Прошивка | V1 совместимость | Заметки |
|---|---|---|---|---|
| RadonEye **Plus2** | `RD200PLUS` | rev 2026-06 (firmware date в advertising) | ✓ работает | Verified live в сессии 2026-06-07. `0x10` молчит, `0x50`+`0x51` работают, `0x51` payload_len=`0x12` (extended) |
| RadonEye **RD200** (classic) | `RD200` | до 2022 | ✓ работает | По sormy KNOWLEDGE_V1.md. `0x51` payload_len=`0x0E` (стандарт) |
| RadonEye **Plus3** | `RD200P3` | ? | ✓ должно работать | Заявлено sormy как V1-совместимый, не верифицировано в этом скилле |
| RadonEye **RD200P** (early Plus) | `RD200P` | ? | ⚠ `?` у sormy | maintainer не уверен. Попробовать `0x50`+`0x51`, не пробовать другие опкоды |
| Old RadonEye (без BLE) | — | — | ✗ нет BLE | — |
| ESP32-based V2 firmware | — | — | ✗ V2 ПРОТОКОЛ | Другие UUID, другие команды. См. sormy `KNOWLEDGE_V2.md` |

## Как опознать прибор перед подключением

Через `bleak` scan:

```python
from bleak import BleakScanner
async def find():
    for d in await BleakScanner.discover(timeout=10.0):
        if d.name and ('FR:R' in (d.name or '') or 'RadonEye' in (d.name or '')):
            print(f"{d.address}  name={d.name}  rssi={d.rssi}")
```

Имена в advertising:
- `FR:R20:SN<serial>` — Plus2/Plus3 семейство
- `RD200N<serial>` — RD200 classic
- `RD200Px` — Plus
- Если имени нет вообще, но advertising UUID = `00001523-...` — это V1.
- Если advertising UUID = `0000ffe0-...` (HM-10 модуль) — это V2.

## Серийник из advertising

В Plus2 семействе серийник зашит прямо в имя:

```
"FR:R20:SN<digits>"
                ^^^^^^^^  → serial "PD<digits>" (P + date-coded)
```

Не нужно слать `0xA4` — серийник уже виден до подключения.

## Mode индикаторы (по поведению)

| Состояние | BLE advertising | Что делать |
|---|---|---|
| Нормальный | имя `FR:R20:SN...`, advertising 1-2 раза/сек | подключаться |
| DFU mode | имя меняется на `DfuTarg` или подобное, fast advertising | **НЕ подключаться нашим скриптом** — это recovery mode. Нужна Nordic nRF Connect для возврата прошивки или power-cycle прибором (вынуть батарейки на 30 сек). |
| Pairing-only | advertising без service UUID | требует pairing в системных Bluetooth-настройках |

## Случай 2026-06-07 — DFU recovery

В Phase 3 при probe опкодов в диапазоне `0xA0..0xCF` прибор перешёл в DFU
mode (advertising имя сменилось, прибор пропал из списка нормальных устройств).
Восстановлено через **power cycle** (вытаскивание батареек на ~30
секунд). История замеров **сохранилась** через power cycle (9600 точек × 1 час
= 13 месяцев — всё на месте после возврата).

Это материальный риск, не теоретический. Whitelist опкодов в `SKILL.md` —
не paranoid, а взят из живого инцидента.
