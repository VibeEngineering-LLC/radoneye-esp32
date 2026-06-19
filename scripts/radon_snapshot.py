# -*- coding: utf-8 -*-
"""
RadonEye Plus2 / RD200P / Plus3 — production snapshot via V1 BLE protocol.

Reads:
  - current/day/month radon avg via opcode 0x50
  - uptime (min + sec byte) and peak via opcode 0x51

Tested live on a RD200PLUS device (Plus2 family) on 2026-06-07.

Usage:
    python radon_snapshot.py                 # single snapshot
    python radon_snapshot.py --watch 24      # 24 snapshots
    python radon_snapshot.py --watch 24 --interval 3600   # hourly for 24h
    python radon_snapshot.py --mac AA:BB:CC:DD:EE:FF
    RADONEYE_MAC=AA:BB:CC:DD:EE:FF python radon_snapshot.py

Output: stdout + append to --out path (default radon_snapshots.jsonl).
Each line is a self-contained JSON record with timestamp_utc, radon, uptime_peak.

Constraints (read SKILL.md anti-patterns BEFORE editing):
  - Do NOT add probe opcodes outside the V1 whitelist.
    Opcodes in 0xA0..0xCF range have triggered DFU mode in the wild.
  - Do NOT keep the BLE central role longer than needed — the device allows
    exactly one central at a time, and a held connection blocks the phone app.
  - Do NOT decode temperature/humidity from bytes 12/13 of 0x51 — those are
    the peak f32, not temp/hum. See references/temp_humidity_research.md.

Requires: bleak (pip install bleak)
"""
import sys
import os
import asyncio
import struct
import json
import argparse
import traceback
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
from bleak import BleakClient

DEFAULT_MAC = os.environ.get("RADONEYE_MAC", "AA:BB:CC:DD:EE:FF")  # replace via env or --mac

# V1 protocol GATT characteristics (custom service 1523)
CMD_CHAR    = "00001524-1212-efde-1523-785feabcd123"  # write opcodes here
NOTIFY_1525 = "00001525-1212-efde-1523-785feabcd123"  # primary notify
NOTIFY_1526 = "00001526-1212-efde-1523-785feabcd123"  # secondary notify

PCI_TO_BQ = 37.0


async def _write_and_wait(client, opcode, wait=1.5):
    await client.write_gatt_char(CMD_CHAR, bytes([opcode]), response=False)
    await asyncio.sleep(wait)


def decode_0x50(b: bytes) -> dict:
    """RADON frame: echo=0x50, len=0x10, then floats and counters."""
    cur = struct.unpack('<f', b[2:6])[0]
    day = struct.unpack('<f', b[6:10])[0]
    mon = struct.unpack('<f', b[10:14])[0]
    return {
        "current_pCi_L":   round(cur, 4),
        "current_Bq_m3":   round(cur * PCI_TO_BQ, 2),
        "day_avg_pCi_L":   round(day, 4),
        "day_avg_Bq_m3":   round(day * PCI_TO_BQ, 2),
        "month_avg_pCi_L": round(mon, 4),
        "month_avg_Bq_m3": round(mon * PCI_TO_BQ, 2),
        "cur_count":       struct.unpack('<H', b[14:16])[0],
        "prev_count":      struct.unpack('<H', b[16:18])[0],
    }


def decode_0x51(b: bytes) -> dict:
    """UPTIME+PEAK frame: echo=0x51, then uptime u16 and peak f32.

    On Plus2 firmware (rev 2026-06) length is 0x12 (18) with 4 trailing bytes
    whose meaning is unknown; byte 19 is observed to tick as seconds-within-minute
    (verified live: +4 per 4-second interval). See references/frame_layouts.md.
    """
    uptime_min = struct.unpack('<H', b[4:6])[0]
    sec_byte = b[19] if len(b) >= 20 else 0
    peak = struct.unpack('<f', b[12:16])[0]
    return {
        "uptime_minutes": uptime_min,
        "uptime_hours":   round(uptime_min / 60.0, 2),
        "uptime_days":    round(uptime_min / 1440.0, 2),
        "second_byte":    sec_byte,
        "peak_pCi_L":     round(peak, 4),
        "peak_Bq_m3":     round(peak * PCI_TO_BQ, 2),
    }


