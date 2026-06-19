# RadonEye Plus2 → ESP32 → Home Assistant / Web UI

> 🇷🇺 Русская версия: [README.md](README.md)

![Two RadonEye Plus2 detectors next to an ESP32 gateway with a U.FL/IPEX antenna](images/radoneye-plus2-pair-with-gateway.jpg)

*Top — a pair of RadonEye Plus2 (RD200P2) with OLED displays.
Bottom — an ESP32 board in heat-shrink with an external PCB antenna on a
U.FL/IPEX pigtail: a detached antenna keeps the device↔gateway RSSI stable
even through a reinforced-concrete wall.*

Ready-to-flash ESPHome firmware that turns a cheap ESP32 board into a
**24/7 BLE gateway** between a **RadonEye Plus2 (RD200PLUS)** radon detector
and your home. The detector stops depending on a phone — while the ESP32
is plugged in, data flows around the clock without the FTLAB/Ecosense
app and without the cloud.

```
RadonEye Plus2 ─BLE Notify─► ESP32 ─Web UI v3─► browser
   (RD200PLUS)                  │
                                ├─► ESPHome API ─► Home Assistant
                                │
                                └─► Narodmon (infrastructure present, OFF by default)
```

Skill documentation:

- [`SKILL.md`](SKILL.md) — full knowledge base (Russian)
- [`INSTALL.en.md`](INSTALL.en.md) — step-by-step install + 12 troubleshooting cases
- [`KNOWN_ISSUES.en.md`](KNOWN_ISSUES.en.md) — board compatibility matrix + incident registry
- [`firmware/CHANGELOG.en.md`](firmware/CHANGELOG.en.md) — firmware version history
- [`references/plus2_protocol.md`](references/plus2_protocol.md) — full BT protocol reverse-engineering (Russian)

---

## Which firmware for which board

The skill ships **two firmwares** on a single codebase, one subfolder
per board type. Differences: target ESP32 module, BLE stack, number of
simultaneous devices.

| Firmware | Target board | What's inside | When to pick |
|---|---|---|---|
| **[`firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml`](firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml)** *(current, v2.1-c3, 2026-06-17)* | **Seeed Studio XIAO ESP32-C3** (`board: seeed_xiao_esp32c3`, variant=`esp32c3`, framework=arduino) | BLE client to 1×RadonEye Plus2, Web Server v3 + Basic Auth + sorting_groups (5 groups: Sensors / BLE / Actions / Narodmon / Diag), ESPHome API encryption, WiFi watchdog, Narodmon infrastructure (switch `ALWAYS_OFF`) | Production-ready gateway for **one** RadonEye Plus2, smallest board (~$5), native USB-C |
| [`firmware/esp32-classic/radon_ha_gateway.yaml`](firmware/esp32-classic/radon_ha_gateway.yaml) *(v2.0, 2026-06-15)* | **ESP32-DevKitC v4** WROOM-32 (`board: esp32dev`, framework=arduino) | Baseline gateway on classic DevKitC, BLE client to 1×RadonEye, Web UI + ESPHome API | If you already own a DevKitC, or prefer micro-USB over USB-C |

Both firmwares speak the same RadonEye Plus2 protocol (`Service 00001523-…`).
A full compatibility matrix of supported / untested / incompatible boards
is in [`KNOWN_ISSUES.en.md`](KNOWN_ISSUES.en.md) §1.

---

## What this firmware solves

- The FTLAB/Ecosense app is Android/iOS-only and keeps data on the phone.
- A community Home Assistant integration exists, but requires HA + a
  separate Bluetooth proxy.
- This firmware turns an ESP32 into a **standalone 24/7 gateway, no cloud
  required**: BLE → parsing → Web UI + ESPHome API + (optional) Narodmon.

---

## Quick start (XIAO ESP32-C3, ~15 minutes)

Full install guide with troubleshooting is in [`INSTALL.en.md`](INSTALL.en.md).
Short version:

### 1. Prepare secrets

```powershell
git clone https://github.com/VibeEngineering-LLC/radoneye-esp32.git
cd radoneye-esp32\firmware\
Copy-Item secrets.example.yaml secrets.yaml
```

