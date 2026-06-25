# Known Issues & Hardware Compatibility — radoneye-esp32

> 🇷🇺 Русская версия: [KNOWN_ISSUES.md](KNOWN_ISSUES.md)

Quick reference: which boards have actually been verified on the
RadonEye Plus2 gateway, which problems customers hit most often, and
what to do about them. Full BLE-protocol technical knowledge base —
in [README.en.md](README.en.md) and
[references/plus2_protocol.md](references/plus2_protocol.md) (Russian).

---

## 1. Board compatibility matrix

> **Disclaimer.** Operation is confirmed only on boards marked ✅. For
> everything else — **no guarantees**. If you tried something and it
> worked / didn't work — open an
> [issue](https://github.com/VibeEngineering-LLC/radoneye-esp32/issues),
> we'll add it to the matrix.

### ✅ Tested and recommended

| Board | Chip | Flash | PSRAM | Antenna | USB | YAML | Notes |
|---|---|---|---|---|---|---|---|
| **Seeed Studio XIAO ESP32-C3** ⭐ | ESP32-C3 single-core RISC-V 160 MHz | 4 MB | — | PCB | Type-C (native CDC) | `xiao-esp32-c3/radon_ha_gateway_c3.yaml` (arduino + NimBLE) | **Recommended board.** ~22×18 mm, ~$5. Web UI sorting_groups (5 groups), Narodmon infrastructure with `restore_mode: ALWAYS_OFF`. `web_server.log: true` is left as the user's explicit exception (2026-06-17). |
| **ESP32-DevKitC v4 (WROOM-32)** | ESP32 classic dual-core 240 MHz | 4 MB | — | PCB | micro-USB through CH340C / CP210x | `esp32-classic/radon_ha_gateway.yaml` (arduino + Bluedroid) | Baseline. Supports **up to 3 devices** (`radon1_mac` / `radon2_mac` / `radon3_mac`), RE mode (manual hex frame viewer). For a single device, the XIAO C3 is preferable (smaller form-factor + USB-C). |

### ❌ Does NOT work / not suitable

| Board | Reason |
|---|---|
| **ESP32-S2** | No BLE — physically cannot be a BLE gateway to RadonEye. |
| **ESP8266 (any)** | No BLE. |

### ⚠ Not tested — at your own risk

| Board | Expectation |
|---|---|
| **ESP32-S3-DevKitC-1 N16R8** | No ready-made YAML for S3. The neighbouring skill `atomfast-esp32` has a working S3 baseline — porting is feasible (change `board`, `variant`, `framework: esp-idf`, add `psram`), but not verified against RadonEye. |
| **ESP32-C6 / H2** | BLE 5.0 is there, the NimBLE stack is supported, but no YAML for them in this skill. |
| **ESP32-C3 SuperMini** | The chip is the same as on XIAO C3, but the GPIO mapping (LED, BOOT pad) and Flash size can differ. You can use `xiao-esp32-c3/radon_ha_gateway_c3.yaml` as a starting point — change `board: esp32-c3-devkitm-1` (if needed), remove `web_server.log: true` (SuperMini may not have enough heap). |
| **No-name ESP32-WROOM-32 clones** | Usually behaves like DevKitC v4, but crystal / PSRAM / Wi-Fi PA quality is unpredictable. May hit `WiFi Auth Expired` (see Troubleshooting #7 in [INSTALL.en.md](INSTALL.en.md)). |

---

## 2. Hardware selection guide

1. **Buying a new board for production** (one RadonEye Plus2 per gateway): **Seeed Studio XIAO ESP32-C3**. Stable, USB-C, mini form-factor, ~$5. Firmware — `xiao-esp32-c3/radon_ha_gateway_c3.yaml`.
2. **Already own a classic ESP32-DevKitC v4**: use `esp32-classic/radon_ha_gateway.yaml`. If you have several RadonEyes in the house / on one floor — this baseline supports up to 3 devices on a single gateway (`radon1_mac` / `radon2_mac` / `radon3_mac` in `secrets.yaml`).
3. **One gateway for 4+ RadonEyes**: ESPHome doesn't scale that way — maximum **3 `ble_client`** entries per board (Bluedroid stack limit). Run two gateways, each with its own `device_name` (e.g. `radon-gw-1` and `radon-gw-2`) and its own api/ota passwords.
4. **What NOT to buy**:
   - ESP32-S2 / ESP8266 (no BLE).
   - Boards without an explicit chip marking from the seller (often turn out to be ESP-12F with a fake ESP32 sticker).

---

## 3. Incidents

### INC-RADON-UNIT — `0x53` resets the RadonEye config (units + alarm threshold)

- **Date:** 2026-06-07 (recorded during Plus2 protocol reverse engineering)
- **Severity:** device remains operable, but its settings are reset
- **Status:** ✅ **Mitigated** by the gateway's opcode whitelist

**Symptom.** After an accidental `WRITE 0x53 …` (with no valid payload)
to the device:
- Display flips **Bq/m³ → pCi/L** (or vice versa).
- Alarm threshold is zeroed (was 200 Bq/m³ → became 0 → device beeps on any reading).
- Buzzer / night mode / temperature unit may reset.

**Root cause.** Opcode `0x53` is a config-WRITE on the device. The full
frame looks like:

```
53 11 01 00 00 c8 00 01 00 00 00 00 00 00 00 00 00 00 00 00
         ↑          ↑↑↑↑↑↑    ↑
         threshold  ?         changed-field code
         c8 00 = 200 Bq/m³
```

`0x53` is in the whitelist (`{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60,
0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`) — the device «recognises»
it. But a bare `0x53` with no byte structure in `[2:7]` zeroes
everything.

**Solution.**

- ✅ **The `radon_ha_gateway.yaml` / `_c3.yaml` gateway polls the device using ONLY opcodes `{0x50, 0x51}`.** `0x53` is not sent in any automatic sequence.
- ⚠ If you build your own client (Python bleak / nRF Connect) — **never** send a bare `53 ...` with no payload. The full byte map — in [references/plus2_protocol.md](references/plus2_protocol.md) §6B (Russian).

**Recovery after an accidental 0x53.**

- Open the FTLAB / Ecosense app on your phone.
- Connect to the device.
- Settings → manually set: units = Bq/m³, alarm threshold = 200 (or your value), buzzer = ON.
- Save & Reboot the device.

### INC-RADON-DFU — opcodes in `0xA0..0xCF` outside the whitelist → DFU mode

- **Date:** 2026-06-07 (live incident during opcode fuzzing)
- **Severity:** device temporarily unavailable, BLE interrupted
- **Status:** ✅ **Mitigated** by a strict whitelist

**Symptom.** When trying to `WRITE` an opcode **in the `0xA0..0xCF`
range that is NOT in the whitelist** (e.g. `0xA0`, `0xA1`, `0xA2`,
`0xA3`, `0xA5`, `0xA7`, `0xA9`, `0xAA..0xAE`, `0xB0..0xCF`):
- The device enters **DFU (Device Firmware Update) mode**.
- The BLE GATT session is torn down, advertising stops completely.
- Display — blank or shows a DFU icon.

**Recovery. Physical only:**

1. Open the battery compartment.
2. Take out **both** batteries.
3. Wait **~30 seconds** (bypass capacitors must drain).
4. Put the batteries back.
5. The device reboots in normal mode.

**Solution.**

- ✅ The gateway firmware's opcode whitelist is **strict** (`{0x10, 0x50, 0x51, 0x53, 0x54, 0x56, 0x60, 0x61, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}`). Any opcode outside the whitelist is **rejected** by the gateway's lambda parser.
- The whitelisted opcodes inside `0xA0..0xCF` (`0xA4`, `0xA6`, `0xA8`, `0xAF`) — **confirmed safe** from the official RadonEye app trace.
- ⚠ If you build your own client — never do `for op in range(0xA0, 0xD0): write(op, 0x00, ...)`. That's a DFU-bricking tool, not reverse engineering.

### INC-PLUS2-SINGLE-CENTRAL — while the phone is connected, the ESP can't connect

- **Date:** 2026-06-15
- **Severity:** UX issue
- **Status:** ✅ Documented

**Symptom.** You set the MAC through Web UI, rebooted the gateway —
`BLE: RadonEye connected = OFF`, RSSI keeps coming in, but the
connection doesn't happen. In the UART/OTA log:

```
[W][ble_client]: Connection failed, reason 0x05 (PEER_DISC_REASON_REM_HOST)
```

**Root cause.** RadonEye Plus2 is **single-central**: a GATT session
can only be open with one BLE central at a time. While the FTLAB /
Ecosense app session is active (even if the phone is in your pocket
and the app is in the background), the ESP gets `Connection refused`.

**Solution.**

- **Close the app completely.** On Android — Force Stop in app settings. On iOS — double-swipe up to remove from multitasking.
- Wait ~30 seconds after closing the app (the BLE session doesn't tear down instantly).
- In the gateway's Web UI — click «Reconnect» in the BLE group.

**Verification.** In the UART/OTA log you should see:
```
[I][ble_client]: Connected to RadonEye
[I][ble_client]: Service 00001523-... discovered
[I][ble_client]: Subscribed to NOTIFY-1 (0x000d)
```

### INC-PLUS2-MTU23 — Plus2 doesn't request an MTU increase

- **Date:** 2026-06-15
- **Severity:** architectural limit, not a bug
- **Status:** Documented as «don't try to work around it»

**Symptom.** In the UART log:
```
[W][ble_client_base]: MTU exchange timeout (default MTU=23 used)
```

**Root cause.** RadonEye Plus2 does not reply to
`esp_ble_gattc_send_mtu_req()` — that's a device-firmware limit,
non-overrideable.

**Solution.** **Don't try to work around it.** All our frames (opcodes
`0x50`/`0x51`/`0x54`/`0x60`/`0x61`) are ≤ 20 ATT payload bytes and fit
into one MTU=23. Just ignore the warning.

⚠ **Don't** try to raise the MTU in future gateway-firmware revisions —
you'll hit the same warning and waste time.

### INC-RADON-JSON111 — `json:111` on XIAO C3 with `web_server.log: true`

- **Date:** 2026-06-17
- **Severity:** near-OOM, worst case a reboot
- **Status:** ⚠ **Operator's open decision** — works for now; at the first reboot, roll back

**Symptom.** In the UART/OTA log:
```
[E][web_server:198]: json:111: JSON document overflow
```

**Root cause.** The Debug Log panel in Web UI v3 (`web_server.log:
true`) subscribes to the `/events` SSE and serialises **every** log
message as a JSON event. On XIAO C3 with 400 KB SRAM (no PSRAM), under
a browser F5 storm + Wi-Fi flaps, the SSE buffer doesn't drain →
ArduinoJSON document overflow → near-OOM.

**Solution in the current firmware (`xiao-esp32-c3/radon_ha_gateway_c3.yaml`).**

On 2026-06-17 the user explicitly allowed `log: true` as an
exception for debugging convenience. The YAML contains a comment:

```yaml
web_server:
  version: 3
  port: 80
  log: true   # ⚠ EXCEPTION: on XIAO C3 the user left this as true for the
              # native logs tab in Web UI. If reboots / json:111 / OOM appear —
              # switch back to false without asking again.
```

**If you hit json:111 on your own board** — switch to `log: false`,
recompile, reflash. The Debug Log panel disappears from Web UI, but
sensors, sorting_groups, and the API stay intact.

### INC-RADON-SCAN-RESONANCE — resonance of scan_parameters with the adv period

- **Date:** 2026-06-12 (conclusions migrated from the neighbouring skill `atomfast-esp32`)
- **Severity:** «silent» Wi-Fi failure under long runs
- **Status:** ✅ **Mitigated** by the YAML's default scan_parameters

**Symptom.** With `esp32_ble_tracker.scan_parameters: interval` ≈
`1000ms` (= RadonEye Plus2 advertising period) — phase beating,
periodic air-time dropouts, Wi-Fi-stack starvation on the single
radio. After 30+ minutes: BLE notify keeps coming, but Wi-Fi is dead
(no ping, no HTTP, no reboot loop).

**Solution in the current YAMLs.**

In both `radon_ha_gateway.yaml` and `radon_ha_gateway_c3.yaml` the
scan parameters are set so they do NOT coincide with the 1-second adv
period:

```yaml
esp32_ble_tracker:
  scan_parameters:
    interval: 640ms      # not a divisor of 1000ms, no phase lock
    window: 32ms         # 5 % duty cycle
    active: true         # active scan (scan-response request). Extra
                         # air-time vs BLE-WiFi coex, but improves
                         # Plus2 discovery and ble_client.connect()
                         # stability. See actual YAML
                         # (esp32-classic/radon_ha_gateway.yaml:166,
                         # xiao-esp32-c3/radon_ha_gateway_c3.yaml:125).
```

⚠ **Don't** change scan_parameters to `1000ms / 100ms` or `500ms /
50ms` — that brings the resonance back.

### INC-RADON-NARODMON-ALWAYS-OFF — the Narodmon switch MUST restore to OFF

- **Date:** 2026-06-17 (project HARD rule)
- **Severity:** privacy / policy
- **Status:** ✅ Locked in the YAML

**Symptom.** After reboot / safe-mode / factory_reset / OTA, the
«Upload to Narodmon» switch in Web UI restores to the **on** state, and
the ESP starts sending data to narodmon.ru without the user's
confirmation.

**Root cause.** ESPHome `switch.template` by default uses
`restore_mode: RESTORE_DEFAULT_OFF` — meaning «restore the last value,
default OFF». If NVS contained `ON` (the user once enabled it for a
test, then reflashed without `esphome clean` or with an NVS migration)
— after OTA the switch restores to `ON`.

**Solution in the current YAMLs.**

In both `radon_ha_gateway.yaml` and `radon_ha_gateway_c3.yaml` — a HARD
rule:

```yaml
- platform: template
  name: "Выгружать на Народмон"
  id: narodmon_enabled
  restore_mode: ALWAYS_OFF     # ← guaranteed OFF after reboot/safe-mode/OTA
  optimistic: true
```

⚠ **Never** change to `RESTORE_DEFAULT_OFF`,
`RESTORE_INVERTED_DEFAULT_OFF`, or `ALWAYS_ON`. Details — in the ESP32
project's `CLAUDE.md`, section «Switch «Выгружать на Народмон» —
restore_mode: ALWAYS_OFF».

---

## 4. Common installation errors

### `Invalid key format, please check it's using base64`

The most common first-install error. Full breakdown — in
[INSTALL.en.md](INSTALL.en.md), Troubleshooting section **0**.

Short fix: generate a valid `api_encryption_key` with

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

and put it into `secrets.yaml` in place of the placeholder `0000…==`.

### The other 11 typical install errors

See [INSTALL.en.md](INSTALL.en.md), section **Troubleshooting** — 12
numbered items:

0. Invalid key format (MOST COMMON)
1. Board not detected as a COM port
2. `esphome compile` fails with `UnicodeDecodeError`
3. `esphome upload`: «Failed to connect to ESP32»
4. After flashing, the board reboots in a loop
5. Web UI opens but has no cards
6. `BLE: RadonEye connected = OFF`
7. `WiFi: Auth Expired` every few seconds
8. `json:111: JSON document overflow` + empty Web UI
9. OTA stops working after a password change
10. Claude Code can't run commands with the right encoding (Windows)
11. ESP sees multiple `FR:PD…` devices (not yours)

---

## 5. Related projects / cross-references

- [atomfast-esp32 KNOWN_ISSUES](https://github.com/VibeEngineering-LLC/atomfast-esp32/blob/main/KNOWN_ISSUES.md) — analogous reference for AtomFast Plus2 (γ-dosimeter).
- [radex-esp32 KNOWN_ISSUES](https://github.com/VibeEngineering-LLC/radex-esp32/blob/main/KNOWN_ISSUES.md) — analogous reference for Radex MR107ion (also radon, but READ-poll).
- [Narodmon.ru](https://narodmon.ru/) — public crowdsourced sensor network; upload protocol documented on the project site.
- [Issues tracker](https://github.com/VibeEngineering-LLC/radoneye-esp32/issues) — file new issues or matrix additions here.
