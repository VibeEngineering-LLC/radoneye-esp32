#!/usr/bin/env python3
"""plus2_gatt_dump.py — прямой дамп GATT RadonEye Plus2 через BT компьютера (bleak/WinRT).

Назначение: подключиться к живому RadonEye Plus2, снять ПОЛНУЮ GATT-карту
(service / characteristic с handle+properties / descriptor), затем (опкоды из
whitelist) записать 0x50 и 0x51 в write-характеристику и поймать notify-кадры.
Декодирует кадр 0x50 как Plus2-формат: uint16 LE Bq/m³ @ [2:4].

ВАЖНО (whitelist HARD): пишем ТОЛЬКО опкоды {0x50, 0x51}. Диапазон 0xA0..0xCF
вне whitelist → DFU-RISK, НЕ трогать.

Usage (bleak требует Python 3.12):
    python3.12 plus2_gatt_dump.py
    python3.12 plus2_gatt_dump.py --addr AA:BB:CC:DD:EE:FF --name-prefix FR:PD
    # Windows: py -3.12 plus2_gatt_dump.py ...
"""
from __future__ import annotations
import sys, asyncio, struct, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from bleak import BleakScanner, BleakClient
except Exception as e:
    print("BLEAK_IMPORT_FAIL:", repr(e))
    sys.exit(2)

DEFAULT_ADDR = "AA:BB:CC:DD:EE:FF"
DEFAULT_NAME_PREFIX = "FR:PD"

notifications = []  # (ts, char_uuid, handle, bytes)


def hexs(b: bytes) -> str:
    return " ".join("%02x" % x for x in b)


def notify_cb_factory(char_uuid, handle):
    def cb(_char, data: bytearray):
        notifications.append((time.time(), char_uuid, handle, bytes(data)))
        print("  NOTIFY h=0x%04x uuid=%s len=%d : %s" % (handle, char_uuid, len(data), hexs(bytes(data))))
    return cb


def decode_0x50(data: bytes):
    """Plus2: 0x50→20B, [2:4]=current Bq/m³ uint16 LE, [12:14]=radon echo,
    [14:16]=pulse, [16:18]=pulse10, [18:20]=cache mm:ss от last 0x51.
    day/month via 0x60+0x61 bulk (NOT in 0x50 frame, verified live 2026-06-15)."""
    out = {}
    if len(data) < 2 or data[0] != 0x50:
        out["_warn"] = "не 0x50-кадр или короткий"
        return out
    try:
        if len(data) >= 4:
            bq = struct.unpack("<H", data[2:4])[0]
            out["current_Bq_m3"] = bq
            out["current_pCi_L"] = round(bq / 37.0, 3)
        if len(data) >= 6:
            out["_reserved_4_6"] = struct.unpack("<H", data[4:6])[0]
        if len(data) >= 8:
            out["_reserved_6_8"] = struct.unpack("<H", data[6:8])[0]
        if len(data) >= 14:
            out["radon_echo_Bq"] = struct.unpack("<H", data[12:14])[0]
        if len(data) >= 16:
            out["pulse"] = struct.unpack("<H", data[14:16])[0]
        if len(data) >= 18:
            out["pulse10"] = struct.unpack("<H", data[16:18])[0]
        if len(data) >= 20:
            out["cache_mm"], out["cache_ss"] = data[18], data[19]
    except Exception as ex:
        out["_decode_err"] = repr(ex)
    return out