Open `secrets.yaml` and fill in:
- `wifi_ssid` / `wifi_password` — home 2.4 GHz Wi-Fi.
- `ap_password` — password for the «radon-gw Fallback» captive-portal AP (≥8 characters).
- `api_encryption_key` — `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`.
- `ota_password` — a long password for OTA (also used as the Web UI Basic Auth password; username = `radon` inline in the YAML).
- `radon1_mac` — **can stay as the `AA:BB:CC:DD:EE:FF` placeholder**, you set the real MAC via Web UI after the first flash.

### 2. Compile and flash

```powershell
# Adjust the path to esphome.exe (typical Windows location):
$esp = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\esphome.exe"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
cd claude-skills\radoneye-esp32\firmware\
& $esp compile xiao-esp32-c3/radon_ha_gateway_c3.yaml
& $esp upload  xiao-esp32-c3/radon_ha_gateway_c3.yaml --device COM<N>
```

Find the COM port:
```powershell
Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'CH340|CP210|FTDI|USB Serial' }
```

### 3. First boot → captive portal → WiFi

If WiFi isn't configured, the ESP brings up an AP **«radon-gw Fallback»**
with the password from `ap_password`. From a phone, connect to that AP →
open `http://192.168.4.1/` → pick your home network → enter password →
**Save**. The ESP reboots and joins your WiFi.

### 4. Web UI and MAC binding

On your home network: `http://radon-gw.local/` (login `radon`,
password = `ota_password` from `secrets.yaml`).

In the Web UI:
- Group **«Поиск BLE» (BLE scan)** → «Запустить скан 30 с» («Run scan 30 s»)
  → find the device by its `FR:PD…` name → copy the MAC.
- Paste it into **«MAC Radon 1»** → click «Применить MAC и перезагрузить»
  («Apply MAC and reboot»).
- After reboot, the **«Sensors»** group should populate with
  radon/temperature/Peak/Count.

### 5. Connect to Home Assistant

In HA → Settings → Devices & Services → **Add Integration** → ESPHome →
host `radon-gw.local` (or IP), encryption key — the same one from
`secrets.yaml`.

### If something goes wrong

See [`INSTALL.en.md`](INSTALL.en.md) §11 (12 troubleshooting cases) and
[`KNOWN_ISSUES.en.md`](KNOWN_ISSUES.en.md) (compatibility matrix + 7 incidents).

---

## Full RadonEye Plus2 BLE protocol

> All numbers below are the result of **live reverse-engineering 2026-06-15**
> (direct read via PC Bluetooth + HCI-snoop trace of the official RadonEye+²
> Android app). Raw frames and details — in
> [`references/plus2_protocol.md`](references/plus2_protocol.md) (Russian).

### Device identification on the air

| Parameter | Value |
|---|---|
| Model | **RD200PLUS** (the «Plus2» family) |
| advertising local_name | `FR:PD<serial>` (`FR:PD` is the generation prefix; digits are the serial) |
| PDU type | ADV_IND |
| Adv interval | ≈ 1 s |
| Service UUID in adv | `00001523-1212-efde-1523-785feabcd123` (Nordic-base) |
| MTU | 23 (default; the device does not request an upgrade) |
| Pairing / bonding | NOT required |
| Single-central | only one host connected at a time — others get refused (close FTLAB-app before starting the gateway) |

### GATT map

```
SERVICE  h=0x0001  1800  Generic Access Profile
SERVICE  h=0x0008  1801  Generic Attribute Profile
SERVICE  h=0x0009  00001523-1212-efde-1523-785feabcd123   (Nordic-base, "LED Button Service")
  CHAR   h=0x000a  00001524-...   [read,write]   <- WRITE (commands/opcodes), VALUE-handle 0x000b
  CHAR   h=0x000c  00001525-...   [read,notify]  <- NOTIFY-1 (replies),       VALUE-handle 0x000d
    DESC h=0x000e  2902  CCCD
  CHAR   h=0x000f  00001526-...   [read,notify]  <- NOTIFY-2 (history),       VALUE-handle 0x0010
    DESC h=0x0011  2902  CCCD
SERVICE  h=0x0012  180a  Device Information
  CHAR   h=0x0013  2a29  [read]  Manufacturer Name String
```

