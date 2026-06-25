# Known Issues & Hardware Compatibility — radoneye-esp32

> 🇬🇧 English version: [KNOWN_ISSUES.en.md](KNOWN_ISSUES.en.md)

Краткий справочник: какие платы реально проверены на RadonEye Plus2-шлюзе,
какие проблемы клиенты ловят чаще всего, и что с этим делать. Полная
техническая база знаний по BLE-протоколу — в [README.md](README.md) и
[references/plus2_protocol.md](references/plus2_protocol.md).

---

## 1. Матрица совместимости плат (hardware compatibility)

> **Дисклеймер.** Работа подтверждена только на платах со статусом ✅. Для
> всех остальных — **гарантий нет**. Если попробовал и получилось/не
> получилось — открой [issue](https://github.com/VibeEngineering-LLC/radoneye-esp32/issues),
> добавим в матрицу.

### ✅ Протестированы и рекомендованы

| Плата | Чип | Flash | PSRAM | Антенна | USB | YAML | Заметки |
|---|---|---|---|---|---|---|---|
| **Seeed Studio XIAO ESP32-C3** ⭐ | ESP32-C3 single-core RISC-V 160 MHz | 4 MB | — | PCB | Type-C (нативный CDC) | `xiao-esp32-c3/radon_ha_gateway_c3.yaml` (arduino + NimBLE) | **Рекомендованная плата.** ~22×18 мм, ~$5. Web UI sorting_groups (5 групп), Народмон-инфраструктура с `restore_mode: ALWAYS_OFF`. `web_server.log: true` оставлено намеренно (диагностика). |
| **ESP32-DevKitC v4 (WROOM-32)** | ESP32 classic dual-core 240 MHz | 4 MB | — | PCB | micro-USB через CH340C / CP210x | `esp32-classic/radon_ha_gateway.yaml` (arduino + Bluedroid) | Baseline. Поддерживает **до 3 приборов** (`radon1_mac` / `radon2_mac` / `radon3_mac`), RE-режим (ручной hex viewer кадров). Для одного прибора предпочтительнее XIAO C3 (меньше форм-фактор + USB-C). |

### ❌ НЕ работает / не подходит

| Плата | Причина |
|---|---|
| **ESP32-S2** | Нет BLE — физически не может быть BLE-шлюзом к RadonEye. |
| **ESP8266 (любой)** | Нет BLE. |

### ⚠ Не протестированы — на свой риск

| Плата | Ожидание |
|---|---|
| **ESP32-S3-DevKitC-1 N16R8** | Нет готового YAML под S3. Соседний скилл `atomfast-esp32` имеет работающий S3-baseline — портировать можно (поменять `board`, `variant`, `framework: esp-idf`, добавить `psram`), но не верифицировано на RadonEye. |
| **ESP32-C6 / H2** | BLE 5.0 есть, NimBLE-стек поддерживается, но YAML под них в скилле не написан. |
| **ESP32-C3 SuperMini** | Чип такой же, что у XIAO C3, но GPIO-маппинг (LED, BOOT pad) и Flash могут отличаться. Можно использовать `xiao-esp32-c3/radon_ha_gateway_c3.yaml` как стартовую точку — поменять `board: esp32-c3-devkitm-1` (если нужно), снять `web_server.log: true` (на SuperMini может не хватить heap). |
| **Безымянные ESP32-WROOM-32 клоны** | Обычно работает как DevKitC v4, но качество кварца / PSRAM / Wi-Fi PA непредсказуемо. Может ловить `WiFi Auth Expired` (см. Troubleshooting #7 в [INSTALL.md](INSTALL.md)). |

---

## 2. Рекомендации по выбору железа

1. **Покупаешь новую плату под продакшен** (один прибор RadonEye Plus2 на один шлюз): **Seeed Studio XIAO ESP32-C3**. Стабильна, USB-C, mini-форм-фактор, ~$5. Прошивка — `xiao-esp32-c3/radon_ha_gateway_c3.yaml`.
2. **Уже есть классический ESP32-DevKitC v4**: используй `esp32-classic/radon_ha_gateway.yaml`. Если в доме / на одном этаже несколько RadonEye — этот baseline поддерживает до 3 приборов одним шлюзом (`radon1_mac` / `radon2_mac` / `radon3_mac` в `secrets.yaml`).
3. **Нужен один шлюз на 4+ RadonEye**: ESPHome не масштабируется так — максимум **3 `ble_client`** на одной плате (ограничение Bluedroid-стека). Поставь два шлюза, у каждого свой `device_name` (например, `radon-gw-1` и `radon-gw-2`) и свои api/ota пароли.
4. **Что не брать**:
   - ESP32-S2 / ESP8266 (нет BLE).
   - Платы без явного маркировки чипа от продавца (часто оказываются ESP-12F с поддельной наклейкой ESP32).

---

## 3. Инциденты

### INC-RADON-UNIT — `0x53` обнуляет конфиг RadonEye (единицы + порог тревоги)

- **Дата:** 2026-06-07 (зафиксировано при реверсе протокола Plus2)
- **Severity:** прибор остаётся работоспособным, но настройки сбрасываются
- **Статус:** ✅ **Митигировано** в whitelist опкодов шлюза

**Симптом.** После случайного `WRITE 0x53 …` (без валидного payload) на
прибор:
- Дисплей переключается **Bq/m³ → pCi/L** (или наоборот).
- Порог тревоги обнуляется (был 200 Bq/m³ → стал 0 → прибор пищит на любых показаниях).
- Зуммер / ночной режим / температурная единица могут сброситься.

**Корень.** Опкод `0x53` — это config-WRITE прибора. Полный кадр выглядит так:

```
53 11 01 00 00 c8 00 01 00 00 00 00 00 00 00 00 00 00 00 00
         ↑          ↑↑↑↑↑↑    ↑
         порог      ?         код изменяемого поля
         c8 00 = 200 Bq/m³
```

`0x53` входит в whitelist (`{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61,
0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`) — прибор его «распознаёт». Но голый
`0x53` без структуры байт `[2:7]` обнуляет всё.

**Решение.**

- ✅ **Шлюз `radon_ha_gateway.yaml` / `_c3.yaml` опрашивает прибор ТОЛЬКО опкодами `{0x50, 0x51}`.** `0x53` не отправляется ни в одной автоматической последовательности.
- ⚠ Если разрабатываешь свой клиент (Python bleak / nRF Connect) — **никогда** не шли голый `53 ...` без payload. Полная байтовая карта — в [references/plus2_protocol.md](references/plus2_protocol.md) §6B.

**Восстановление после случайного 0x53.**

- Открыть приложение FTLAB / Ecosense на телефоне.
- Connect к прибору.
- Settings → выставить вручную: единицы Bq/m³, порог тревоги 200 (или своё значение), зуммер ON.
- Save & Reboot прибора.

### INC-RADON-DFU — опкоды в диапазоне `0xA0..0xCF` вне whitelist → DFU mode

- **Дата:** 2026-06-07 (live-инцидент при опкод-fuzzing'е)
- **Severity:** прибор временно недоступен, BLE прерывается
- **Статус:** ✅ **Митигировано** жёстким whitelist

**Симптом.** При попытке `WRITE` опкода **в диапазоне `0xA0..0xCF`, который не
входит в whitelist** (напр. `0xA0`, `0xA1`, `0xA2`, `0xA3`, `0xA5`, `0xA7`,
`0xA9`, `0xAA..0xAE`, `0xB0..0xCF`):
- Прибор переходит в **DFU (Device Firmware Update) mode**.
- BLE GATT-сессия обрывается, advertising полностью прекращается.
- На дисплее — ничего или иконка DFU.

**Восстановление.** **Только физическое:**

1. Открыть отсек батареек.
2. Вынуть **обе** батарейки.
3. Подождать **~30 секунд** (разрядка bypass-конденсаторов).
4. Вставить батарейки обратно.
5. Прибор перезагрузится в нормальном режиме.

**Решение.**

- ✅ **Канонический whitelist «распознаётся прибором»** (`plus2_protocol.md §5`) — 14 опкодов: `{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`. ⚠ «Распознаётся» ≠ «безопасно слать»: `0x53` подтверждённо обнуляет конфиг (INC-RADON-UNIT 2026-06-16).
- ✅ **Поллер шлюза (`poll_radon`) — литерал `[0x50]`/`[0x51]`**, других опкодов в эфир не отправляет (`firmware/esp32-classic/radon_ha_gateway.yaml:579-589`, `firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml:607-617`).
- ✅ **SAFE-WRITE whitelist на кнопке `RE: → произвольный hex`** (только read-опкоды: `{0x50, 0x51, 0x54, 0x56, 0x60, 0x61}`, `firmware/esp32-classic/radon_ha_gateway.yaml:509-528`). Любой байт вне этого множества → полная отмена записи + `ESP_LOGW`. Защищает от ручного ввода `0x53` (сброс конфига) и `0xA0..0xCF` (DFU).
- Опкоды внутри канонического whitelist в диапазоне `0xA0..0xCF` (`0xA4`, `0xA6`, `0xA8`, `0xAF`) — **распознаются прибором** и подтверждены не-DFU трассой официального приложения. На кнопке hex-ввода намеренно НЕ разрешены (только read-опкоды).
- ⚠ Если разрабатываешь свой клиент — никогда не делай `for op in range(0xA0, 0xD0): write(op, 0x00, ...)`. Это инструмент DFU-погружения, а не reverse engineering.

### INC-PLUS2-SINGLE-CENTRAL — пока подключён телефон, ESP не коннектится

- **Дата:** 2026-06-15
- **Severity:** UX-issue
- **Статус:** ✅ Документировано

**Симптом.** Установил MAC через Web UI, перезагрузил шлюз — `BLE: RadonEye
подключён = OFF`, RSSI идёт, но коннект не происходит. В UART/OTA-логе:

```
[W][ble_client]: Connection failed, reason 0x05 (PEER_DISC_REASON_REM_HOST)
```

**Корень.** RadonEye Plus2 — **single-central**: GATT-сессия может быть
открыта только с одним BLE-центром одновременно. Пока в нём активна сессия с
приложением FTLAB/Ecosense (даже если телефон в кармане и приложение в
background), ESP получает `Connection refused`.

**Решение.**

- **Закрыть приложение полностью.** На Android — Force Stop в настройках приложения. На iOS — двойной свайп вверх для удаления из мультитаскинга.
- Подождать ~30 секунд после закрытия приложения (BLE-сессия закрывается не моментально).
- В Web UI шлюза — нажать «Переподключить» в группе BLE.

**Проверка.** В UART/OTA-логе должно появиться:
```
[I][ble_client]: Connected to RadonEye
[I][ble_client]: Service 00001523-... discovered
[I][ble_client]: Subscribed to NOTIFY-1 (0x000d)
```

### INC-PLUS2-MTU23 — Plus2 не запрашивает увеличение MTU

- **Дата:** 2026-06-15
- **Severity:** архитектурное ограничение, не баг
- **Статус:** Документировано как «не пытаться обходить»

**Симптом.** В UART-логе:
```
[W][ble_client_base]: MTU exchange timeout (default MTU=23 used)
```

**Корень.** RadonEye Plus2 не отвечает на `esp_ble_gattc_send_mtu_req()` —
это ограничение прошивки прибора, обойти нельзя.

**Решение.** **Не надо обходить.** Все наши кадры (опкоды `0x50`/`0x51`/`0x54`/
`0x60`/`0x61`) ≤ 20 байт ATT payload и помещаются в один MTU=23. Просто
игнорировать warning.

⚠ **Не пытаться** поднимать MTU в будущих ревизиях прошивки шлюза — упрёшься в
тот же warning и потратишь время.

### INC-RADON-JSON111 — `json:111` на XIAO C3 с `web_server.log: true`

- **Дата:** 2026-06-17
- **Severity:** near-OOM, в худшем случае ребут
- **Статус:** ⚠ **Открытое решение** — пока работает, при первом ребуте откатить

**Симптом.** В UART/OTA-логе:
```
[E][web_server:198]: json:111: JSON document overflow
```

**Корень.** Debug Log панель в Web UI v3 (`web_server.log: true`) подписана на
`/events` SSE и сериализует **каждое** лог-сообщение как JSON-event. На XIAO
C3 с 400 KB SRAM (без PSRAM) при F5-шторме браузера + WiFi-флапах SSE-буфер
не дренируется → ArduinoJSON document overflow → near-OOM.

**Решение в текущей прошивке (`xiao-esp32-c3/radon_ha_gateway_c3.yaml`).**

Оператор 2026-06-17 явно разрешил `log: true` как исключение для удобства
отладки. В YAML стоит комментарий:

```yaml
web_server:
  version: 3
  port: 80
  log: true   # ⚠ ИСКЛЮЧЕНИЕ: на XIAO C3 оставлено true для нативной
              # вкладки логов в Web UI. Если пойдут ребуты / json:111 / OOM —
              # вернуть false БЕЗ переспроса.
```

**Если ловишь json:111 на своей плате** — поменяй на `log: false`, перекомпилируй,
перезалей. Debug Log панель исчезнет из Web UI, но сенсоры, sorting_groups и API
останутся целы.

### INC-RADON-SCAN-RESONANCE — резонанс scan_parameters с adv-периодом

- **Дата:** 2026-06-12 (выводы перенесены из соседнего скилла `atomfast-esp32`)
- **Severity:** «тихий» отказ WiFi при долгом прогоне
- **Статус:** ✅ **Митигировано** дефолтными scan_parameters в YAML

**Симптом.** При `esp32_ble_tracker.scan_parameters: interval` ≈ `1000ms`
(= advertising-период RadonEye Plus2) — фазовое биение, периодические
провалы air-time, голодание WiFi-стека на одном радио. Через 30+ минут:
BLE notify идёт, но WiFi мёртв (ни ping, ни HTTP, без reboot-loop).

**Решение в текущих YAML.**

В обоих `radon_ha_gateway.yaml` и `radon_ha_gateway_c3.yaml` параметры скана
заданы так, чтобы НЕ совпадать с adv-периодом 1 с:

```yaml
esp32_ble_tracker:
  scan_parameters:
    interval: 640ms      # не делитель 1000ms, нет фазового замка
    window: 32ms         # duty 5 %
    active: true         # активный скан (запрос scan-response). Стоит
                         # дополнительного air-time (BLE-WiFi coex),
                         # но улучшает обнаружение Plus2 и стабильность
                         # ble_client.connect(). См. реальные YAML
                         # (esp32-classic/radon_ha_gateway.yaml:166,
                         # xiao-esp32-c3/radon_ha_gateway_c3.yaml:125).
```

⚠ **Не правь** scan_parameters на `1000ms / 100ms` или `500ms / 50ms` — это
вернёт резонанс.

### INC-RADON-NARODMON-ALWAYS-OFF — switch Народмона обязан восстанавливаться в OFF

- **Дата:** 2026-06-17 (HARD-правило проекта)
- **Severity:** privacy/policy
- **Статус:** ✅ Зафиксировано в YAML

**Симптом.** После reboot / safe-mode / factory_reset / OTA switch «Выгружать
на Народмон» в Web UI восстанавливается во **включённое** состояние, ESP
начинает слать данные на narodmon.ru без явного подтверждения пользователя.

**Корень.** ESPHome `switch.template` по умолчанию использует
`restore_mode: RESTORE_DEFAULT_OFF` — это «восстановить последнее, по умолчанию
OFF». Если в NVS было `ON` (пользователь когда-то включил для теста, потом
перепрошил без `esphome clean` или с миграцией NVS) — после OTA switch
восстановится в `ON`.

**Решение в текущих YAML.**

В обоих `radon_ha_gateway.yaml` и `radon_ha_gateway_c3.yaml` HARD-правило:

```yaml
- platform: template
  name: "Выгружать на Народмон"
  id: narodmon_enabled
  restore_mode: ALWAYS_OFF     # ← после reboot/safe-mode/OTA гарантированно OFF
  optimistic: true
```

⚠ **Никогда** не менять на `RESTORE_DEFAULT_OFF`, `RESTORE_INVERTED_DEFAULT_OFF`
или `ALWAYS_ON`. Подробности — в `CLAUDE.md` проекта ESP32, секция «Switch
«Выгружать на Народмон» — restore_mode: ALWAYS_OFF».

---

## 4. Частые ошибки установки клиентов

### `Invalid key format, please check it's using base64`

Самая частая ошибка первой установки. Полный разбор — в [INSTALL.md](INSTALL.md),
Troubleshooting раздел **0**.

Короткий путь решения: сгенерируй валидный `api_encryption_key` командой

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

и положи в `secrets.yaml` вместо placeholder'а `0000…==`.

### Прочие 11 типовых ошибок установки

См. [INSTALL.md](INSTALL.md), раздел **Troubleshooting** — там 12 пронумерованных
пунктов:

0. Invalid key format (САМАЯ ЧАСТАЯ)
1. Плата не определяется как COM-порт
2. `esphome compile` падает с `UnicodeDecodeError`
3. `esphome upload`: «Failed to connect to ESP32»
4. После прошивки плата ребутится в цикле
5. Web UI открывается, но карточек нет
6. `BLE: RadonEye подключён = OFF`
7. `WiFi: Auth Expired` каждые несколько секунд
8. `json:111: JSON document overflow` + пустой Web UI
9. OTA не работает после смены пароля
10. Команды Claude Code не запускаются с правильной кодировкой (Windows)
11. ESP видит несколько `FR:PD…` устройств (не свой)

---

## 5. Связанные проекты / cross-references

- [atomfast-esp32 KNOWN_ISSUES](https://github.com/VibeEngineering-LLC/atomfast-esp32/blob/main/KNOWN_ISSUES.md) — аналогичный справочник для AtomFast Plus2 (γ-дозиметр).
- [radex-esp32 KNOWN_ISSUES](https://github.com/VibeEngineering-LLC/radex-esp32/blob/main/KNOWN_ISSUES.md) — аналогичный справочник для Radex MR107ion (тоже радон, но READ-poll).
- [Narodmon.ru](https://narodmon.ru/) — публичная сеть бытовых датчиков, протокол выгрузки документирован на сайте проекта.
- [Issues tracker](https://github.com/VibeEngineering-LLC/radoneye-esp32/issues) — сюда репортить новые проблемы или дополнения в матрицу плат.
