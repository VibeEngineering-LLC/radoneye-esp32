# -*- coding: utf-8 -*-
"""
RadonEye Plus2 (RD200PLUS) - live-загрузчик почасовой истории по BLE.

Скачивает сохранённую почасовую историю радона напрямую с прибора:
  0x60 -> число записей в приборе (ответ на NOTIFY-1, char 1525, байты [2:4] LE)
  0x61 -> bulk-дамп N свежих почасовых записей (поток N*8 байт на NOTIFY-2, char 1526)
Декодирует 8-байтовые записи и сохраняет в JSON + CSV.

Протокол верифицирован btsnoop-трассой официального приложения (2026-06-15),
см. references/plus2_protocol.md §6A. История download = READ-ONLY, безопасна.

Формат команды (20 байт write в char 1524 / handle 0x000b):
    <opcode> 0x11 <param_u16_LE> 00 ...нули до 20 байт
Формат записи (8 байт, oldest->newest):
    [0:4] uint32 LE  Unix timestamp (ЛОКАЛЬНОЕ время прибора, шаг +3600 с)
    [4:6] uint16 LE  радон, Bq/m3
    [6:8] uint16 LE  temp_raw — формат НЕ верифицирован (рабочая гипотеза Q8.8
                     /256, но btsnoop-трасса 0x60/0x61 это НЕ подтвердила).
                     До верификации публикуется как сырой uint16 + флаг
                     `temp_unverified: true` (см. plus2_protocol.md §6A).

Usage (bleak требует Python 3.12; Windows — `py -3.12`, Linux — `python3.12`):
    # последние N часов (N свежих почасовых записей):
    python3.12 plus2_history_download.py --mac AA:BB:CC:DD:EE:FF --hours 48
    # вся история (число записей берётся из ответа 0x60):
    python3.12 plus2_history_download.py --mac AA:BB:CC:DD:EE:FF --all
    # окно по датам (скачать всё, отфильтровать по встроенному ts):
    python3.12 plus2_history_download.py --mac AA:BB:CC:DD:EE:FF --all --from 2026-06-01 --to 2026-06-10
    # поиск по adv-префиксу имени вместо MAC:
    $PY plus2_history_download.py --name-prefix FR:PD --all
"""
from __future__ import annotations
import sys, asyncio, struct, json, csv, argparse
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bleak import BleakClient, BleakScanner

CMD_CHAR    = "00001524-1212-efde-1523-785feabcd123"  # WRITE (handle 0x000b)
NOTIFY_1525 = "00001525-1212-efde-1523-785feabcd123"  # ответы команд (0x000d)
NOTIFY_1526 = "00001526-1212-efde-1523-785feabcd123"  # bulk-история (0x0010)

OPCODE_COUNT = 0x60
OPCODE_DUMP  = 0x61
REC_LEN      = 8
MAX_RECORDS  = 9600   # из 0x60-трассы (~401 день почасовой истории)

# Anti-DFU whitelist (см. SKILL.md / plus2_protocol.md §5).
# Опкоды вне whitelist с высокой вероятностью переводят прибор в DFU mode
# (recovery — вынуть батарейки ~30 с). НЕ расширять без верификации btsnoop.
WHITELIST = frozenset({
    0x10, 0x50, 0x51, 0x53, 0x54, 0x56,
    0x60, 0x61,
    0xA4, 0xA6, 0xA8, 0xAF,
    0xE8, 0xE9,
})


def build_cmd(opcode: int, param: int = 0) -> bytes:
    """20-байтовая команда: <opcode> 0x11 <param_u16_LE> 00 ...padding нулями.

    Runtime-страж: opcode ОБЯЗАН быть в WHITELIST. Иначе RuntimeError —
    write вообще не выполняется (предохранитель от DFU).
    """
    op = opcode & 0xFF
    if op not in WHITELIST:
        raise RuntimeError(
            f"opcode 0x{op:02X} вне whitelist; 0xA0..0xCF -> DFU mode. "
            "Расширять WHITELIST только после трассы btsnoop."
        )
    buf = bytearray(20)
    buf[0] = op
    buf[1] = 0x11
    struct.pack_into("<H", buf, 2, param & 0xFFFF)
    return bytes(buf)


def decode_record(b: bytes) -> dict:
    """8-байтовая запись: ts u32 LE | radon u16 LE | bytes[6:8] = "temp_raw" u16 LE.

    Поле temp_raw НЕ декодируется в °C: формат Q8.8 (/256) — это рабочая
    гипотеза 2026-06-15, она НЕ подтверждена btsnoop-трассой Plus2 §6А.
    До верификации — публикуем сырое значение + флаг unverified.
    """
    ts   = struct.unpack_from("<I", b, 0)[0]
    bq   = struct.unpack_from("<H", b, 4)[0]
    traw = struct.unpack_from("<H", b, 6)[0]
    return {
        "ts_unix": ts,
        "ts_local": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "radon_bq_m3": bq,
        "temp_raw": traw,
        "temp_unverified": True,
    }


async def find_address(name_prefix: str) -> str | None:
    print(f"[+] скан BLE 12 c, ищу adv-префикс '{name_prefix}' ...", flush=True)
    devs = await BleakScanner.discover(timeout=12.0)
    for d in devs:
        nm = d.name or ""
        if nm.startswith(name_prefix):
            print(f"[+] найден {d.address}  name='{nm}'  rssi={getattr(d, 'rssi', '?')}", flush=True)
            return d.address
    print("[!] прибор с таким префиксом не найден в эфире", flush=True)
    return None