ATT operates on **value-handles (declaration + 1)**: WRITE = `0x000b`,
NOTIFY-1 = `0x000d`, NOTIFY-2 = `0x0010`.

### Opcode whitelist (HARD — DO NOT VIOLATE)

Allowed writes to **value-handle 0x000b**:

```
{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}
```

> ⚠️ **DFU-RISK.** Probing opcodes **in the range `0xA0..0xCF` outside the
> whitelist** puts the device into DFU mode. Logged as an incident on
> 2026-06-07. Recovery — physical battery removal for ~30 seconds.
>
> 🛑 **`0x53` is a config-WRITE.** The opcode is in the whitelist in the
> sense «the device recognises it», but a bare `0x53` (with no valid
> payload) **wipes the device configuration**: display flips Bq/m³ → pCi/L,
> alarm threshold resets to 0. Recovery — manually through the RadonEye app.
>
> **Gateway polling = ONLY `{0x50, 0x51}`.** Treat any other opcode as
> potentially writable; never send it without exact knowledge of the
> payload (or an official-app trace confirming safety).

### Opcode 0x50 — instant radon (decoded live, 6/6)

**Request:** write the 20-byte command `50 11 00 … 00` to WRITE handle `0x000b`.
**Response:** notify on NOTIFY-1 (`0x000d`), **20 bytes**.

Live example (radon ≈ 18 Bq/m³):
```
50 10 12 00 00 00 00 00 00 00 00 00 16 00 01 00 02 00 1f 16
```

| Offset | Field | Type | Meaning |
|---|---|---|---|
| `[0]` | opcode echo | u8 | `0x50` |
| `[1]` | payload length | u8 | `0x10` = 16 |
| `[2:4]` | **Radon current** | **uint16 LE, Bq/m³** | 18 in the example (= 0.486 pCi/L) |
| `[4:6]` | reserved | uint16 LE | always 0 (NOT day-avg) |
| `[6:8]` | reserved | uint16 LE | always 0 (NOT month-avg) |
| `[8:12]` | reserved / zeros | — | 0 |
| `[12:14]` | **Peak (max radon)** | uint16 LE, Bq/m³ | confirmed against the device display |
| `[14:16]` | **Count (measurement number)** | uint16 LE | increments 1→2→3 within the window |
| `[16:18]` | secondary counter | uint16 LE | role TBD |
| `[18:20]` | clock mm:ss (cached) | 2×u8 | value at the moment of the last `0x51` (not live) |

**Unit conversion:** `pCi/L = Bq/m³ ÷ 37` (exact). The device returns **Bq/m³**.

### Opcode 0x51 — status / uptime / live clock

**Request:** `51 11 00 … 00` to `0x000b`. **Response:** notify on `0x000d`, 20 bytes.

Live example:
```
51 12 02 00 5c 00 00 00 fc 0a 08 00 aa 19 1a 06 0f 01 1f 16
```

| Offset | Field | Type | Meaning |
|---|---|---|---|
| `[0]` | opcode echo | u8 | `0x51` |
| `[1]` | payload length | u8 | `0x12` = 18 |
| `[2:4]` | status | uint16 LE | constant `0x0002` |
| `[4:8]` | **Uptime minutes** | uint32 LE | +1 per minute (confirmed) |
| `[8:12]` | unknown | uint32 LE | **NOT a counter** (non-monotonic, refuted) |
| `[12:14]` | unknown | 2×u8 | varies |
| `[14:17]` | firmware / factory date (?) | 3×u8 | constant `1a 06 0f` |
| `[17]` | slow flag | u8 | increments every ~30-48 min |
| `[18:20]` | **Clock mm:ss (live)** | 2×u8 | `[18]` = minutes, `[19]` = seconds, plain hex |

### Opcode 0x54 — firmware version + config

**Response (NOTIFY-1):** `54 0f 01 00 00 c8 00 01 56 31 2e 30 2e 32 00 01 00 44 32 00`.
- `[2]` — units (`01` = Bq/m³, `00` = pCi/L).
- `[5:7]` — alarm threshold (`c8 00` LE = 200 Bq/m³).
- `[8:14]` — ASCII «V1.0.2».

### Opcode 0x56 — serial / model

