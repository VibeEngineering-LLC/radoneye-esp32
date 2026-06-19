# INSTALL — RadonEye Plus2 → ESP32 → Home Assistant

> 🇬🇧 English version: [INSTALL.en.md](INSTALL.en.md)

Сборка и установка с нуля. Документ написан для клиента, который раньше не
работал с ESPHome.

Времязатраты: **~20–30 минут** (большая часть — ожидание скачивания
toolchain ESPHome при первой компиляции и первой OTA).

---

## 0. Что понадобится

### Физическое железо

Выбор одной из двух плат:

| Плата | Когда брать | Где купить (примерно) |
|---|---|---|
| **Seeed Studio XIAO ESP32-C3** ⭐ | Готовый production-шлюз для **одного** RadonEye Plus2. Mini-форм-фактор ≈ 22×18 мм, USB-C, ~$5. | Seeed/AliExpress «XIAO ESP32-C3», ~400 ₽ |
| **ESP32-DevKitC v4 (WROOM-32)** | Когда плата уже в руках, либо нужен старый baseline с поддержкой до 3 приборов. USB-microB. | Любой DIY-магазин, ~600 ₽ |

Плюс:
- USB-кабель (Type-C для XIAO C3, micro-USB для DevKitC v4) — желательно тот же, которым плата выходит из коробки (в OEM-пачках бывает «зарядный без data-линий», на такой `esphome upload` не увидит порт).
- Сам **RadonEye Plus2 (RD200PLUS)** — версия с BLE («FR:PD…» в advertising).
- 2.4 GHz Wi-Fi точка с известным паролем (5 GHz не поддерживается ни одной из плат).
- (Опционально) Home Assistant — для приёма сенсоров через ESPHome API.

### Софт

Любая из платформ:

- **Windows 10/11** — это эталонная инструкция, все примеры команд PowerShell.
- macOS / Linux — команды отличаются префиксом `sudo`, путём к `esphome`, и тем, что Python надо ставить через `brew`/`apt`. Логика та же.

---

## 1. Установить ESPHome (Python 3.10+)

ESPHome — Python-пакет. Под Windows проще всего через системный Python от
python.org (не через Microsoft Store — там Python sandboxed и `esphome.exe`
не виден из PATH).

```powershell
# 1.1. Скачать Python 3.10+ с https://www.python.org/downloads/
#      В инсталляторе включить "Add python.exe to PATH".

# 1.2. Поставить ESPHome:
python -m pip install --upgrade pip
python -m pip install esphome

# 1.3. Проверить:
esphome version
```

Если `esphome` не находится в PATH (типично на Windows при кириллице в
имени пользователя) — используй полный путь:

```
C:\Users\<твоё_имя>\AppData\Local\Programs\Python\Python312\Scripts\esphome.exe
```

(Дальше в инструкции — `esphome` как сокращение; подставляй полный путь, если PATH-путь не работает.)

---

## 2. Скачать скилл

```powershell
git clone https://github.com/VibeEngineering-LLC/radoneye-esp32.git
cd radoneye-esp32\firmware\
```

