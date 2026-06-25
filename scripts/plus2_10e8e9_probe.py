#!/usr/bin/env python3
"""plus2_10e8e9_probe.py - tshatelno snyat whitelist-opkody 0x10/0xE8/0xE9 RadonEye Plus2.

Оператор попросил «снять 0x10/0xE8/0xE9». Делаем по-настоящему:
  - сначала один 0x50 как маркер живости линка (отвечает -> линк жив);
  - затем по каждому из 0x10/0xE8/0xE9: 3 записи с длинным окном прослушки (10 с);
  - подписка на ОБЕ notify (1525 + 1526) - ловим любой канал ответа;
  - MAC/serial маскируются в выводе -> лог публикабелен.

WHITELIST HARD: пишем ТОЛЬКО {0x10, 0xE8, 0xE9} (+ 0x50 маркер). Всё в whitelist.
0xA0..0xCF вне whitelist -> DFU-RISK, НЕ трогать.

Usage (bleak требует Python 3.12):
    python3.12 plus2_10e8e9_probe.py
    # Windows: py -3.12 plus2_10e8e9_probe.py
"""
from __future__ import annotations
import sys, asyncio, struct, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bleak import BleakScanner, BleakClient

ADDR = "AA:BB:CC:DD:EE:FF"
NAME_PREFIX = "FR:PD"
WRITE_UUID = "00001524-1212-efde-1523-785feabcd123"
NOTIFY1 = "00001525-1212-efde-1523-785feabcd123"
NOTIFY2 = "00001526-1212-efde-1523-785feabcd123"

WHITELIST = {0x10, 0x50, 0x51, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}
PROBE = [0x10, 0xE8, 0xE9]
REPEATS = 3
WINDOW = 10.0


def _check_whitelist_or_abort(ops):
    bad = [op for op in ops if op not in WHITELIST]
    if bad:
        print("ABORT: opkody vne whitelist:", [hex(x) for x in bad])
        print("0xA0..0xCF -> DFU mode (vynut batareyki ~30s). Pravka PROBE bez probrosa cherez whitelist zapreschena.")
        sys.exit(2)

frames = []
T0 = None
_cur_op = None


def hexs(b):
    return " ".join("%02x" % x for x in b)


def mask_addr(a):
    return ":".join(["**"] * 5 + [a.split(":")[-1]]) if ":" in a else "***"


def mask_name(n):
    return (n[:5] + "****") if n else n


def cb_factory(tag):
    def cb(_c, data):
        data = bytes(data)
        dt = (time.time() - T0) if T0 else 0.0
        frames.append((dt, tag, _cur_op, data))
        print("    [%6.1fs] NOTIFY(%s) op=0x%02x len=%d : %s" % (dt, tag, _cur_op or 0, len(data), hexs(data)))
    return cb


async def find_device(addr, name_prefix, timeout=12.0):
    found = {}

    def det(dev, adv):
        nm = adv.local_name or dev.name or ""
        if dev.address.upper() == addr.upper() or (name_prefix and name_prefix in nm):
            found.setdefault(dev.address, (dev, nm, adv.rssi))

    sc = BleakScanner(detection_callback=det)
    await sc.start()
    t0 = time.time()
    while time.time() - t0 < timeout:
        if any(d.address.upper() == addr.upper() for d, _n, _r in found.values()):
            break
        await asyncio.sleep(0.4)
    await sc.stop()
    for dev, nm, rssi in found.values():
        if dev.address.upper() == addr.upper():
            return dev, nm, rssi
    return (list(found.values())[0] if found else (None, None, None))


async def write_and_listen(client, op, window):
    global _cur_op
    if op not in WHITELIST:    # двойная защита в цикле: PYTHONOPTIMIZE срежет assert, runtime — нет
        print("  [skip] op=0x%02x vne whitelist — propusk (DFU-RISK guard)" % op)
        return 0
    _cur_op = op
    n0 = len(frames)
    print("  [write] op=0x%02x  slushayu %.0f s..." % (op, window))
    try:
        await client.write_gatt_char(WRITE_UUID, bytes([op]), response=True)
    except Exception as ex:
        print("  [write] FAIL 0x%02x : %r" % (op, ex))
    await asyncio.sleep(window)
    got = len(frames) - n0
    print("  [write] op=0x%02x -> kadrov: %d" % (op, got))
    return got


async def main():
    global T0
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=ADDR)
    ap.add_argument("--window", type=float, default=WINDOW)
    args = ap.parse_args()

    # runtime страж whitelist (assert вырезается под python -O — нельзя полагаться)
    _check_whitelist_or_abort(PROBE + [0x50])

    print("[scan] addr=%s / name~%s ..." % (mask_addr(args.addr), NAME_PREFIX))
    dev, nm, rssi = await find_device(args.addr, NAME_PREFIX)
    if dev is None:
        print("RESULT: ustroistvo ne naideno (ESP-most derzhit link? pribor vne zony? telefon-prilozhenie podklyucheno?)")
        return
    print("[found] %s  name=%r  rssi=%s" % (mask_addr(dev.address), mask_name(nm), rssi))

    async with BleakClient(dev) as client:
        print("[connect] connected=%s" % client.is_connected)
        for u, tag in ((NOTIFY1, "1525"), (NOTIFY2, "1526")):
            try:
                await client.start_notify(u, cb_factory(tag))
                print("[notify] subscribed %s" % tag)
            except Exception as ex:
                print("[notify] FAIL %s : %r" % (tag, ex))

        T0 = time.time()
        print("\n=== MARKER ZHIVOSTI: 0x50 ===")
        await write_and_listen(client, 0x50, 4.0)

        for op in PROBE:
            print("\n=== OPKOD 0x%02x x %d ===" % (op, REPEATS))
            for i in range(REPEATS):
                print(" popytka %d/%d:" % (i + 1, REPEATS))
                await write_and_listen(client, op, args.window)

        await asyncio.sleep(1.0)
        for u in (NOTIFY1, NOTIFY2):
            try:
                await client.stop_notify(u)
            except Exception:
                pass

    print("\n" + "=" * 60)
    print("ITOG po opkodam:")
    for op in [0x50] + PROBE:
        cnt = sum(1 for _dt, _tag, oc, _d in frames if oc == op)
        print("  0x%02x : %d kadrov" % (op, cnt))
    n1526 = sum(1 for _dt, tag, _oc, _d in frames if tag == "1526")
    print("notify-1526 vsego: %d (0 -> molchit)" % n1526)


if __name__ == "__main__":
    asyncio.run(main())