**Response (NOTIFY-1):** `56 11 <17 ASCII bytes> 00` — serial in the format
«YYYYMMDD» + «SN» + «####» + «PD2».

### Opcodes 0x60 / 0x61 — hourly history (decoded, btsnoop 2026-06-15)

`0x60` — request **number of available records**. NOTIFY-1 response:
`[2:4]` uint16 LE = total record count. On a real device — 9600
(≈ 13 months of hourly history).

`0x61` — bulk dump. Command format: `61 11 <N_u16_LE> 00…`. Parameter
`[2:4]` = how many of the most recent records to return. Response — a
continuous stream of **8-byte records on NOTIFY-2** (`0x0010`).

**History record format (8 bytes):**

| Offset | Field | Type | Meaning |
|---|---|---|---|
| `[0:4]` | **Unix timestamp** | uint32 LE | seconds, device local time |
| `[4:6]` | **Radon** | uint16 LE | Bq/m³ |
| `[6:8]` | **Temperature** | uint16 LE | °C × 256 (Q8.8 fixed-point, divide by 256) |

> On a full 9600-record dump: radon min=0 / max=884 / mean=132.3 Bq/m³,
> temperature min=20.2 / max=27.6 / mean=23.6 °C — physically plausible.
> Inter-record step is exactly 3600 s; gaps = the device being powered off.

The **day / month / year averages** are NOT a dedicated opcode — the
official app downloads the raw hourly history via `0x60`/`0x61` and
**aggregates the averages locally**. The NOTIFY-2 channel (`1526`/`0x0010`),
which stays silent on direct probes, is the **history channel** —
activated only after `0x60`/`0x61`.

### Opcode 0x53 — config-WRITE (dangerous, never poll with it)

```
53 11 01 00 00 c8 00 01 00 00 00 00 00 00 00 00 00 00 00 00
                  └─┬─┘  └┬┘
                  threshold  field-id
                  c8 00=200 Bq/m³
```

The device confirms the write via a NOTIFY frame **echoing as 0x54**.
The complete byte map (units, alarm on/off, interval, °C↔°F, buzzer) is
only partially decoded — see [`references/plus2_protocol.md`](references/plus2_protocol.md) §6B (Russian).

### Minimal read recipe (any stack)