async def snapshot(mac: str) -> dict:
    notifies: list[bytes] = []

    def handler(_sender, data):
        notifies.append(bytes(data))

    out = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        "mac": mac,
        "model_hint": "RD200PLUS-or-V1-compatible",
    }
    try:
        async with BleakClient(mac, timeout=15.0) as client:
            if not client.is_connected:
                out["error"] = "not connected (phone app may hold the central role)"
                return out
            await client.start_notify(NOTIFY_1525, handler)
            await client.start_notify(NOTIFY_1526, handler)
            await asyncio.sleep(0.3)  # CCCD settle

            await _write_and_wait(client, 0x50)
            await _write_and_wait(client, 0x51)

            try: await client.stop_notify(NOTIFY_1525)
            except Exception: pass
            try: await client.stop_notify(NOTIFY_1526)
            except Exception: pass
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    for n in notifies:
        if not n:
            continue
        oc = n[0]
        if oc == 0x50 and len(n) >= 18:
            out["radon"] = decode_0x50(n)
            out["radon"]["_raw_hex"] = n.hex()
        elif oc == 0x51 and len(n) >= 16:
            out["uptime_peak"] = decode_0x51(n)
            out["uptime_peak"]["_raw_hex"] = n.hex()

    return out


def fmt(snap: dict) -> str:
    if "error" in snap:
        return f"[{snap.get('timestamp_utc')}] ERROR {snap['mac']}: {snap['error']}"
    r = snap.get("radon", {})
    u = snap.get("uptime_peak", {})
    return "\n".join([
        f"[{snap['timestamp_utc']}] RadonEye {snap['mac']}",
        f"  Current : {r.get('current_pCi_L','?')} pCi/L  ({r.get('current_Bq_m3','?')} Bq/m³)",
        f"  Day avg : {r.get('day_avg_pCi_L','?')} pCi/L  ({r.get('day_avg_Bq_m3','?')} Bq/m³)",
        f"  Month   : {r.get('month_avg_pCi_L','?')} pCi/L  ({r.get('month_avg_Bq_m3','?')} Bq/m³)",
        f"  Peak    : {u.get('peak_pCi_L','?')} pCi/L  ({u.get('peak_Bq_m3','?')} Bq/m³)",
        f"  Counts  : cur={r.get('cur_count','?')}  prev={r.get('prev_count','?')}",
        f"  Uptime  : {u.get('uptime_minutes','?')} min  ({u.get('uptime_hours','?')} h, {u.get('uptime_days','?')} d)",
    ])


async def main():
    ap = argparse.ArgumentParser(description="RadonEye V1 BLE snapshot")
    ap.add_argument('--mac', default=DEFAULT_MAC,
                    help=f"Device MAC (default {DEFAULT_MAC}; or env RADONEYE_MAC)")
    ap.add_argument('--watch', type=int, default=1,
                    help="Number of snapshots (default 1)")
    ap.add_argument('--interval', type=int, default=60,
                    help="Seconds between snapshots when --watch >1 (default 60)")
    ap.add_argument('--out', default="radon_snapshots.jsonl",
                    help="Append-only JSONL log path")
    args = ap.parse_args()

    n = max(1, args.watch)
    for i in range(n):
        snap = await snapshot(args.mac)
        print(fmt(snap), flush=True)
        with open(args.out, 'a', encoding='utf-8') as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        if i < n - 1:
            print(f"  ...sleep {args.interval}s", flush=True)
            await asyncio.sleep(args.interval)
    print(f"\nSaved (append) → {args.out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
    except Exception:
        traceback.print_exc()
