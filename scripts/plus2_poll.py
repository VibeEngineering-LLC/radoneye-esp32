#!/usr/bin/env python3
"""plus2_poll.py — multi-sample опроса RadonEye Plus2 через BT компьютера (bleak).

Пишет опкод 0x50 N раз с паузой, ловит notify на 1525/1526 и печатает КАЖДЫЙ кадр
в ДВУХ интерпретациях сразу (uint16 LE Bq/m3 vs float32 LE pCi/L), чтобы по
стабильности значений однозначно определить формат Plus2. Опкод 0x50 — whitelist.

Usage (bleak требует Python 3.12):
    python3.12 plus2_poll.py
    python3.12 plus2_poll.py --n 6 --gap 3
    python3.12 plus2_poll.py --addr AA:BB:CC:DD:EE:FF   # либо подхват по имени FR:PD
    # Windows: py -3.12 plus2_poll.py ...
"""
from __future__ import annotations
import sys, asyncio, struct, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bleak import BleakScanner, BleakClient

# MAC прибора приватный → placeholder. Реальный прибор находится по NAME_PREFIX
# (adv local_name начинается с "FR:PD") либо задаётся флагом --addr.
ADDR = "AA:BB:CC:DD:EE:FF"
NAME_PREFIX = "FR:PD"
WRITE_UUID = "00001524-1212-efde-1523-785feabcd123"
frames = []


def hexs(b):
    return " ".join("%02x" % x for x in b)


def u16(b, o):
    return struct.unpack("<H", b[o:o + 2])[0] if len(b) >= o + 2 else None


def f32(b, o):
    return struct.unpack("<f", b[o:o + 4])[0] if len(b) >= o + 4 else None


def cb(_c, data):
    data = bytes(data)
    frames.append((time.time(), data))
    op = data[0] if data else None
    print("  NOTIFY len=%d : %s" % (len(data), hexs(data)))
    if op == 0x50:
        # две гипотезы
        bq = u16(data, 2)
        fl = f32(data, 2)
        print("     [uint16 Bq] cur=%s Bq (=%.3f pCi/L)  day=%s  month=%s  | pulse@14=%s pulse@16=%s" % (
            bq, (bq / 37.0 if bq is not None else 0), u16(data, 4), u16(data, 6), u16(data, 14), u16(data, 16)))
        print("     [float32  ] cur=%.4f pCi/L  (если ~0 при ненулевом uint16 -> формат uint16)" % (fl if fl is not None else 0))


async def find_device(addr, name_prefix, timeout=12.0):
    """Находит прибор по точному MAC ИЛИ по префиксу adv-имени (FR:PD…).
    Так скрипт работает с placeholder-MAC: реальный прибор подхватывается по имени."""
    found = {}

    def det_cb(dev, adv):
        nm = adv.local_name or dev.name or ""
        if dev.address.upper() == addr.upper() or (name_prefix and name_prefix in nm):
            found.setdefault(dev.address, (dev, nm, adv.rssi))

    scanner = BleakScanner(detection_callback=det_cb)
    await scanner.start()
    t0 = time.time()
    while time.time() - t0 < timeout:
        if any(d.address.upper() == addr.upper() for d, _n, _r in found.values()):
            break
        await asyncio.sleep(0.4)
    await scanner.stop()
    for dev, nm, rssi in found.values():
        if dev.address.upper() == addr.upper():
            return dev
    return list(found.values())[0][0] if found else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=ADDR, help="точный MAC; по умолчанию placeholder → скан по имени FR:PD")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--gap", type=float, default=3.0)
    args = ap.parse_args()

    print("[scan] addr=%s / name~%s ..." % (args.addr, NAME_PREFIX))
    dev = await find_device(args.addr, NAME_PREFIX)
    if dev is None:
        print("RESULT: устройство не найдено")
        return
    print("[connect] %s" % dev.address)
    async with BleakClient(dev) as client:
        print("[connect] connected=%s" % client.is_connected)
        # подписка на обе notify-характеристики
        for u in ("00001525-1212-efde-1523-785feabcd123", "00001526-1212-efde-1523-785feabcd123"):
            try:
                await client.start_notify(u, cb)
                print("[notify] subscribed %s" % u)
            except Exception as ex:
                print("[notify] FAIL %s : %r" % (u, ex))
        for i in range(args.n):
            print("[write] #%d opcode=0x50 -> %s" % (i + 1, WRITE_UUID))
            try:
                await client.write_gatt_char(WRITE_UUID, b"\x50", response=True)
            except Exception as ex:
                print("[write] FAIL : %r" % ex)
            await asyncio.sleep(args.gap)
        await asyncio.sleep(1.0)

    print()
    print("=== ИТОГО кадров: %d ===" % len(frames))
    cur_seq = []
    for _ts, d in frames:
        if d and d[0] == 0x50:
            cur_seq.append(u16(d, 2))
    print("Последовательность current[2:4] uint16 Bq:", cur_seq)


if __name__ == "__main__":
    asyncio.run(main())