1. Scan → find the device by adv prefix `FR:PD` (or by known MAC).
2. Connect (single-central; free up the ESP bridge if it's connected).
3. Subscribe notify on `00001525-…` (CCCD `0x000e` → `01 00`).
4. Write `50 11 00 … 00` to `00001524-…` (value-handle `0x000b`).
5. Receive a 20-byte notify frame on `0x000d`.
6. `radon_Bq = uint16_LE(frame[2:4])`; `radon_pCi = radon_Bq / 37`.

In ESPHome: `ble_client.services[].characteristics[]` writes `01 00`
into the CCCD, writes `50 11 00…` into `00001524-…`, parses the notify
in a lambda: `x[2] | (x[3] << 8)` → Bq/m³.

---

## Web UI / Home Assistant

The C3 firmware Web UI ships with five themed groups (`sorting_groups`):

| Group | Contents |
|---|---|
| `sg_sensors` | Radon Bq/m³, Peak, Count, rolling hour/day averages, temperature from history |
| `sg_ble` | BLE connected / connects / reconnects / RSSI / reconnect / counter reset |
| `sg_actions` | Reboot (Safe Mode), factory reset, diagnostics buttons |
| `sg_narodmon` | Switch «Выгружать на Народмон» (ALWAYS_OFF), transport select, metric names RR1/T1/H1, «Send now» button |
| `sg_diag` | WiFi signal/SSID/IP/MAC, API connected, uptime, firmware version |

In Home Assistant all entities appear automatically via the ESPHome API.

---

## Narodmon infrastructure — OFF by default (HARD)

The «Выгружать на Народмон» (Upload to Narodmon) switch is present, but
**MUST** have `restore_mode: ALWAYS_OFF`:

```yaml
- platform: template
  name: "Выгружать на Народмон"
  id: narodmon_enabled
  restore_mode: ALWAYS_OFF     # ← HARD: always OFF after reboot/safe-mode/OTA
  optimistic: true
```

After a reboot, a brief power loss, safe-mode, factory reset, or OTA —
the switch **always** returns to OFF. The user never gets a
«surprise» upload to the cloud.

The «Способ отправки» (transport) select offers 4 transports (see the
Narodmon project documentation):

- `HTTP GET` — `narodmon.ru/get?ID=<MAC>&RR1=<value>&T1=<value>&H1=<value>`
- `HTTP POST` — `narodmon.ru/post`, form-urlencoded
- `HTTPS POST` — same, via mbedTLS
- `JSON POST` — `narodmon.ru/json`, application/json

The Narodmon server enforces a 5-minute minimum interval; shorter = a
1-hour IP ban. The firmware hard-codes 600 s.

---

## HARD anti-patterns (violation → secret leak / device damage)

- ❌ **Don't publish `firmware.bin` / `firmware.factory.bin`** — the
  binary embeds WiFi SSID, WiFi password, device MAC, OTA password, and
  API encryption key as plain ASCII. Only YAML + `secrets.example.yaml`
  with placeholders.
- ❌ **Don't drop `restore_mode: ALWAYS_OFF` from the Narodmon switch**
  (HARD 2026-06-17).
- ❌ **Don't run `esphome logs --device COM<N>`** — DTR/RTS reboots the
  board and drops the BLE session. Use OTA-logger
  (`--device <hostname>.local`) or
  `mode COM<N> DTR=OFF RTS=OFF` + Python-serial (`scripts/serial_capture.ps1`).
- ❌ **Don't probe opcodes outside the whitelist** in the `0xA0..0xCF`
  range — DFU mode.
- ❌ **Don't send a bare `0x53`** — wipes device config (units + alarm threshold).
- ❌ **Don't enable `web_server.log: true`** on C3/S3 without a deliberate
  reason — SSE Debug Log during an F5 storm = json:111 overflow + near-OOM.
  On XIAO-C3 it is left as `true` for diagnostics convenience; if reboots
  appear, switch to `false`.

---

## Skill layout

```
radoneye-esp32/
├── README.md                            ← Russian entry point
├── README.en.md                         ← THIS FILE (English)
├── SKILL.md                             ← full knowledge base (Russian)
├── INSTALL.md / INSTALL.en.md           ← install guide + troubleshooting
├── KNOWN_ISSUES.md / KNOWN_ISSUES.en.md ← board compatibility + incident registry
├── firmware/
│   ├── CHANGELOG.md / CHANGELOG.en.md   ← firmware version history
│   ├── secrets.example.yaml             ← shared secrets template
│   ├── xiao-esp32-c3/
│   │   └── radon_ha_gateway_c3.yaml     ← CURRENT (v2.1-c3, XIAO ESP32-C3)
│   └── esp32-classic/
│       └── radon_ha_gateway.yaml        ← baseline (v2.0, ESP32-DevKitC v4)
├── references/
│   ├── plus2_protocol.md                ← full BT reverse-engineering (Russian, live + btsnoop)
│   ├── frame_layouts.md                 ← byte-by-byte for 0x50/0x51 (RD200 classic)
│   ├── known_devices.md                 ← which RadonEye models work
│   ├── v1_protocol.md                   ← V1 protocol (RD200 classic, opcodes + UUID)
│   ├── v2_protocol.md                   ← V2 protocol (RD200 ≥2022)
│   ├── temp_humidity_research.md        ← attempts to locate T/H in live frames
│   ├── python_v1_client.md              ← minimal bleak client
│   └── sources.md                       ← reverse-engineering sources
└── scripts/                             ← bleak helpers for RE sessions (plus2_*.py)
```

---

## Related projects

- [`VibeEngineering-LLC/atomfast-esp32`](https://github.com/VibeEngineering-LLC/atomfast-esp32) — AtomFast Plus2 (γ-dosimeter) → ESP32 → HA gateway, MIT.
- [`VibeEngineering-LLC/radex-esp32`](https://github.com/VibeEngineering-LLC/radex-esp32) — Radex MR107ion (radon too, but READ-poll), MIT.
- [Narodmon.ru](https://narodmon.ru/) — public crowdsourced sensor network; upload protocol documented on the project site.

---

## License

MIT.