async def find_device(addr, name_prefix, timeout=12.0):
    print("[scan] поиск устройства %s / имя ~ %s (%.0f с)..." % (addr, name_prefix, timeout))
    found = {}

    def det_cb(dev, adv):
        nm = adv.local_name or dev.name or ""
        if dev.address.upper() == addr.upper() or (name_prefix and name_prefix in nm):
            if dev.address not in found:
                found[dev.address] = (dev, nm, adv.rssi)
                print("  [scan] кандидат: %s  name=%r  rssi=%s" % (dev.address, nm, adv.rssi))

    scanner = BleakScanner(detection_callback=det_cb)
    await scanner.start()
    t0 = time.time()
    while time.time() - t0 < timeout:
        if any(d.address.upper() == addr.upper() for d in [v[0] for v in found.values()]):
            break
        await asyncio.sleep(0.4)
    await scanner.stop()
    # точное совпадение по MAC приоритетно
    for dev, nm, rssi in found.values():
        if dev.address.upper() == addr.upper():
            return dev, nm, rssi
    if found:
        dev, nm, rssi = list(found.values())[0]
        return dev, nm, rssi
    return None, None, None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=DEFAULT_ADDR)
    ap.add_argument("--name-prefix", default=DEFAULT_NAME_PREFIX)
    ap.add_argument("--no-write", action="store_true", help="только GATT-дамп, без записи опкодов")
    args = ap.parse_args()

    dev, nm, rssi = await find_device(args.addr, args.name_prefix)
    if dev is None:
        print("RESULT: устройство не найдено (проверь, что ESP отключён и прибор в зоне)")
        return
    print("[connect] %s  name=%r  rssi=%s ..." % (dev.address, nm, rssi))

    async with BleakClient(dev) as client:
        print("[connect] connected=%s" % client.is_connected)
        print()
        print("=" * 70)
        print("GATT-КАРТА")
        print("=" * 70)
        write_chars = []
        notify_chars = []
        svcs = client.services
        for svc in svcs:
            print("SERVICE  h=0x%04x  uuid=%s  (%s)" % (svc.handle, svc.uuid, svc.description))
            for ch in svc.characteristics:
                props = ",".join(ch.properties)
                print("  CHAR   h=0x%04x  uuid=%s  props=[%s]  (%s)" % (ch.handle, ch.uuid, props, ch.description))
                if "1524" in ch.uuid.lower() or "write" in props or "write-without-response" in props:
                    write_chars.append(ch)
                if "notify" in props or "indicate" in props:
                    notify_chars.append(ch)
                for d in ch.descriptors:
                    print("    DESC h=0x%04x  uuid=%s  (%s)" % (d.handle, d.uuid, d.description))
        print("=" * 70)
        print()

        # выбрать write-характеристику: предпочесть 1524
        wch = None
        for ch in write_chars:
            if "1524" in ch.uuid.lower():
                wch = ch
                break
        if wch is None and write_chars:
            wch = write_chars[0]

        # подписаться на notify
        subscribed = []
        for ch in notify_chars:
            try:
                await client.start_notify(ch, notify_cb_factory(ch.uuid, ch.handle))
                subscribed.append(ch)
                print("[notify] subscribed h=0x%04x uuid=%s" % (ch.handle, ch.uuid))
            except Exception as ex:
                print("[notify] FAIL h=0x%04x : %r" % (ch.handle, ex))
        print()

        if args.no_write:
            print("[write] пропущено (--no-write)")
        elif wch is None:
            print("[write] write-характеристика не найдена!")
        else:
            wnr = "write-without-response" in wch.properties
            for op in (0x50, 0x51):
                print("[write] -> h=0x%04x uuid=%s  opcode=0x%02x (response=%s)" % (wch.handle, wch.uuid, op, not wnr))
                try:
                    await client.write_gatt_char(wch, bytes([op]), response=not wnr)
                except Exception as ex:
                    print("[write] FAIL opcode 0x%02x : %r" % (op, ex))
                await asyncio.sleep(2.5)

        # дать notify добежать
        await asyncio.sleep(1.5)
        for ch in subscribed:
            try:
                await client.stop_notify(ch)
            except Exception:
                pass

    print()
    print("=" * 70)
    print("СОБРАННЫЕ NOTIFY-КАДРЫ: %d" % len(notifications))
    print("=" * 70)
    for ts, uuid, handle, data in notifications:
        print("h=0x%04x uuid=%s len=%d : %s" % (handle, uuid, len(data), hexs(data)))
        if data and data[0] == 0x50:
            print("   DECODE 0x50:", decode_0x50(data))
        elif data and data[0] == 0x51:
            print("   (0x51 uptime/peak кадр — len=%d)" % len(data))


if __name__ == "__main__":
    asyncio.run(main())