#!/usr/bin/env python3
"""Decode RadonEye Plus2 BLE history dump from an Android btsnoop log.

Associates each TX WRITE op=0x61 (handle 0x000b) "history dump" command with the
contiguous stream of RX NOTIFY frames on handle 0x0010 (NOTIFY-2, bulk history).
Record size is 8 bytes: [0:4]=uint32 LE Unix timestamp (+3600s per record),
[4:6]=uint16 LE radon, [6:8]=tail (flags/temp, under analysis). Records ordered
oldest -> newest.

Usage:
    python plus2_history_decode.py <btsnoop_hci.log> [--recsize N] [--dump-index K]
"""
from __future__ import annotations
import sys, struct
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plus2_btsnoop_parse import parse

CMD_HANDLE = 0x000b
HIST_HANDLE = 0x0010


def collect_dumps(recs):
    dumps = []
    cur = None
    for kind, opc, ah, val, d, t in recs:
        is_61 = (kind == "WRITE" and ah == CMD_HANDLE and val and val[0] == 0x61)
        is_hist = (kind == "NOTIFY" and ah == HIST_HANDLE)
        if is_61:
            param = struct.unpack("<H", val[2:4])[0] if len(val) >= 4 else None
            cur = {"param": param, "ts": t, "stream": bytearray()}
            dumps.append(cur)
        elif is_hist and cur is not None:
            cur["stream"] += val
        else:
            cur = None
    return dumps


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    path = args[0]
    recsize = int(args[args.index("--recsize") + 1]) if "--recsize" in args else None
    dump_index = int(args[args.index("--dump-index") + 1]) if "--dump-index" in args else None

    recs = parse(path, None)
    dumps = collect_dumps(recs)
    print("# %d history dump(s) found" % len(dumps))
    print("%-3s %-10s %-8s %-10s %-12s" % ("#", "req_recs", "bytes", "bytes/rec", "remainder"))
    for i, dmp in enumerate(dumps):
        n = dmp["param"]
        b = len(dmp["stream"])
        per = ("%.3f" % (b / n)) if n else "?"
        rem = (b % n) if n else "?"
        print("%-3d %-10s %-8d %-10s %-12s" % (i, n, b, per, rem))

    if dump_index is None:
        dump_index = max(range(len(dumps)), key=lambda k: len(dumps[k]["stream"])) if dumps else None
    if dump_index is None:
        return
    dmp = dumps[dump_index]
    stream = bytes(dmp["stream"])
    print("\n# inspecting dump #%d: req=%s recs, %d bytes" % (dump_index, dmp["param"], len(stream)))

    from datetime import datetime, timezone

    def show8(j, r):
        ts = struct.unpack("<I", r[0:4])[0]
        radon = struct.unpack("<H", r[4:6])[0]
        tail = struct.unpack("<H", r[6:8])[0]
        try:
            dt = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            dt = "?"
        print("  rec %5d: %s  ts=%d (%s)  radon=%-5d tail=0x%04x" % (j, r.hex(), ts, dt, radon, tail))

    sz = recsize or 8
    nrec = len(stream) // sz
    print("\n=== record size %d -> %d records ===" % (sz, nrec))
    if nrec == 0:
        print("# (empty stream — nothing to decode)")
        return
    if sz == 8:
        print("# HEAD (oldest):")
        for j in range(min(nrec, 16)):
            show8(j, stream[j * sz:(j + 1) * sz])
        if nrec > 32:
            print("# TAIL (newest):")
            for j in range(max(0, nrec - 16), nrec):
                show8(j, stream[j * sz:(j + 1) * sz])
        bad = 0
        prev = None
        radons = []
        for j in range(nrec):
            ts = struct.unpack("<I", stream[j * sz:j * sz + 4])[0]
            radons.append(struct.unpack("<H", stream[j * sz + 4:j * sz + 6])[0])
            if prev is not None and (ts - prev) != 3600:
                bad += 1
            prev = ts
        t0 = struct.unpack("<I", stream[0:4])[0]
        tN = struct.unpack("<I", stream[(nrec - 1) * sz:(nrec - 1) * sz + 4])[0]
        print("# spacing audit: %d/%d gaps != 3600s; span=%.1f days" % (bad, nrec - 1, (tN - t0) / 86400.0))
        print("# radon[4:6] stats: min=%d max=%d mean=%.1f" % (min(radons), max(radons), sum(radons) / len(radons)))
    else:
        for j in range(min(nrec, 16)):
            print("  rec %3d: %s" % (j, stream[j * sz:(j + 1) * sz].hex()))


if __name__ == "__main__":
    main()