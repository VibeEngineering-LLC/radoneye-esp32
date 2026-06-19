# INSTALL — RadonEye Plus2 → ESP32 → Home Assistant

> 🇷🇺 Русская версия: [INSTALL.md](INSTALL.md)

Build and install from scratch. Written for a customer who has never
worked with ESPHome before.

Time budget: **~20–30 minutes** (most of it spent waiting for the
ESPHome toolchain to download during the first compile and the first OTA).

---

## 0. What you'll need

### Physical hardware

Pick one of two boards:

| Board | When to pick | Where to buy (approx.) |
|---|---|---|
| **Seeed Studio XIAO ESP32-C3** ⭐ | Production-ready gateway for **one** RadonEye Plus2. Mini form factor ≈ 22×18 mm, USB-C, ~$5. | Seeed/AliExpress «XIAO ESP32-C3», ~$5 |
| **ESP32-DevKitC v4 (WROOM-32)** | If you already own one, or want the legacy baseline with up to 3 devices supported. USB-microB. | Any DIY shop, ~$8 |

Plus:
- USB cable (Type-C for XIAO C3, micro-USB for DevKitC v4) — ideally the same one the board ships with (OEM bundles often include a charge-only cable with no data lines; `esphome upload` won't see the port over those).
- The actual **RadonEye Plus2 (RD200PLUS)** — the BLE-capable version (`FR:PD…` prefix in advertising).
- A 2.4 GHz Wi-Fi access point with a known password (neither board supports 5 GHz).
- (Optional) Home Assistant — to receive sensors via the ESPHome API.

### Software

Any of the platforms below:

- **Windows 10/11** — this is the reference instruction; all command examples are PowerShell.
- macOS / Linux — commands differ in `sudo`, the path to `esphome`, and the fact that Python comes from `brew`/`apt`. The logic is identical.

---

## 1. Install ESPHome (Python 3.10+)

ESPHome is a Python package. On Windows, the simplest path is the system
Python from python.org (NOT the Microsoft Store one — that Python is
sandboxed and `esphome.exe` won't appear on PATH).

```powershell
# 1.1. Download Python 3.10+ from https://www.python.org/downloads/
#      In the installer, enable "Add python.exe to PATH".

# 1.2. Install ESPHome:
python -m pip install --upgrade pip
python -m pip install esphome

# 1.3. Verify:
esphome version
```

If `esphome` is not found on PATH (common on Windows when the username
contains Cyrillic characters) — use the full path:

```
C:\Users\<your_username>\AppData\Local\Programs\Python\Python312\Scripts\esphome.exe
```

(Throughout this guide, `esphome` is shorthand — substitute the full path
if PATH resolution doesn't work.)

---

## 2. Clone the skill

```powershell
git clone https://github.com/VibeEngineering-LLC/radoneye-esp32.git
cd radoneye-esp32\firmware\
```

If you don't use git — download the ZIP from
[github.com/VibeEngineering-LLC/radoneye-esp32](https://github.com/VibeEngineering-LLC/radoneye-esp32),
unpack it, and `cd radoneye-esp32-main\firmware\` in PowerShell.

Inside `firmware/`:

```
firmware/
├── esp32-classic/         radon_ha_gateway.yaml        (baseline ESP32-DevKitC, arduino)
├── xiao-esp32-c3/         radon_ha_gateway_c3.yaml     (current, XIAO ESP32-C3, arduino)
├── secrets.example.yaml   (shared secrets template)
├── CHANGELOG.md
└── .gitignore
```

---

## 3. Create `secrets.yaml`

In the `firmware/` folder:

```powershell
Copy-Item secrets.example.yaml secrets.yaml
notepad secrets.yaml
```

Fill in six fields:

| Field | What to put |
|---|---|
| `wifi_ssid` | SSID of your home 2.4 GHz network (case-sensitive). |
| `wifi_password` | Wi-Fi password. |
| `ap_password` | Any string ≥8 characters. The captive portal asks for this if the ESP fails to join your home Wi-Fi. |
| `api_encryption_key` | Generate with the command below — **base64 of 32 bytes**, ends with `==`. |
| `ota_password` | Any long string. Used both as the OTA password and the Web UI Basic Auth password. |
| `radon1_mac` | Can stay as the `AA:BB:CC:DD:EE:FF` placeholder — set the real MAC via Web UI after the first boot. |

### Generate `api_encryption_key`

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Copy the full output (including trailing `=` signs) into `secrets.yaml`.

> **⚠ Warning!** `api_encryption_key` MUST be valid base64 of 32 bytes.
> If you leave the placeholder `0000000000000000000000000000000000000000000==`
> or paste an arbitrary string — ESPHome boots into a loop with
> `Invalid key format, please check it's using base64`. See Troubleshooting
> section **0** below.

### Generate a strong `ota_password`

```powershell
python -c "import secrets; print(secrets.token_urlsafe(18))"
```

---

## 4. Pick a board variant

### Variant A — XIAO ESP32-C3 (recommended, 2026-06-17)

**Chip:** ESP32-C3 single-core RISC-V 160 MHz.
**Flash:** 4 MB. **RAM:** 400 KB.
**USB:** Type-C (native CDC, **not** through CH340/CP210).
**Antenna:** built-in PCB antenna on the board.

**YAML:** `xiao-esp32-c3/radon_ha_gateway_c3.yaml`.

**What's inside:** BLE client to one RadonEye Plus2, Web UI v3 + Basic Auth +
sorting_groups (5 groups: Sensors / BLE / Actions / Narodmon / Diag),
ESPHome API encryption, WiFi watchdog, **Narodmon infrastructure with
`restore_mode: ALWAYS_OFF`** (HARD).

### Variant B — ESP32-DevKitC v4 (baseline)

**Chip:** classic ESP32 dual-core 240 MHz.
**Flash:** 4 MB. **RAM:** 520 KB.
**USB:** micro-USB through CH340C / CP210x (Windows drivers — installed
automatically on first plug-in).
**Antenna:** built-in PCB antenna on the WROOM-32 module.

**YAML:** `esp32-classic/radon_ha_gateway.yaml`.

**What's inside:** baseline firmware (ESP-IDF/arduino), Web UI BLE MAC
scanner, support for **up to 3 devices** (`radon1_mac` / `radon2_mac` /
`radon3_mac` in one gateway), RE mode (manual hex frame viewer for
developers). See [`CHANGELOG.en.md`](firmware/CHANGELOG.en.md).

---

## 5. Find the RadonEye Plus2 MAC (optional)

If you don't know the MAC — skip this step, leave
`radon1_mac: "AA:BB:CC:DD:EE:FF"` in `secrets.yaml`. The real MAC will
be picked up via Web UI after the first boot.

If you already know it (e.g. from nRF Connect or the FTLAB app) — enter
it in `radon1_mac` in UPPERCASE with colons, like `12:34:AB:CD:EF:00`.

---

## 6. Compile the firmware

In PowerShell, inside `firmware/`:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Variant A (XIAO C3):
esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml

# Variant B (DevKitC v4):
esphome compile esp32-classic/radon_ha_gateway.yaml
```

> **What happens.** The first compile downloads the PlatformIO toolchain
> (~500 MB) — can take **5–15 minutes** depending on your internet.
> Subsequent compiles take ~60–90 seconds. On XIAO C3 the resulting
> firmware uses ~85 % of Flash; on DevKitC — ~80 %.

The final `INFO Successfully compiled program.` message means the
compile is done.

---

## 7. Flash (first time — over USB)

Connect the board with a USB cable. On Windows, find the COM port:

```powershell
Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'CH340|CP210|FTDI|USB Serial|JTAG' }
```

XIAO C3 appears as **"USB JTAG/serial debug unit"** or **"USB Serial
Device"** (native CDC, no CH340); the port number is `COM<N>`.

```powershell
# Variant A:
esphome upload xiao-esp32-c3/radon_ha_gateway_c3.yaml --device COM<N>

# Variant B:
esphome upload esp32-classic/radon_ha_gateway.yaml --device COM<N>
```

After `Successfully uploaded` the board reboots. The flash is done.

> **Important about logs.** **DO NOT** run `esphome logs --device COM<N>` —
> on both XIAO C3 and DevKitC it reopens USB and toggles DTR/RTS, the
> board «jumps» and the BLE session drops every 5–10 seconds. Use
> **OTA logs**:
> `esphome logs xiao-esp32-c3/radon_ha_gateway_c3.yaml --device radon-gw.local`
> (once the board has joined Wi-Fi at least once).

---

## 8. First boot → captive portal → WiFi

If the board fails to join your home Wi-Fi (new firmware, SSID change,
captive timeout) — it brings up its own AP:

- **C3**: `radon-gw Fallback`
- **DevKitC**: `radon-ha Fallback`

The AP password is whatever you set in `ap_password`.

From your phone / laptop:

1. Connect to that AP.
2. If the captive portal doesn't open on its own — visit `http://192.168.4.1/`.
3. Pick your home Wi-Fi 2.4 GHz from the network list, enter the password → **Save**.
4. The ESP reboots; ~10 seconds later it joins your home Wi-Fi.

---

## 9. Web UI and RadonEye MAC binding

On your home network, from a PC or phone:

- **C3:** [`http://radon-gw.local/`](http://radon-gw.local/)
- **DevKitC:** [`http://radon-ha-gateway.local/`](http://radon-ha-gateway.local/)

If `.local` doesn't resolve (some corporate DNS / routers without mDNS) —
find the IP in your router admin by the board's MAC and open
`http://<IP>/`.

Basic Auth login/password:
- **C3:** `radon` / `<ota_password>`
- **DevKitC:** `admin` / `<ota_password>`

In the Web UI:

1. Group **«Поиск BLE» (BLE scan)** → button **«Запустить скан 30 с»** (Run scan 30 s).
2. In the results, find a `FR:PD<serial>` row — that's your RadonEye Plus2.
3. Copy the MAC.
4. Paste it into **«MAC Radon 1»**.
5. Click **«Применить MAC и перезагрузить»** (Apply MAC and reboot).

After reboot, the **«Sensors»** group will show:
- Radon Bq/m³ (instant, updated every 10 minutes)
- Peak (lifetime maximum stored in the device)
- Count (measurement number since the device booted)
- Temperature from history
- Rolling hour/day averages

---

## 10. Connect to Home Assistant

In Home Assistant:

1. **Settings → Devices & Services → Add Integration → ESPHome**.
2. Host: `radon-gw.local` (C3) or `radon-ha-gateway.local` (DevKitC), or the IP.
3. Encryption key: the same `api_encryption_key` from `secrets.yaml`.
4. **Submit** → wait for «Discovered new device».
5. Assign an **Area** (e.g. «Bedroom»).

All entities appear automatically:
`sensor.radon_instant_bq_m3`, `sensor.radon_peak`, `sensor.radon_count`,
`sensor.radon_temperature_c`, `sensor.radon_avg_hour`, `sensor.radon_avg_day`,
`binary_sensor.radon_ble_connected`, `sensor.radon_rssi`, etc.

---

## 11. Ready-made Claude Code prompt (for your next build)

If you use Claude Code (claude.ai/code) — paste this prompt verbatim,
filling in your data:

```
Help me set up a RadonEye → Home Assistant gateway on ESP32.

Hardware:
- Board: XIAO ESP32-C3  (or ESP32-DevKitC v4)
- Device: RadonEye Plus2 (RD200PLUS), MAC unknown yet — we'll pick it up via Web UI

What I've already done:
- Python 3.12 + ESPHome installed; "esphome version" works.
- Skill cloned to C:\Users\<name>\claude-skills\radoneye-esp32\

What I need:
1. Help me create secrets.yaml from secrets.example.yaml. Generate:
   - api_encryption_key (base64, 32 bytes)
   - ota_password (>=18 characters)
2. Compile xiao-esp32-c3/radon_ha_gateway_c3.yaml (or
   esp32-classic/radon_ha_gateway.yaml).
3. Find the COM port, flash it.
4. Explain how to set Wi-Fi through the captive portal.
5. Explain how to find the device MAC through the ESP Web UI and bind it.
```

---

## Troubleshooting (common install errors)

### 0. `Invalid key format, please check it's using base64` (MOST COMMON)

**Symptom.** ESP boot hangs; UART/OTA log loops:
```
[E][api]: Invalid key format, please check it's using base64
[E][api]: Initialization failed
```

**Root cause.** `api_encryption_key` in `secrets.yaml` is not a valid
base64 encoding of 32 random bytes. The most common reason — the
placeholder `0000000000000000000000000000000000000000000==` was left in
place (it's 32 bytes, BUT all zeros — ESPHome 2025.8+ rejects it).

**Fix.** Generate a real key:

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Copy the entire output (including the trailing `==`) into
`secrets.yaml`, field `api_encryption_key`. Recompile (`esphome
compile …`) — ESPHome rebuilds the firmware with the new key. Reflash.
In Home Assistant, in the integration, enter the same key.

### 1. Board not detected as a COM port

**Symptom.** `Get-CimInstance Win32_PnPEntity | Where { $_.Name -match 'CH340|CP210|JTAG|USB Serial' }` returns nothing.

**Fix.**
- Charge-only USB cable (no data lines) — common with charging cables. Swap it.
- On DevKitC: install the CH340/CP210x driver (`https://www.wch.cn/downloads/CH341SER_EXE.html` for CH340C). Replug the board after install.
- On XIAO C3: should work out of the box (native CDC). If not — update Windows to build ≥ 19041, install the «Universal Serial Bus controllers → USB Composite Device» driver manually.

### 2. `esphome compile` fails with `UnicodeDecodeError`

**Symptom.**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd0 in position …
```

**Root cause.** The path to secrets / YAML contains Cyrillic characters,
and Python didn't get `PYTHONIOENCODING=utf-8`.

**Fix.** In PowerShell **before each** `esphome` command:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

In Bash (Git Bash):

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 esphome compile ...
```

### 3. `esphome upload`: «Failed to connect to ESP32»

**Symptom.** `esphome upload` shows progress and times out:
```
A fatal error occurred: Failed to connect to ESP32: Wrong boot mode detected (0x13)!
```

**Fix per board.**
- **DevKitC v4:** the board doesn't enter bootloader on its own. Press-and-hold `BOOT`, briefly press `EN`, release `BOOT`. Retry `esphome upload`.
- **XIAO ESP32-C3:** if USB-CDC isn't responding — short `GND ↔ BOOT pad` while plugging in the USB cable. After flashing, briefly press RESET.

### 4. After flashing, the board reboots in a loop

**Symptom.** UART / OTA log:
```
[E][component:182]: Component web_server cleared Warning flag
Boot loop detected after 3 attempts, entering safe mode
```

**Fix.**
- If the log shows `[E][api]: Invalid key format` before the reboot — see Troubleshooting **0**.
- If the log shows `Guru Meditation Error: StoreProhibited` — likely a bug or an incompatible ESPHome (use 2025.8.0+ as required by `min_version`). Upgrade: `python -m pip install --upgrade esphome`.

### 5. Web UI opens but has no cards / groups

**Symptom.** `http://radon-gw.local/` returns an empty HTML with a header, no sensor cards.

**Fix.**
- Browser cached the old ESPHome bundle. **Ctrl+Shift+R** (hard reload).
- Open DevTools (F12) → Console — check JS errors. If «Mixed Content blocked» — open the Web UI explicitly over `http://`, not `https://`.

### 6. `BLE: RadonEye connected = OFF` (after MAC binding)

**Symptom.** In the Web UI, the Sensors group shows «—» for Radon Bq/m³, the BLE group says «not connected».

**Causes (in order of likelihood).**

1. **RadonEye is occupied by the phone.** Plus2 is **single-central**: while a session with the FTLAB/Ecosense app is active, the ESP gets a «refuse». Fully close the app (force-stop), wait 30 seconds, click «Reconnect» in the Web UI.
2. **MAC typo.** Open Web UI «BLE scan» → «Run scan 30 s» → compare bytes.
3. **Device not in the Plus2 family.** This firmware only targets RD200PLUS (`FR:PD…` advertising prefix). RadonEye RD200 V1/V2 is a different protocol. See README → «Which RadonEye models work».
4. **Distance > 5 m or a wall.** RSSI < −85 dBm — the session drops every few seconds. The BLE group shows the RSSI; below −75 dBm — move the ESP closer, or attach an external U.FL antenna (the U.FL variants of DevKitC).

### 7. `WiFi: Auth Expired` every few seconds

**Symptom.** UART:
```
[W][wifi]: Auth Expired
[D][wifi]: Connecting…
…
[W][wifi]: Auth Expired
```

**Fix.**
- Check `wifi_password` — especially if it contains `$`, `#`, quotes. In `secrets.yaml`, double-quoted strings support escapes, single-quoted ones don't.
- A home router with **band steering** (single SSID for 2.4 + 5 GHz): the ESP32 tries to join the 5 GHz radio, fails, loops. Solution — split off a 2.4 GHz-only SSID (no steering), or pin `bssid:` in the YAML to the 2.4 GHz BSSID.

### 8. `json:111: JSON document overflow` + empty Web UI

**Symptom.** UART/OTA log:
```
[E][web_server:198]: json:111: JSON document overflow
```

**Root cause.** The Debug Log panel in Web UI v3 subscribes to the
`/events` SSE and serialises EVERY log message as a separate JSON event.
On XIAO C3 with `web_server.log: true`, this hits near-OOM.

**Fix.** In the XIAO C3 YAML (`xiao-esp32-c3/radon_ha_gateway_c3.yaml`)
`log: true` is left as an exception for diagnostics
convenience. If the C3 starts rebooting / `json:111` / OOM — switch to
`log: false`:

```yaml
web_server:
  version: 3
  port: 80
  log: false   # ← was true, switch to false
```

Recompile, reflash. The Debug Log panel disappears from the Web UI, but
sensors, sorting_groups, and the API stay intact.

### 9. OTA stops working after a password change

**Symptom.** `esphome upload … --device radon-gw.local` fails:
```
ERROR Authentication failed
```

**Root cause.** The Web UI Basic Auth cached old credentials, and the
OTA endpoint uses the same `ota_password`. After replacing
`ota_password` in `secrets.yaml` you need to either:

- Reflash over USB (physical connection, `--device COM<N>`) at least once with the new password — after that, OTA with the new password works.
- OR flash via the old OTA password (if you still remember it), then reboot — the new password takes effect.

⚠ The project's CLAUDE.md has a HARD rule: «Web auth must not change
between steps on the same IP» — otherwise the browser caches the old
auth and after OTA gets a 401 with no prompt. This applies because Web
auth password = ota_password in the current YAMLs.

### 10. Claude Code can't run commands with the right encoding (Windows)

**Symptom.** Running a PowerShell command with Cyrillic in the path via
Claude Code — `UnicodeDecodeError` / gibberish in stdout.

**Fix.** In your PowerShell call, wrap Python scripts and `esphome` like
this:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml
```

For a single Bash command:

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 esphome compile xiao-esp32-c3/radon_ha_gateway_c3.yaml
```

### 11. ESP sees multiple `FR:PD…` devices (not yours)

**Symptom.** In the Web UI «BLE scan» group — multiple `FR:PD<serial>`
results (neighbour's RadonEye).

**Fix.**
- Verify the serial: on the device itself — in the «Information» menu (Plus2 shows the Serial).
- A neighbour's device — won't connect to your firmware anyway (single-central, occupied by the neighbour's phone, or simply refuses an unknown MAC).
- Uniqueness comes from specifying the **exact MAC** in `radon1_mac` (the gateway's BLE scanner connects only to that MAC).

---

## Related documents

- [README.en.md](README.en.md) — skill overview, Plus2 BLE protocol.
- [SKILL.md](SKILL.md) — full firmware-developer knowledge base (Russian).
- [KNOWN_ISSUES.en.md](KNOWN_ISSUES.en.md) — board compatibility matrix and incidents.
- [firmware/CHANGELOG.en.md](firmware/CHANGELOG.en.md) — firmware version history.
- [references/plus2_protocol.md](references/plus2_protocol.md) — BLE protocol reverse-engineering (Russian).
