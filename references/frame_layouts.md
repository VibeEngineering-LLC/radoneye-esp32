# Frame layouts — byte-by-byte map

Маппинг получен **живой stability-diff'ом** 3 последовательных frame
`0x51` с интервалом 4 секунды на a RD200PLUS device (Plus2 family) в Phase 9
сессии 2026-06-07. Frames `0x50` декодированы по `sormy/radoneye/KNOWLEDGE_V1.md`
и подтверждены против ground-truth от приложения FTLAB Connect
(real-time = 0 ± 27 Bq/m³).

## 0x50 RADON — 20 bytes

| Byte | Field | Type | Stability | Notes |
|------|-------|------|-----------|-------|
| 0 | opcode_echo | u8 | STABLE | always `0x50` |
| 1 | payload_len | u8 | STABLE | always `0x10` (=16) |
| 2-5 | current_pCi_L | f32 LE | dynamic | current radon — обновляется каждый sample |
| 6-9 | day_avg_pCi_L | f32 LE | slow | day average |
| 10-13 | month_avg_pCi_L | f32 LE | very slow | month average |
| 14-15 | cur_count | u16 LE | dynamic | sample counter, растёт с каждым sample |
| 16-17 | prev_count | u16 LE | slow | previous counter |
| 18-19 | trailer | bytes | DYNAMIC | observed: `0230`, `0f38` — unknown, не end-marker |

## 0x51 UPTIME+PEAK — 20 bytes (Plus2-extended)

> ⚠ На классических RD200 payload_len = `0x0E` (14). На Plus2 firmware
> rev 2026-06 payload_len = `0x12` (18) — на 4 байта длиннее. Эти 4
> «extra» байта — назначение неизвестно, см. KNOWN-UNKNOWNS.

| Byte | Field | Type | Stability | Notes |
|------|-------|------|-----------|-------|
| 0 | opcode_echo | u8 | STABLE | always `0x51` |
| 1 | payload_len | u8 | STABLE | `0x12` on Plus2 (`0x0E` on V1 baseline) |
| 2-3 | unknown | u16 LE | STABLE | observed `01 00` consistently |
| 4-5 | uptime_minutes | u16 LE | CHANGED+1/min | ✓ verified — `21 00`→`22 00` пересекая минутную границу |
| 6-7 | reserved? | u16 LE | STABLE | observed `00 00` |
| 8-11 | unknown A | bytes | STABLE-12s, CHANGED-8min | возможно sample-related counter |
| 12-15 | peak_pCi_L | f32 LE | STABLE | ✓ verified — на ровных нулях даёт ≈ 0 |
| 16-18 | unknown B | bytes | STABLE | observed `07 0D 0F` неизменно |
| 19 | second_byte | u8 | CHANGED +1/s | ✓ live-verified +4 per 4-second interval — seconds-within-minute |

### Diff таблица (3 frames с интервалом 4с)

Полная стенограмма из Phase 9, 2026-06-07:

```
idx | stable? | f0_t=0.038s | f1_t=4.177s | f2_t=8.198s
[ 0] STABLE    51 51 51   (opcode)
[ 1] STABLE    12 12 12   (payload_len)
[ 2] STABLE    01 01 01
[ 3] STABLE    00 00 00
[ 4] CHANGED!  21 21 22   uptime_minutes_LE  (33→33→34, минута щёлкнула)
[ 5] STABLE    00 00 00   uptime_minutes_LE high byte
[ 6] STABLE    00 00 00
[ 7] STABLE    00 00 00
[ 8] STABLE    B1 B1 B1   unknown A
[ 9] STABLE    08 08 08   unknown A
[10] STABLE    08 08 08   unknown A
[11] STABLE    00 00 00   unknown A
[12] STABLE    A5 A5 A5   peak f32 byte 0
[13] STABLE    18 18 18   peak f32 byte 1
[14] STABLE    1A 1A 1A   peak f32 byte 2
[15] STABLE    06 06 06   peak f32 byte 3
[16] STABLE    07 07 07   unknown B
[17] STABLE    0D 0D 0D   unknown B
[18] STABLE    0F 0F 0F   unknown B
[19] CHANGED!  30 34 38   seconds (0x30=48, +4 каждые 4с)
```

## Ground truth от FTLAB Connect (iPhone)

В момент Phase 8 (uptime ≈ 25 min):
- Temperature: **24.5 °C**
- Humidity: **37 %**
- Real-time radon: **0 ± 27 Bq/m³** ✓ совпадает с нашим `current_pCi_L = 0.0`
- Peak: **----** (нет данных) ✓ совпадает с `peak ≈ 0`
- Meas.Time: **00:27** (27 min — сходится с нашим uptime в пределах 2 мин)
- Data No (history): **9600** (≈ 400 дней × 1 час шаг)

**Маппинга для 24.5°C / 37% в кадре `0x51` найти НЕ удалось.** Ни одно
поле bytes 8-11 или 16-18 не декодируется в эти значения каким-либо
тривиальным форматом (u8, u16 LE, u16 LE / 100, fixed-point /16). См.
`temp_humidity_research.md` — почему правильный путь HCI snoop с Android.

## Источники

- sormy/radoneye KNOWLEDGE_V1.md (primary)
- jdeath/rd200v2 parser.py (cross-check)
- lopsided98/radoneye-ble (UUID confirmation)
- Live capture session 2026-06-07 on a RD200PLUS device (this rig)