Если ты не работаешь с git — скачай ZIP с
[github.com/VibeEngineering-LLC/radoneye-esp32](https://github.com/VibeEngineering-LLC/radoneye-esp32),
распакуй, в PowerShell перейди в `radoneye-esp32-main\firmware\`.

Внутри `firmware/`:

```
firmware/
├── esp32-classic/         radon_ha_gateway.yaml        (baseline ESP32-DevKitC, arduino)
├── xiao-esp32-c3/         radon_ha_gateway_c3.yaml     (актуальная, XIAO ESP32-C3, arduino)
├── secrets.example.yaml   (общий шаблон секретов)
├── CHANGELOG.md
└── .gitignore
```

---

## 3. Создать `secrets.yaml`

В папке `firmware/`:

```powershell
Copy-Item secrets.example.yaml secrets.yaml
notepad secrets.yaml
```

Заполнить шесть полей:

| Поле | Что вписать |
|---|---|
| `wifi_ssid` | SSID домашней 2.4 GHz сети (UPPER/lower важно). |
| `wifi_password` | Пароль Wi-Fi. |
| `ap_password` | Любая строка ≥8 символов. Сюда будет проситься captive portal, если ESP не подключится к домашнему Wi-Fi. |
| `api_encryption_key` | Сгенерировать командой ниже — **base64 от 32 байт**, заканчивается на `==`. |
| `ota_password` | Любая длинная строка. Используется и как OTA-пароль, и как Web UI Basic Auth password. |
| `radon1_mac` | Можно оставить заглушкой `AA:BB:CC:DD:EE:FF` — реальный MAC подцепим через Web UI после первой загрузки. |

### Сгенерировать `api_encryption_key`

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Скопировать вывод полностью (включая `=`-знаки в конце) в `secrets.yaml`.

> **⚠ Внимание!** `api_encryption_key` ДОЛЖЕН быть валидным base64 от 32 байт.
> Если оставить placeholder `0000000000000000000000000000000000000000000==` или
> ввести произвольную строку — ESPHome упадёт на boot с `Invalid key format,
> please check it's using base64`. См. Troubleshooting раздел **0**.

### Сгенерировать сильный `ota_password`

```powershell
python -c "import secrets; print(secrets.token_urlsafe(18))"
```

---

## 4. Выбрать вариант — какую плату прошиваем

### Вариант А — XIAO ESP32-C3 (рекомендованный, 2026-06-17)

**Чип:** ESP32-C3 single-core RISC-V 160 MHz.
**Flash:** 4 MB. **RAM:** 400 KB.
**USB:** Type-C (нативный CDC, **не** через CH340/CP210).
**Антенна:** встроенная PCB-антенна на плате.

**YAML:** `xiao-esp32-c3/radon_ha_gateway_c3.yaml`.

**Что внутри:** BLE-клиент к одному RadonEye Plus2, Web UI v3 + Basic Auth +
sorting_groups (5 групп: Sensors / BLE / Actions / Народмон / Diag),
ESPHome API encryption, watchdog WiFi, **Народмон-инфраструктура с
`restore_mode: ALWAYS_OFF`** (HARD).

### Вариант Б — ESP32-DevKitC v4 (baseline)

**Чип:** ESP32 classic dual-core 240 MHz.
**Flash:** 4 MB. **RAM:** 520 KB.
**USB:** micro-USB через CH340C / CP210x (нужны драйверы Windows — установятся
автоматически при первом подключении).
**Антенна:** встроенная PCB-антенна на модуле WROOM-32.

**YAML:** `esp32-classic/radon_ha_gateway.yaml`.

**Что внутри:** базовая прошивка под ESP-IDF/arduino, BLE-сканер MAC в Web UI,
поддержка **до 3 приборов** (`radon1_mac` / `radon2_mac` / `radon3_mac` в одном
шлюзе), RE-режим (ручной hex viewer кадров для разработчика). Подробности —
[`CHANGELOG.md`](firmware/CHANGELOG.md).

---

## 5. Найти MAC RadonEye Plus2 (опционально)

Если ты не знаешь MAC — пропусти этот шаг, оставь `radon1_mac: "AA:BB:CC:DD:EE:FF"`
в `secrets.yaml`. Реальный MAC подцепим через Web UI после первой загрузки.

Если уже знаешь (например, из nRF Connect / приложения FTLAB) — впиши в `radon1_mac`
в формате UPPERCASE с двоеточиями, например `12:34:AB:CD:EF:00`.

---

## 6. Скомпилировать прошивку

PowerShell, в папке `firmware/`:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Вариант А (XIAO C3):
esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml

# Вариант Б (DevKitC v4):
esphome compile esp32-classic/radon_ha_gateway.yaml
```

> **Что произойдёт.** Первая компиляция скачает PlatformIO toolchain
> (~500 МБ) — может занять **5–15 минут** в зависимости от интернета.
> Последующие — ~60–90 секунд. На XIAO C3 итоговая прошивка занимает
> ~85 % Flash; на DevKitC — ~80 %.

Финальное сообщение `INFO Successfully compiled program.` — компиляция прошла.

---

## 7. Прошить (первый раз — через USB)

Подключи плату USB-кабелем. На Windows определи COM-порт:

```powershell
Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'CH340|CP210|FTDI|USB Serial|JTAG' }
```

XIAO C3 определяется как **"USB JTAG/serial debug unit"** или **"USB Serial Device"**
(нативный CDC, без CH340), номер порта — `COM<N>`.

```powershell
# Вариант А:
esphome upload xiao-esp32-c3/radon_ha_gateway_c3.yaml --device COM<N>

