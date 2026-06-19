# Firmware changelog — radoneye-esp32

> 🇷🇺 Русская версия: [CHANGELOG.md](CHANGELOG.md)

Versioning: semver (`vMAJOR.MINOR.PATCH`) + board suffix via hyphen
(e.g. `v2.1-c3`).

- MAJOR — incompatible protocol / architecture change
- MINOR — feature added, backward compatibility preserved
- PATCH — bugfix / stability / refactor without API change

Dates — UTC+3 (Europe/Moscow).
Active branches:
- **`xiao-esp32-c3/radon_ha_gateway_c3.yaml`** — XIAO ESP32-C3 (arduino + Bluedroid)
- **`esp32-classic/radon_ha_gateway.yaml`** — ESP32-DevKitC v4 WROOM-32 (arduino)

All versions validated on RadonEye Plus2 (RD200PLUS).

---

## 2026-06-19 — reorganised firmware/ into subfolders

**What:** firmware YAMLs were moved from the flat `firmware/*.yaml`
layout to «one board = one subfolder»:

```
firmware/
├── esp32-classic/         radon_ha_gateway.yaml
├── xiao-esp32-c3/         radon_ha_gateway_c3.yaml
├── secrets.example.yaml   (shared)
├── CHANGELOG.md           (this file)
└── .gitignore
```

**Why:** firmware are now published in individual folders named after
the board type. Unified with the sibling project `atomfast-esp32`, which
uses the same layout
(see [atomfast-esp32 CHANGELOG.md](https://github.com/VibeEngineering-LLC/atomfast-esp32/blob/main/firmware/CHANGELOG.md)
v0.9.0-c3).

**What did NOT change:** YAML contents, `secrets.example.yaml`,
firmware versions. This is a structural change — paths in
`INSTALL.md` / `README.md` updated for the new layout.

**Affected documents:**
- [INSTALL.en.md](../INSTALL.en.md) — `esphome compile`/`upload` commands now carry the subfolder prefix.
- [README.en.md](../README.en.md) — table «Which firmware goes with which board», section «Skill structure».
- `secrets.example.yaml` — paths in comments updated.

---

## v2.1-c3 (2026-06-17) — port to Seeed Studio XIAO ESP32-C3 + Narodmon infrastructure

**What:** second parallel baseline — `radon_ha_gateway_c3.yaml` for
**Seeed Studio XIAO ESP32-C3** (`board: seeed_xiao_esp32c3`, variant
`esp32c3`, framework `arduino`). Base: `radon_ha_gateway.yaml` v2.0
(ESP32-DevKitC v4). Narodmon infrastructure added in Web UI, but
**OFF by default** (HARD rule `restore_mode: ALWAYS_OFF`).

**Why a C3 branch:**
- XIAO ESP32-C3 is the most compact (~22×18 mm) ESP board with BLE+Wi-Fi, USB-C, ~$5.
- Fits a production gateway for **one** RadonEye Plus2 (the classic DevKitC v4 supports up to 3, which is overkill for most cases).
- `framework: arduino` chosen deliberately — `esp-idf` on C3 in the Windows ESPHome toolchain is confirmed unstable without MSYS2 (build fails at the CMake stage).

**Changes from v2.0 DevKitC:**

1. **Board**: `esp32: variant: esp32c3, board: seeed_xiao_esp32c3`.
2. **Framework**: `arduino` (same as v2.0; on C3 esp-idf requires MSYS2 — postponed).
3. **Build path**: separate `D:/esp32_radon_build/radon-gw-c3` (to avoid crossing with the DevKitC build).
4. **`device_name`**: `radon-gw` (instead of v2.0's `radon-ha-gateway`) — shorter, doesn't clash with other gateways.
5. **Web Server v3 + sorting_groups (5 groups)**:
   - `sg_sensors` — Radon / Peak / Count / hour/day averages / temperature
   - `sg_ble` — state / reconnects / RSSI / reconnect / reset
   - `sg_actions` — Safe Mode / factory reset / diagnostic
   - `sg_narodmon` — switch ALWAYS_OFF / protocol select / metric names RR1/T1/H1 / send now
   - `sg_diag` — Wi-Fi signal/SSID/IP/MAC / API / uptime / firmware version
6. **Narodmon infrastructure (step3, OFF by default)**:
   - `switch.template narodmon_enabled` — `restore_mode: ALWAYS_OFF` (HARD)
   - `select.template narodmon_method` — 4 options (`HTTP GET`/`HTTP POST`/`HTTPS POST`/`JSON POST`), default `HTTP GET`
   - `button narodmon_send_now` — manual trigger
   - `text` fields `nm_radon` (RR1), `nm_temp` (T1), `nm_hum` (H1) — Narodmon metric names
   - `script send_narodmon` — 4 branches by protocol, guards `wifi.connected` + `!std::isnan(s_radon.state)`
   - `interval: 600s` — auto-send ONLY when `narodmon_enabled.state == true`
   - `http_request: verify_ssl: false, timeout: 5s`
   - `time:` SNTP — was already present, needed for HTTPS handshake
7. **`web_server.log: true`** — HARD exception for C3 (see INC-RADON-JSON111 in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)). If reboots / `json:111` / OOM appear — switch to `false` without asking again.
8. **`web_server.auth`**: username `radon` (inline), password = `!secret ota_password`. Basic Auth is mandatory (INC-PLUS2 INC-10 mitigation — cuts phantom SSE keepalives on 401).
9. **Wi-Fi watchdog 180s** — `wifi::global_wifi_component->is_connected()` false for >180 s → `App.safe_reboot()`.
10. **`api.reboot_timeout: 0s`** — board does NOT reboot on HA-API loss (BLE polling keeps running standalone).

**Carried over from v2.0:**

- BLE client to one RadonEye Plus2 (single-central).
- Opcode whitelist `{0x50, 0x51}` for normal polling (see INC-RADON-UNIT in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)).
- 20-byte notify-frame parsers for `0x50` / `0x51`:
  - `0x50 [2:4]` → uint16 LE Bq/m³ (instant)
  - `0x50 [12:14]` → uint16 LE Peak
  - `0x50 [14:16]` → uint16 LE Count
  - `0x51 [4:8]` → uint32 LE uptime min
  - `0x51 [18:20]` → device clock mm:ss (live)
