#!/usr/bin/env python3
"""plus2_opcode_probe.py — безопасный probe whitelist-опкодов 0x10/0xE8/0xE9 RadonEye Plus2.

Назначение: найти, где Plus2 отдаёт day/month-средние. В 0x50 [4:6]/[6:8]=0 на
приборе с историей — опровергнуто как day/month (см. plus2_protocol.md §5). Кандидаты —
whitelist-опкоды 0x10, 0xE8, 0xE9 (все в whitelist, DFU-риска нет).

WHITELIST HARD: пишем ТОЛЬКО {0x10, 0xE8, 0xE9}. Диапазон 0xA0..0xCF вне whitelist
-> DFU-RISK, НЕ трогать. 0x50/0x51 — для baseline-сверки (тоже whitelist).

Приватность: MAC и serial маскируются в выводе (mask_addr/mask_name) — лог безопасен
для публикации/чтения.

Usage (bleak требует Python 3.12):
    python3.12 plus2_opcode_probe.py
    python3.12 plus2_opcode_probe.py --addr AA:BB:CC:DD:EE:FF --gap 6
    # Windows: py -3.12 plus2_opcode_probe.py ...
"""
from __future__ import annotations
import sys, asyncio, struct, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bleak import BleakScanner, BleakClient

ADDR = "AA:BB:CC:DD:EE:FF"            # placeholder; реальный подхватывается по имени FR:PD
NAME_PREFIX = "FR:PD"
WRITE_UUID = "00001524-1212-efde-1523-785feabcd123"
NOTIFY1 = "00001525-1212-efde-1523-785feabcd123"
NOTIFY2 = "00001526-1212-efde-1523-785feabcd123"

# опкоды probe: ТОЛЬКО whitelist. 0x10/0xE8/0xE9 — цель; 0x50/0x51 — baseline.
PROBE_OPCODES = [0x50, 0x51, 0x10, 0xE8, 0xE9]
WHITELIST = {0x10, 0x50, 0x51, 0xA4, 0xA6, 0xA8, 0xAF, 0xE8, 0xE9}

frames = []   # (ts, src_uuid, opcode_written, bytes)
T0 = None
_current_op = None


def hexs(b):
    return " ".join("%02x" % x for x in b)


def mask_addr(a):
    parts = a.replace("-", ":").split(":")
    return ("**:**:**:**:**:" + parts[-1]) if len(parts) == 6 else "**masked**"


def mask_name(nm):
    return (NAME_PREFIX + "****") if nm and NAME_PREFIX in nm else "****"


def u16(b, o):
    return struct.unpack("<H", b[o:o + 2])[0] if len(b) >= o + 2 else None


def u32(b, o):
    return struct.unpack("<I", b[o:o + 4])[0] if len(b) >= o + 4 else None


def f32(b, o):
    return struct.unpack("<f", b[o:o + 4])[0] if len(b) >= o + 4 else None


def cb_factory(src_uuid):
    def cb(_c, data):
        data = bytes(data)
        dt = (time.time() - T0) if T0 else 0.0
        frames.append((dt, src_uuid, _current_op, data))
        tag = "1526" if src_uuid == NOTIFY2 else "1525"
        print("  [%6.1fs] NOTIFY(%s) op=0x%02x len=%d : %s" % (
            dt, tag, _current_op or 0, len(data), hexs(data)))
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


def decode_frame(op, data):
    """Грубый разбор: dump u16/f32 первых полей кадра для поиска day/month."""
    if not data:
        return "пусто"
    out = ["op_echo=0x%02x" % data[0]]
    if len(data) >= 2:
        out.append("plen=%d" % data[1])
    for o in (2, 4, 6, 8, 10, 12, 14, 16):
        v16 = u16(data, o)
        if v16 is not None:
            out.append("[%d:%d]u16=%d" % (o, o + 2, v16))
    # float32-интерпретация первых полей (V1-формат pCi/L)
    cf = f32(data, 2)
    if cf is not None and 0 <= cf < 1e5:
        out.append("[2:6]f32=%.3f(pCi?)" % cf)
    return "  ".join(out)


async def main():
    global T0, _current_op
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=ADDR)
    ap.add_argument("--gap", type=float, default=6.0, help="пауза после каждого опкода, с")
    args = ap.parse_args()

    # safety assert: ни один probe-опкод не вне whitelist
    bad = [op for op in PROBE_OPCODES if op not in WHITELIST]
    if bad:
        print("ABORT: опкоды вне whitelist:", [hex(x) for x in bad])
        return

    print("[scan] addr=%s / name~%s ..." % (mask_addr(args.addr), NAME_PREFIX))
    dev, nm, rssi = await find_device(args.addr, NAME_PREFIX)
    if dev is None:
        print("RESULT: устройство не найдено (ESP-мост отключён? прибор в зоне?)")
        return
    print("[found] %s  name=%s  rssi=%s" % (mask_addr(dev.address), mask_name(nm), rssi))

    async with BleakClient(dev) as client:
        print("[connect] connected=%s" % client.is_connected)
        for u in (NOTIFY1, NOTIFY2):
            try:
                await client.start_notify(u, cb_factory(u))
                print("[notify] subscribed %s" % u[:8])
            except Exception as ex:
                print("[notify] FAIL %s : %r" % (u[:8], ex))

        T0 = time.time()
        for op in PROBE_OPCODES:
            if op not in WHITELIST:    # двойная защита в цикле
                print("[skip] 0x%02x вне whitelist" % op)
                continue
            _current_op = op
            print("\n[write] opcode=0x%02x  (t=%.1fs)" % (op, time.time() - T0))
            try:
                await client.write_gatt_char(WRITE_UUID, bytes([op]), response=True)
            except Exception as ex:
                print("[write] FAIL 0x%02x : %r" % (op, ex))
            await asyncio.sleep(args.gap)
        _current_op = None
        await asyncio.sleep(1.5)
        for u in (NOTIFY1, NOTIFY2):
            try:
                await client.stop_notify(u)
            except Exception:
                pass

    print("\n" + "=" * 70)
    print("СВОДКА ПО ОПКОДАМ")
    print("=" * 70)
    by_op = {}
    for dt, src, op, data in frames:
        by_op.setdefault(op, []).append((dt, src, data))
    for op in PROBE_OPCODES:
        lst = by_op.get(op, [])
        print("\nopcode 0x%02x -> %d кадров:" % (op, len(lst)))
        for dt, src, data in lst:
            tag = "1526" if src == NOTIFY2 else "1525"
            print("  (%s) %s" % (tag, hexs(data)))
            print("        %s" % decode_frame(op, data))
    n1526 = sum(1 for _dt, src, _op, _d in frames if src == NOTIFY2)
    print("\nNOTIFY-1526 итог: %d кадров (если 0 -> молчит и на этих опкодах)" % n1526)


if __name__ == "__main__":
    asyncio.run(main())