# Вариант Б:
esphome upload esp32-classic/radon_ha_gateway.yaml --device COM<N>
```

После `Successfully uploaded` плата ребутится. Прошивка прошла.

> **Важно про логи.** `esphome logs --device COM<N>` **запускать ЗАПРЕЩЕНО** —
> на XIAO C3 и DevKitC он переподключает USB и дёргает DTR/RTS, прибор
> «прыгает» и BLE-сессия рвётся каждые 5–10 секунд. Используй **OTA-логи**:
> `esphome logs xiao-esp32-c3/radon_ha_gateway_c3.yaml --device radon-gw.local`
> (после первой WiFi-сессии).

---

## 8. Первая загрузка → captive portal → WiFi

Если плата не подключилась к домашней Wi-Fi (новая прошивка, смена SSID,
captive timeout) — поднимет свою AP с именем:

- **C3**: `radon-gw Fallback`
- **DevKitC**: `radon-ha Fallback`

Пароль AP — то, что ты вписал в `ap_password`.

С телефона / ноутбука:

1. Подключиться к этой AP.
2. Если captive portal не открылся сам — перейти на `http://192.168.4.1/`.
3. В списке сетей выбрать домашнюю Wi-Fi 2.4 GHz, ввести пароль → **Save**.
4. ESP перезагрузится, через ~10 секунд подключится к домашней Wi-Fi.

---

## 9. Web UI и привязка MAC RadonEye

В обычной сети, на ПК или телефоне:

