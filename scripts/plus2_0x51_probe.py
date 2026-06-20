#!/usr/bin/env python3
"""plus2_0x51_probe.py - celevoj revers kadra 0x51 RadonEye Plus2 + proverka notify-1526.

Назначение (закрытие хвостов plus2_protocol.md §9):
  1. Multi-sample 0x51 в длинном окне -> найти, какие байты МЕНЯЮТСЯ
     (детекция uptime/счётчиков по дельте к wall-clock).
  2. Подписка на ОБЕ notify-характеристики (1525 + 1526) -> зафиксировать,
     отдаёт ли 1526 хоть что-то на 0x50/0x51 (назначение 1526).
  3. Несколько 0x50 для baseline + сверка хвоста [18:20] (session-constant?).

WHITELIST HARD: пишем ТОЛЬКО {0x50, 0x51}. 0xA0..0xCF вне whitelist -> DFU-RISK.

Usage (bleak требует Python 3.12):
    python3.12 plus2_0x51_probe.py
    python3.12 plus2_0x51_probe.py --addr AA:BB:CC:DD:EE:FF --window 130 --gap 12
    # Windows: py -3.12 plus2_0x51_probe.py ...
"""
from __future__ import annotations
import sys, asyncio, struct, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bleak import BleakScanner, BleakClient

ADDR = "AA:BB:CC:DD:EE:FF"            # placeholder; реальный прибор подхватывается по имени
NAME_PREFIX = "FR:PD"
WRITE_UUID  = "00001524-1212-efde-1523-785feabcd123"
NOTIFY1     = "00001525-1212-efde-1523-785feabcd123"
NOTIFY2     = "00001526-1212-efde-1523-785feabcd123"

# (ts, source_uuid, bytes)
frames: list = []
T0 = None


def hexs(b) -> str:
    return " ".join("%02x" % x for x in b)


def u16(b, o):
    return struct.unpack("<H", b[o:o + 2])[0] if len(b) >= o + 2 else None


def u32(b, o):
    return struct.unpack("<I", b[o:o + 4])[0] if len(b) >= o + 4 else None


def cb_factory(src_uuid):
    def cb(_c, data):
        data = bytes(data)
        dt = (time.time() - T0) if T0 else 0.0
        frames.append((dt, src_uuid, data))
        tag = "1526" if src_uuid == NOTIFY2 else "1525"
        print("  [%6.1fs] NOTIFY(%s) len=%d : %s" % (dt, tag, len(data), hexs(data)))
    return cb


async def find_device(addr, name_prefix, timeout=12.0):
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
            return dev, nm, rssi
    if found:
        return list(found.values())[0]
    return None, None, None


def analyze_0x51():
    s51 = [(dt, d) for dt, src, d in frames if src == NOTIFY1 and d and d[0] == 0x51]
    if not s51:
        print("0x51: кадров нет")
        return
    print("\n=== АНАЛИЗ 0x51: %d кадров ===" % len(s51))
    n = min(len(d) for _dt, d in s51)
    first_dt, first = s51[0]
    last_dt, last = s51[-1]
    span = last_dt - first_dt
    print("Первый @ %.1fs : %s" % (first_dt, hexs(first)))
    print("Последний @ %.1fs : %s" % (last_dt, hexs(last)))
    print("Окно между первым и последним: %.1f с\n" % span)
    print("offset | first | last | u16(f->l) | u32(f->l) | changed?")
    changed = []
    for o in range(n):
        f, l = first[o], last[o]
        mark = "<-- ИЗМЕНИЛСЯ" if f != l else ""
        if f != l:
            changed.append(o)
        u16f = u16(first, o); u16l = u16(last, o)
        u32f = u32(first, o); u32l = u32(last, o)
        print("  [%2d] |  %02x   |  %02x  | %5s->%-5s | %9s->%-9s | %s" % (
            o, f, l,
            (str(u16f) if u16f is not None else "-"),
            (str(u16l) if u16l is not None else "-"),
            (str(u32f) if u32f is not None else "-"),
            (str(u32l) if u32l is not None else "-"),
            mark))
    print("\nИзменившиеся offsets:", changed)
    # кандидаты uptime: смотрим u32 LE на [4] и [8]
    for base in (4, 8):
        seq = [(round(dt, 1), u32(d, base)) for dt, d in s51]
        vals = [v for _t, v in seq]
        if len(set(vals)) > 1:
            d_val = vals[-1] - vals[0]
            rate = (d_val / span) if span > 0 else 0
            print("u32[%d:%d] меняется: %s  Δ=%d за %.1fs  (~%.3f/с)" % (
                base, base + 4, seq, d_val, span, rate))
        else:
            print("u32[%d:%d] константа = %s" % (base, base + 4, vals[0]))
    # хвост [18:20] sanity
    tails = set(hexs(d[18:20]) for _dt, d in s51 if len(d) >= 20)
    print("Хвост [18:20] по всем 0x51:", tails)


def cross_tail():
    s50 = [d for _dt, src, d in frames if src == NOTIFY1 and d and d[0] == 0x50 and len(d) >= 20]
    s51 = [d for _dt, src, d in frames if src == NOTIFY1 and d and d[0] == 0x51 and len(d) >= 20]
    t50 = set(hexs(d[18:20]) for d in s50)
    t51 = set(hexs(d[18:20]) for d in s51)
    print("\n=== ХВОСТ [18:20] cross-opcode (session-constant?) ===")
    print("0x50 tails:", t50)
    print("0x51 tails:", t51)
    print("Совпадает между 0x50 и 0x51:", (t50 == t51 and len(t50) == 1))


async def main():
    global T0
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=ADDR)
    ap.add_argument("--window", type=float, default=130.0, help="общее окно опроса, с")
    ap.add_argument("--gap", type=float, default=12.0, help="пауза между записями, с")
    args = ap.parse_args()

    print("[scan] addr=%s / name~%s ..." % (args.addr, NAME_PREFIX))
    dev, nm, rssi = await find_device(args.addr, NAME_PREFIX)
    if dev is None:
        print("RESULT: устройство не найдено (ESP-мост отключён? прибор в зоне?)")
        return
    print("[found] %s  name=%r  rssi=%s" % (dev.address, nm, rssi))

    async with BleakClient(dev) as client:
        print("[connect] connected=%s" % client.is_connected)
        for u in (NOTIFY1, NOTIFY2):
            try:
                await client.start_notify(u, cb_factory(u))
                print("[notify] subscribed %s" % u)
            except Exception as ex:
                print("[notify] FAIL %s : %r" % (u, ex))

        T0 = time.time()
        cycles = max(1, int(args.window // args.gap))
        for i in range(cycles):
            op = 0x51 if (i % 3 != 2) else 0x50   # 2 раза 0x51, 1 раз 0x50
            print("[write] #%d opcode=0x%02x  (t=%.1fs)" % (i + 1, op, time.time() - T0))
            try:
                await client.write_gatt_char(WRITE_UUID, bytes([op]), response=True)
            except Exception as ex:
                print("[write] FAIL 0x%02x : %r" % (op, ex))
            await asyncio.sleep(args.gap)
        await asyncio.sleep(1.5)
        for u in (NOTIFY1, NOTIFY2):
            try:
                await client.stop_notify(u)
            except Exception:
                pass

    n1526 = sum(1 for _dt, src, _d in frames if src == NOTIFY2)
    print("\n=== NOTIFY-1526 итог: %d кадров (если 0 -> молчит на 0x50/0x51) ===" % n1526)
    analyze_0x51()
    cross_tail()


if __name__ == "__main__":
    asyncio.run(main())