- `esp32_ble_tracker.scan_parameters: interval: 640ms, window: 32ms, active: false` (5 % duty cycle, doesn't resonate with the ~1 s adv period).

**Stability target:** running in production since 2026-06-17.
No specific MTBF figures at publication time.

**File:** `firmware/xiao-esp32-c3/radon_ha_gateway_c3.yaml`.

---

## v2.0 (2026-06-15) — base DevKitC + live-reverse Plus2 protocol

**What:** baseline `radon_ha_gateway.yaml` for **ESP32-DevKitC v4**
(WROOM-32), `board: esp32dev`, `framework: arduino`. Full live reverse
of the BLE protocol of RadonEye Plus2 (RD200PLUS), opcodes `{0x50,
0x51, 0x54, 0x56, 0x60, 0x61}` parsed byte by byte. Support for **up
to 3 devices** simultaneously (`radon1_mac`, `radon2_mac`,
`radon3_mac`).

**Why:** before this revision we worked with opcode `0x50` through
blind probing — without understanding the byte layout. The 2026-06-15
live reverse (direct PC Bluetooth read + HCI-snoop trace of the
official RadonEye+² Android app) gave precise offsets.

**Changes from earlier versions:**

1. **Parser of 20-byte `0x50` notify frames** (instant radon):
   - `[0]` — opcode echo (`0x50`)
   - `[1]` — payload length (`0x10` = 16)
   - **`[2:4]` — Radon current, uint16 LE, Bq/m³** ← main field
   - `[12:14]` — Peak (max radon), uint16 LE, Bq/m³
   - `[14:16]` — Count (measurement number), uint16 LE
   - `[16:18]` — secondary counter
   - `[18:20]` — clock mm:ss (cached since the last `0x51`)
2. **Parser for `0x51`** (status/uptime/live clock):
   - **`[4:8]` — Uptime minutes, uint32 LE** (+1/min)
   - `[12:14]`, `[14:17]` — device config, partially decoded
   - **`[18:20]` — Clock mm:ss (live)** ← useful for sync
3. **Opcodes `0x60` / `0x61` (history)** parsed:
   - `0x60` → request for the number of records available (on a real device ~9600 = ~13 months of hourly history)
   - `0x61 <N_u16_LE>` → bulk dump of the N most recent records on NOTIFY-2 (`0x0010`)
   - 8-byte record format:
     - `[0:4]` — Unix timestamp, uint32 LE
     - `[4:6]` — Radon, uint16 LE, Bq/m³
     - `[6:8]` — Temperature, °C × 256 (Q8.8 fixed-point, divide by 256)
4. **Opcode `0x54`** (firmware version + config):
   - `[2]` — units (`01` = Bq/m³, `00` = pCi/L)
   - `[5:7]` — alarm threshold (uint16 LE)
   - `[8:14]` — ASCII «V1.0.2»
5. **Opcode `0x56`** (serial): 17 ASCII bytes in the format «YYYYMMDD» + «SN» + «####» + «PD2».
6. **Strict opcode whitelist** (HARD): `{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`. Any other opcode in `0xA0..0xCF` is DFU-risk (see INC-RADON-DFU in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)).
7. **Gateway polls only `{0x50, 0x51}`**. `0x53` is in the whitelist, but a bare `0x53` zeroes the device config (see INC-RADON-UNIT in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)) — do NOT send during polling.
8. **GATT map** confirmed:
   - SERVICE `0x0009` `00001523-1212-efde-1523-785feabcd123` (Nordic-base)
   - CHAR `0x000a` `00001524-…` write — opcode WRITE (value-handle `0x000b`)
   - CHAR `0x000c` `00001525-…` notify — NOTIFY-1 (value-handle `0x000d`) — replies to opcodes
   - CHAR `0x000f` `00001526-…` notify — NOTIFY-2 (value-handle `0x0010`) — history channel for `0x60`/`0x61`
