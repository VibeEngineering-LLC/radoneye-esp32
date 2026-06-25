# Temperature & humidity — почему нет публичного опкода

> ⚠ **SUPERSEDED (2026-06-20).** Этот документ — историческая фиксация состояния
> на 2026-06-07: тогда temp/hum выглядели «не в кадре 0x51», а байты `[12:16]`
> кадра 0x51 принимались за `peak f32`. **Это верно только для V1-протокола
> (RD200P)**. На Plus2 кадр 0x51 короче (≥0x12) и **temp/hum живут именно
> в нём**: `[12]` = humidity `byte & 0x7F` %, `[13]` = temperature °C
> (подтверждено живым дисплеем 46% / 24…24.5 °C, см.
> [`plus2_protocol.md` §6](plus2_protocol.md)). Прошивка C3-шлюза
> (`firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml`) уже работает по §6.
>
> Считайте всё ниже **методическим логом RE-сессии 2026-06-07**, не
> референсом по протоколу. Для производственных решений — `plus2_protocol.md`.

## TL;DR (исторический, 2026-06-07)

**На момент 2026-06-07** опкод/поле для чтения температуры и влажности на
RadonEye Plus2 / RD200P / Plus3 публично не задокументирован ни в одном из 7
живых open-source репо. Прибор сам датчики имеет и показывает их в FTLAB
Connect, но как именно приложение их получает по BLE — закрыто. Не угадывать.
Не пробовать случайные опкоды (это уже привело к DFU mode в сессии 2026-06-07).

**Update 2026-06-20:** загадка решена для Plus2 — см. `plus2_protocol.md §6`.
Temp/hum на Plus2 публикуются в том же кадре 0x51 в байтах [12]/[13].

Единственный надёжный путь — **захват HCI Bluetooth snoop log на Android**
во время штатной работы официального приложения, расшифровка `.btsnoop` →
точный опкод и offset. iPhone HCI snoop не предоставляет.

## Что проверено (исчерпывающий обзор, 2026-06-07)

Sub-agent research (`aa238afe4d3e58d1f`, 489 s, 41 tool uses):

| Источник | Что искали | Результат |
|---|---|---|
| sormy/radoneye | KNOWLEDGE_V1.md, KNOWLEDGE_V2.md | RD200P/P2 явно помечены `?` — протокол не известен maintainer'у |
| jdeath/rd200v2 | parser.py, SensorEntityDescription | UI-поля temperature/humidity/pressure ЕСТЬ в коде, но parser их НИКОГДА не заполняет — мёртвые placeholder'ы |
| lopsided98/radoneye-ble | весь код | нет temp/hum референсов |
| mangelajo/radoneye | весь код | нет |
| AntoineLah/RadonEye_Aranet | весь код | **единственный кандидат** — претендует читать temp/hum из `0x51` байтов [12], [13]. **Проверка против sormy fixture**: эти байты — float32 peak_radon. На fixture `50 b1 0c 40` → 2.198 pCi/L peak. AntoineLah даёт humidity=80, temperature=177.5°C. Мусор. Автор не валидировал. |
| aaronjauf/radoneye-v3 | V3 firmware | другая структура, неприменимо |
| sormy-reader | весь код | нет |
| HA core (полным клоном) | компонент radoneye_ble | компонент отсутствует |
| GitHub Issues+PRs sormy/jdeath | поиск «temperature», «humidity», «temp», «hum» | НИ ОДНОГО PR/issue про это |
| PyPI registry | поиск по «radoneye» | нет официального SDK |

## Live verification against ground truth

При известных значениях из FTLAB Connect (temp=24.5°C, hum=37%) **ни одна
byte-позиция** во frame `0x51 12 01 00 21 00 00 00 b1 08 08 00 a5 18 1a 06 07 0d 0f 30`
не декодируется в эти числа:

- `byte 8 = 0xB1 = 177` — не 24.5, не 37
- `bytes 8-9 LE u16 = 0x08B1 = 2225` → /100 = 22.25 (ballpark, но не 24.5)
- `bytes 10-11 LE u16 = 0x0008 = 8`
- `byte 17 = 0x0D = 13`, `byte 18 = 0x0F = 15`
- humidity 37 = `0x25` — нигде во frame нет байта `0x25`
- temperature 24.5 × {1, 2, 10, 100} = {24.5, 49, 245, 2450} → `0x18`, `0x31`,
  `0xF5`, `0x0992` — нигде во frame не наблюдаются

Гипотезы про fixed-point /16, half-degree, signed offset — тоже не сходятся.
Вывод: temp/hum **не в frame `0x51`**.

## Anti-hallucination case study (учебный)

В этой же сессии:
1. Ollama (qwen3-coder:30b) на вопрос «sormy документирует humidity?» —
   ответил «да, byte 12 of 0x51».
2. Sub-agent перед использованием прогнал точечный `grep -c humidity`
   против `KNOWLEDGE_V1.md` → 0 hits, опровергнуто.
3. AntoineLah'овский код, который мог бы «подтвердить» это, на проверку
   против sormy fixture дал мусор → отклонён.

Это иллюстрирует **правило verify-by-fact**: Ollama-claim и одиночное
open-source совпадение — это сырьё, не истина. Валидируй точечным grep
против первичного источника.

## Как получить опкод правильно — Android HCI snoop

1. Android-телефон, **Developer Options** включены.
2. **Enable Bluetooth HCI snoop log** в Developer Options. Перезагрузить
   Bluetooth.
3. Установить официальное приложение **«RadonEye» от Ecosense/FTLAB** из
   Google Play (соответствует iOS-приложению FTLAB Connect).
4. Соединиться с прибором, дать приложению прочитать temp/humidity один-два
   раза.
5. Достать `btsnoop_hci.log`:
   - либо `adb bugreport` (полный архив, snoop внутри),
   - либо напрямую `/sdcard/btsnoop_hci.log` через `adb pull` (если
     accessibility разрешает).
6. Открыть `.btsnoop` в Wireshark (display filter: `bthci_acl`). Найти
   write-команды от приложения к UUID `00001524-...` — это и есть опкод.
   Ответы по UUID `00001525-...` — frames с temp/hum полями.
7. Сопоставить байты с известным temp/hum (которое ты видел на экране
   приложения) → точный offset.

Это занимает **5-10 минут ручной работы**, даёт 100% надёжный
mapping и снимает все домыслы.

## До тех пор — рабочий обходной путь

Снимаем по BLE: radon (current/day/month/peak/uptime/counts) — это
надёжно работает.

Temp/humidity — параллельно смотрим в **FTLAB Connect** на телефоне.
Эти данные одинаковы в обоих каналах (приложение читает их с того же
прибора), просто разными способами доставки.
