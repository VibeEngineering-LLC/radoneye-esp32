---
name: radoneye-ble
description: Read radon, peak, uptime, and counts from a RadonEye Plus2 / RD200P / Plus3 detector over BLE (V1 protocol). Use whenever the user wants to connect to a RadonEye device by MAC, take a snapshot, or set up periodic radon logging — for example "сними показания радона", "подключись к RadonEye по BLE", "поллинг радона раз в час", "decode RadonEye frame", "read RD200P over Bluetooth". Ships a ready production script and a fact-cited V1 protocol reference. Do NOT use this skill for the V2 ESP32 firmware or for temperature/humidity readout (not in V1 protocol — see KNOWN-UNKNOWNS).
---

# RadonEye BLE — снимаем данные с прибора без угадайки

Скилл закрывает одну задачу: **подключиться к RadonEye Plus2 / RD200P / Plus3 по
Bluetooth LE, прочитать радон + uptime + peak + counts, записать в JSONL**.
Использует только known-safe V1-опкоды, документированные в `sormy/radoneye`
KNOWLEDGE_V1.md и сверенные на живом приборе a RD200PLUS device (Plus2 family) в сессии 2026-06-07.

> **Если прибор V2 (ESP32 firmware с другим набором UUID)** — этот скилл НЕ
> подходит. У V2 другие сервисные UUID и другая команда (`RD200`). См.
> `sormy/radoneye/KNOWLEDGE_V2.md` отдельно.

## Когда срабатывать

- Оператор просит снять текущие показания радона с известного MAC.
- Нужно запустить периодический мониторинг (`--watch N --interval S`).
- Нужно расшифровать сырой frame от RadonEye (`51 ...` / `50 ...` hex) — см.
  `references/frame_layouts.md`.
- Оператор хочет понять, безопасно ли пробовать новый опкод — см.
  «Anti-patterns» ниже.

НЕ срабатывать:
- Температура / влажность (см. KNOWN-UNKNOWNS — опкод не документирован).
- V2-устройства.
- История замеров (`0xE8/0xE9` count+data) — отдельная задача, не покрыта.

## Быстрый старт

```bash
# Один снимок (печать + append в jsonl)
python scripts/radon_snapshot.py

# 24 снимка раз в час (сутки логирования)
python scripts/radon_snapshot.py --watch 24 --interval 3600
```

Перед запуском подставь свой `MAC` в верх скрипта или передай через
переменную окружения `RADONEYE_MAC`.

**Конкуренция за central:** BLE-устройство держит ровно одного central'а.
Если к прибору подключено iPhone/Android-приложение FTLAB/Ecosense — наш
скрипт получит `not connected`. Отключи приложение (BT off на телефоне или
выход из приложения) перед запуском.

## Что мы читаем (V1 протокол)

| Опкод | Поле | Точность | Источник |
|---|---|---|---|
| `0x50` cur f32 LE @ bytes 2..6 | current radon | pCi/L | sormy KNOWLEDGE_V1.md |
| `0x50` day_avg f32 LE @ 6..10 | day average | pCi/L | sormy |
| `0x50` month_avg f32 LE @ 10..14 | month average | pCi/L | sormy |
| `0x50` cur_count u16 LE @ 14..16 | sample counter | counts | sormy |
| `0x50` prev_count u16 LE @ 16..18 | previous counter | counts | sormy |
| `0x51` uptime u16 LE @ 4..6 | uptime minutes | min | sormy + verified |
| `0x51` peak f32 LE @ 12..16 | peak radon | pCi/L | sormy + verified |
| `0x51` byte @ 19 | seconds-within-minute | sec | verified live |

Все frame'ы доезжают по characteristic `0x1525`
(`00001525-1212-efde-1523-785feabcd123`). Команды пишутся в `0x1524`
(`00001524-...`). Полная таблица — в `references/v1_protocol.md`.

## KNOWN-UNKNOWNS — не угадывать!

| Что | Статус | Почему не делаем |
|---|---|---|
| `0x10` FULL_STATUS | На RD200PLUS rev 2026-06 **молчит** (0 notifies) — на других моделях работает | Не критично — `0x50+0x51` дают всё нужное |
| Temperature / Humidity | **Опкод не задокументирован публично** ни в одном из 7 публичных репо (sormy, jdeath, lopsided98, mangelajo, AntoineLah, aaronjauf, sormy-reader) | Единственный путь — HCI snoop с Android. См. `references/temp_humidity_research.md` |
| История замеров `0xE8/0xE9` | В V1 doc описано, но требует burst-handling | Отдельная задача, не в этом скилле |
| Serial / Model / FW via `0xA4/0xA6/0xA8/0xAF` | На RD200PLUS rev 2026-06 силент на direct write (приходят только в составе ответа `0x10`) | Серийник и модель уже известны из advertising-данных |

## Anti-patterns — НЕ делать никогда

1. **Не пробовать опкоды вне whitelist `{0x10, 0x50, 0x51, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`.**
   В сессии 2026-06-07 probe в диапазоне `0xA0..0xCF` перевёл живой прибор в
   **DFU mode** — восстановление потребовало вытащить батарейки. Это не теоретический
   риск, это материальный инцидент.
2. **Не доверять «нашёл в одном репо без cross-check»**. `AntoineLah/RadonEye_Aranet`
   парсит temp/hum из `0x51` байтов 12/13 — но это байты `peak_pCi_L` float32 по
   sormy. На реальных данных это даёт мусор (humidity=80%, temperature=177.5°C).
3. **Не верить Ollama-ответу «опкод X документирует Y» без точечного `grep -c`
   против источника.** В этой сессии Ollama выдала галлюцинацию «sormy documents
   humidity at byte 12» — провалидировали по `KNOWLEDGE_V1.md`, отклонили.
4. **Не держать BLE-сессию открытой долго, если пользователь хочет работать с
   приложением.** Один central — одно подключение. Закрывать клиента после
   снапшота.

## Архитектура скрипта (краткая)

```python
async with BleakClient(MAC, timeout=15.0) as client:
    await client.start_notify(NOTIFY_1525, handler)
    await client.start_notify(NOTIFY_1526, handler)  # обычно молчит, но подписываемся на всякий
    await asyncio.sleep(0.3)                          # CCCD settle
    await client.write_gatt_char(CMD_CHAR, bytes([0x50]), response=False)
    await asyncio.sleep(1.5)                          # frame arrives ~30-50ms
    await client.write_gatt_char(CMD_CHAR, bytes([0x51]), response=False)
    await asyncio.sleep(1.5)
# decode bytes per references/frame_layouts.md
```

## Файлы в скилле

- `scripts/radon_snapshot.py` — production-ready, передан как есть из живого
  rig 2026-06-07. Без зависимостей кроме `bleak`.
- `references/v1_protocol.md` — полная таблица V1 опкодов + UUID + serial decoding.
- `references/frame_layouts.md` — byte-by-byte layout `0x50` и `0x51` frames с
  CHANGED/STABLE classification из live diff session.
- `references/temp_humidity_research.md` — почему НЕТ публично известного опкода
  temp/hum и как его получить (Android HCI snoop).
- `references/known_devices.md` — какие модели работают по этому V1-протоколу,
  какие — нет.