9. **MTU=23 (default)** — Plus2 does NOT request an increase; 20-byte ATT payload is enough (see INC-PLUS2-MTU23 in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)).
10. **Single-central** — while an FTLAB-app phone is connected, the ESP gets refused (see INC-PLUS2-SINGLE-CENTRAL in [KNOWN_ISSUES.en.md](../KNOWN_ISSUES.en.md)).

**What's exposed to Home Assistant:**

- `sensor.radon_instant` — instant radon, Bq/m³
- `sensor.radon_pci` — same in pCi/L (= Bq/m³ ÷ 37)
- `sensor.radonye_uptime_min` — device uptime, min
- `text_sensor.radon_last_updated` — timestamp of the last measurement
- `text_sensor.radon_device_clock` — device clock mm:ss
- `binary_sensor.radon_ble_connected`
- `sensor.radon_rssi`

**File:** `firmware/esp32-classic/radon_ha_gateway.yaml`.

---

## Architectural limits (not bugs)

- **MTU=23, not 247.** Plus2 doesn't reply to MTU exchange. Don't try to work around it — you'll waste time. The 20-byte ATT payload is enough for all opcodes.
- **Single-central.** One BLE central at a time. Close the FTLAB app before starting the gateway, or treat the ESP as an «exclusive gateway» (don't connect the phone).
- **Maximum 3 `ble_client`** per board (Bluedroid stack limit). If you have 4+ RadonEyes — run 2+ gateways.
- **0x53 = config-WRITE** is in the whitelist, but a bare `0x53` zeroes the config. NEVER send it during automatic polling — only via a manual payload backed by an official-app trace.
- **0xA0..0xCF outside the whitelist = DFU mode.** Recovery — physical battery removal for ~30 s.

---

## Reverse-engineering sources

See [references/sources.md](../references/sources.md) and
[references/plus2_protocol.md](../references/plus2_protocol.md)
(Russian). Main ones:

- live PC Bluetooth read (Python bleak), 2026-06-15
- Android HCI-snoop trace of the official RadonEye+² app (FTLAB), 2026-06-15
- open-source https://github.com/EtoTen/radonreader (RD200 V1)
- ZheTian Lab / GitHub — RD200 V2 + Plus2 opcodes