async def download(address: str, want: int) -> list[dict]:
    notify_1526 = bytearray()
    resp_1525: list[bytes] = []

    def on_1525(_s, data):
        resp_1525.append(bytes(data))

    def on_1526(_s, data):
        notify_1526.extend(bytes(data))

    print(f"[+] подключение к {address} ...", flush=True)
    async with BleakClient(address, timeout=20.0) as c:
        if not c.is_connected:
            print("[!] не удалось подключиться", flush=True)
            return []
        await c.start_notify(NOTIFY_1525, on_1525)
        await c.start_notify(NOTIFY_1526, on_1526)
        await asyncio.sleep(0.4)

        # 1) 0x60 - сколько записей хранит прибор
        # Чистим преамбулу из notify_1525 ровно перед write, иначе при ranной
        # выдаче `total` может «прийти» из случайного хвоста, не из ответа 0x60.
        resp_1525.clear()
        await c.write_gatt_char(CMD_CHAR, build_cmd(OPCODE_COUNT), response=False)
        await asyncio.sleep(1.5)
        total = None
        for r in resp_1525:
            if r and r[0] == OPCODE_COUNT and len(r) >= 4:
                total = struct.unpack_from("<H", r, 2)[0]
                break
        if total is None:
            print("[!] прибор не ответил на 0x60 (число записей). Прерываю.", flush=True)
            return []
        print(f"[+] записей в приборе: {total}", flush=True)

        n = total if want <= 0 else min(want, total)
        n = min(n, MAX_RECORDS)
        if n <= 0:
            print("[!] нечего запрашивать (n=0)", flush=True)
            return []
        print(f"[+] запрашиваю последние {n} почасовых записей (0x61) ...", flush=True)

        # 2) 0x61 - bulk-дамп N свежих записей
        before = len(notify_1526)
        await c.write_gatt_char(CMD_CHAR, build_cmd(OPCODE_DUMP, n), response=False)

        expected = n * REC_LEN
        deadline, waited, last_len, quiet = 120.0, 0.0, len(notify_1526), 0.0
        while waited < deadline:
            await asyncio.sleep(0.3)
            waited += 0.3
            cur = len(notify_1526)
            if cur >= before + expected:
                break
            if cur > last_len:
                last_len, quiet = cur, 0.0
            else:
                quiet += 0.3
                if quiet > 8.0:
                    print(f"[!] поток затих: {cur - before}/{expected} байт", flush=True)
                    break

        try:
            await c.stop_notify(NOTIFY_1525)
        except Exception:
            pass
        try:
            await c.stop_notify(NOTIFY_1526)
        except Exception:
            pass

    raw = bytes(notify_1526[before:])
    nrec = len(raw) // REC_LEN
    recs = [decode_record(raw[i * REC_LEN:(i + 1) * REC_LEN]) for i in range(nrec)]
    print(f"[+] получено {nrec} записей ({len(raw)} байт)", flush=True)
    return recs


def filter_by_date(recs, dfrom, dto):
    def ep(s):
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    lo = ep(dfrom) if dfrom else None
    hi = (ep(dto) + 86400) if dto else None
    out = []
    for r in recs:
        if lo is not None and r["ts_unix"] < lo:
            continue
        if hi is not None and r["ts_unix"] >= hi:
            continue
        out.append(r)
    return out


def save(recs, base):
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    with open(base + ".csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_unix", "ts_local", "radon_bq_m3", "temp_raw", "temp_unverified"])
        for r in recs:
            w.writerow([r["ts_unix"], r["ts_local"], r["radon_bq_m3"],
                        r["temp_raw"], r.get("temp_unverified", True)])
    print(f"[+] сохранено: {base}.json / {base}.csv", flush=True)


async def amain(a):
    addr = a.mac
    if not addr and a.name_prefix:
        addr = await find_address(a.name_prefix)
    if not addr:
        print("[!] не задан --mac и прибор не найден по --name-prefix", flush=True)
        return 2
    want = 0 if a.all else max(1, a.hours)
    recs = await download(addr, want)
    if not recs:
        return 1
    if a.from_ or a.to:
        recs = filter_by_date(recs, a.from_, a.to)
        print(f"[+] после фильтра по датам: {len(recs)} записей", flush=True)
    if recs:
        print(f"    первая:    {recs[0]['ts_local']}  радон={recs[0]['radon_bq_m3']} Bq/m3  temp_raw={recs[0]['temp_raw']} (unverified)", flush=True)
        print(f"    последняя: {recs[-1]['ts_local']}  радон={recs[-1]['radon_bq_m3']} Bq/m3  temp_raw={recs[-1]['temp_raw']} (unverified)", flush=True)
    save(recs, a.out)
    return 0


def main():
    p = argparse.ArgumentParser(description="RadonEye Plus2 - скачать почасовую историю по BLE (0x60/0x61)")
    p.add_argument("--mac", help="MAC прибора, напр. AA:BB:CC:DD:EE:FF")
    p.add_argument("--name-prefix", default="FR:PD", help="искать по adv-префиксу имени, если --mac не задан")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--hours", type=int, default=48, help="последние N часов = N свежих записей (по умолчанию 48)")
    g.add_argument("--all", action="store_true", help="вся история (число записей из ответа 0x60)")
    p.add_argument("--from", dest="from_", help="фильтр: дата от YYYY-MM-DD")
    p.add_argument("--to", help="фильтр: дата до YYYY-MM-DD включительно")
    p.add_argument("--out", default="plus2_history", help="базовое имя выходных файлов")
    a = p.parse_args()
    try:
        return asyncio.run(amain(a))
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())