- **C3:** [`http://radon-gw.local/`](http://radon-gw.local/)
- **DevKitC:** [`http://radon-ha-gateway.local/`](http://radon-ha-gateway.local/)

Если `.local` не резолвится (бывает на корпоративных DNS / некоторых
роутерах без mDNS) — найди IP в админке роутера по MAC платы и открой
`http://<IP>/`.

Login/Password Basic Auth:
- **C3:** `radon` / `<ota_password>`
- **DevKitC:** `admin` / `<ota_password>`

В Web UI:

1. Группа **«Поиск BLE»** → кнопка **«Запустить скан 30 с»**.
2. В списке результатов найти строку `FR:PD<серийник>` — это и есть твой RadonEye Plus2.
3. Скопировать MAC.
4. Вставить в поле **«MAC Radon 1»**.
5. Нажать **«Применить MAC и перезагрузить»**.

После перезагрузки в группе **«Sensors»** появятся:
- Радон Bq/m³ (мгновенный, обновляется раз в 10 минут)
- Peak (максимум за всё время в приборе)
- Count (номер замера от старта)
- Температура из истории
- Скользящие средние час/день

---

## 10. Подключить к Home Assistant

В Home Assistant:

1. **Settings → Devices & Services → Add Integration → ESPHome**.
2. Host: `radon-gw.local` (C3) или `radon-ha-gateway.local` (DevKitC), либо IP.
3. Encryption key: тот же `api_encryption_key`, что в `secrets.yaml`.
4. **Submit** → подождать «Discovered new device».
5. Назначить **Area** (например, «Спальня»).

Все сенсоры появятся автоматически:
`sensor.radon_instant_bq_m3`, `sensor.radon_peak`, `sensor.radon_count`,
`sensor.radon_temperature_c`, `sensor.radon_avg_hour`, `sensor.radon_avg_day`,
`binary_sensor.radon_ble_connected`, `sensor.radon_rssi`, и др.

---

## 11. Готовый промпт Claude Code (для следующей сборки)

Если ты используешь Claude Code (claude.ai/code) — копируй этот промпт целиком,
подставив свои данные:

```
Помоги мне поднять RadonEye → Home Assistant шлюз на ESP32.

Железо:
- Плата: XIAO ESP32-C3  (или ESP32-DevKitC v4)
- Прибор: RadonEye Plus2 (RD200PLUS), MAC ещё не знаю — подцепим через Web UI

Что у меня уже сделано:
- Python 3.12 + ESPHome установлены, "esphome version" работает.
- Скилл скачан в C:\Users\<имя>\claude-skills\radoneye-esp32\

Что нужно:
1. Помоги создать secrets.yaml на основе secrets.example.yaml. Сгенерируй:
   - api_encryption_key (base64, 32 байта)
   - ota_password (>=18 символов)
2. Скомпилировать xiao-esp32-c3/radon_ha_gateway_c3.yaml (или
   esp32-classic/radon_ha_gateway.yaml).
3. Найти COM-порт, прошить.
4. Объяснить, как через captive portal задать Wi-Fi.
5. Объяснить, как через Web UI ESP найти MAC прибора и привязать.
```

---

## Troubleshooting (частые ошибки установки)

### 0. `Invalid key format, please check it's using base64` (САМАЯ ЧАСТАЯ)

**Симптом.** Boot ESP подвисает, в UART/OTA-логе циклически:
```
[E][api]: Invalid key format, please check it's using base64
[E][api]: Initialization failed
```

**Корень.** `api_encryption_key` в `secrets.yaml` не является валидным base64-кодированием
32 случайных байт. Самая частая причина — оставлен placeholder
`0000000000000000000000000000000000000000000==` (он 32-байтовый, НО все нули —
ESPHome 2025.8+ это считает невалидным).

**Решение.** Сгенерируй настоящий ключ:

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Скопируй вывод полностью (включая `==` в конце) в `secrets.yaml`, поле
`api_encryption_key`. Перекомпилируй (`esphome compile …`) — ESPHome пересоберёт
прошивку под новый ключ. Залей повторно. В Home Assistant в интеграции — ввести
этот же ключ.

### 1. Плата не определяется как COM-порт

**Симптом.** `Get-CimInstance Win32_PnPEntity | Where { $_.Name -match 'CH340|CP210|JTAG|USB Serial' }` ничего не показывает.

**Решение.**
- USB-кабель без data-линий (только зарядка) — частая болезнь зарядных шнуров. Поменять.
- На DevKitC: установить драйвер CH340/CP210x (`https://www.wch.cn/downloads/CH341SER_EXE.html` для CH340C). После установки переподключить плату.
- На XIAO C3: должно работать out-of-the-box (нативный CDC). Если нет — обновить Windows до build ≥ 19041, установить «Universal Serial Bus controllers → USB Composite Device» драйвер вручную.

### 2. `esphome compile` падает с `UnicodeDecodeError`

**Симптом.**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd0 in position …
```

**Корень.** Путь к secrets / YAML содержит кириллицу, а Python не получил
`PYTHONIOENCODING=utf-8`.

**Решение.** В PowerShell **перед каждой** `esphome` командой:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

В Bash (Git Bash):

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 esphome compile ...
```

### 3. `esphome upload`: «Failed to connect to ESP32»

**Симптом.** `esphome upload` показывает прогресс и срывается с timeout:
```
A fatal error occurred: Failed to connect to ESP32: Wrong boot mode detected (0x13)!
```

**Решение по платам.**
- **DevKitC v4:** прибор сам не входит в bootloader. На плате нажать-удержать `BOOT`, коротко нажать `EN`, отпустить `BOOT`. Повторить `esphome upload`.
- **XIAO ESP32-C3:** если USB-CDC не отвечает — короткое замыкание `GND ↔ BOOT pad` пока вставляешь USB. После flash сбросить плату коротким нажатием RESET.

### 4. После прошивки плата ребутится в цикле

**Симптом.** UART / OTA лог:
```
[E][component:182]: Component web_server cleared Warning flag
Boot loop detected after 3 attempts, entering safe mode
```

**Решение.**
- Если в логе перед reboot `[E][api]: Invalid key format` — см. Troubleshooting **0**.
- Если в логе `Guru Meditation Error: StoreProhibited` — баг или несовместимый ESPHome (использовать 2025.8.0+ как указано в `min_version`). Обновить: `python -m pip install --upgrade esphome`.

### 5. Web UI открывается, но карточек/групп нет

**Симптом.** `http://radon-gw.local/` отдаёт пустой HTML с заголовком, без sensor-плашек.

**Решение.**
- Браузер закэшировал старый bundle ESPHome. **Ctrl+Shift+R** (hard reload).
- Открыть DevTools (F12) → Console — посмотреть на ошибки JS. Если «Mixed Content blocked» — открыть Web UI явно по `http://`, не `https://`.

### 6. `BLE: RadonEye подключён = OFF` (после привязки MAC)

**Симптом.** В Web UI в группе «Sensors» Radon Bq/m³ показывает «—», в группе «BLE» состояние «не подключено».

**Причины (в порядке вероятности).**

1. **RadonEye занят телефоном.** Plus2 — **single-central**: пока в нём активна сессия с приложением FTLAB/Ecosense, ESP получает «refuse». Закрой приложение полностью (force-stop), подожди 30 секунд, нажми в Web UI «Переподключить».
2. **MAC введён с опечаткой.** Открой группу «Поиск BLE» → «Запустить скан 30 с» → сравни байты.
3. **Прибор не в Plus2-семействе.** Эта прошивка только для RD200PLUS (advertising префикс `FR:PD…`). RadonEye RD200 V1/V2 — другой протокол. См. README раздел «Какие модели RadonEye работают».
4. **Расстояние > 5 м или стена.** RSSI < −85 dBm — сессия рвётся каждые несколько секунд. В группе «BLE» виден RSSI; если < −75 dBm — переместить ESP ближе либо подключить внешнюю U.FL антенну (DevKitC-варианты с U.FL).

### 7. `WiFi: Auth Expired` каждые несколько секунд

**Симптом.** UART:
```
[W][wifi]: Auth Expired
[D][wifi]: Connecting…
…
[W][wifi]: Auth Expired
```

**Решение.**
- Проверить `wifi_password` — особенно если есть `$`, `#`, кавычки. В YAML `secrets.yaml` строки в двойных кавычках поддерживают escape, в одинарных — нет.
- Domestic router с **band steering** (одно SSID для 2.4 + 5 GHz): ESP32 пытается подцепиться к 5 GHz, не может, петля. Решение — выделить отдельный SSID 2.4 GHz only (без steering), или поставить `bssid:` в YAML вручную на 2.4 GHz BSSID.

### 8. `json:111: JSON document overflow` + пустой Web UI

**Симптом.** В UART/OTA-логе:
```
[E][web_server:198]: json:111: JSON document overflow
```

**Корень.** Debug Log панель в Web UI v3 подписана на `/events` SSE и
сериализует КАЖДОЕ лог-сообщение как отдельный JSON-event. На XIAO C3 с
включённым `web_server.log: true` это даёт near-OOM.

**Решение.** В YAML XIAO C3-варианта (`xiao-esp32-c3/radon_ha_gateway_c3.yaml`)
`log: true` оставлено как исключение для удобства отладки. Если на C3
пошли ребуты / `json:111` / OOM — поменять на `log: false`:

```yaml
web_server:
  version: 3
  port: 80
  log: false   # ← с true на false
```

Перекомпилировать, перезалить. Debug Log панель исчезнет из Web UI, но сенсоры,
sorting_groups и API останутся целы.

### 9. OTA не работает после смены пароля

**Симптом.** `esphome upload … --device radon-gw.local` падает:
```
ERROR Authentication failed
```

**Корень.** Web UI Basic Auth закэшировал старые credentials, а OTA-эндпоинт
использует те же `ota_password`. После замены `ota_password` в `secrets.yaml`
нужно либо:

- Прошить через USB (физическое подключение, `--device COM<N>`) хотя бы один раз с новым паролем — после этого OTA на этот пароль работает.
- ЛИБО прошить через старый OTA-пароль (если ещё помнишь), потом ребут — новый пароль вступит в силу.

⚠ В CLAUDE.md проекта прошито HARD-правило: «Web auth не менять между шагами одной IP» — иначе браузер закэширует старый auth и после OTA получит 401 без prompt. Это касается только web auth password = ota_password в текущих YAML.

### 10. Команды Claude Code не запускаются с правильной кодировкой (Windows)

**Симптом.** При выполнении PowerShell-команды с кириллицей в путях через
Claude Code — `UnicodeDecodeError` / абракадабра в выводе.

**Решение.** В PowerShell-инвоке оборачивай Python-скрипты и `esphome` так:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml
```

Для одиночной Bash-команды:

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml
```

### 11. ESP видит несколько `FR:PD…` устройств (не свой)

**Симптом.** В Web UI группе «Поиск BLE» — несколько `FR:PD<серийник>` (соседский RadonEye).

**Решение.**
- Сверить серийник: на приборе физически — в меню «Информация» (Plus2 показывает Serial).
- Если соседний прибор соседа — он в нашу прошивку не подцепится (single-central, занят соседским телефоном или просто отказывает чужому MAC).
- Однозначность достигается только указанием **конкретного MAC** в `radon1_mac` (BLE-сканер шлюза подключится только к этому).

---

## Связанные документы

- [README.md](README.md) — обзор скилла, BLE-протокол Plus2.
- [SKILL.md](SKILL.md) — полная база знаний для разработчика прошивки.
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — матрица совместимости плат и инциденты.
- [firmware/CHANGELOG.md](firmware/CHANGELOG.md) — история версий прошивки.
- [references/plus2_protocol.md](references/plus2_protocol.md) — реверс BLE-протокола.
