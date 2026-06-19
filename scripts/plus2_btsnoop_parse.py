#!/usr/bin/env python3
"""Parse Android btsnoop_hci.log -> list ATT writes/notifies (RadonEye Plus2 reverse).

Reassembles ACL fragments, prints every ATT Write Command/Request (0x52/0x12) and
Handle Value Notification/Indication (0x1b/0x1d) in chronological order with
timestamp, direction (TX=host->device, RX=device->host), ATT handle and value hex.
Used to identify the day/month/year history opcodes of the RadonEye Plus2 protocol.

Usage:
    python plus2_btsnoop_parse.py <btsnoop_hci.log> [--handle 0xNN] [--last N] [--writes]
"""
from __future__ import annotations
import sys, struct
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from datetime import datetime, timedelta

BTSNOOP_MAGIC = b"btsnoop\x00"
TIME_CONV = 0x00dcddb30f2f8000  # us between 0000-01-01 and 1970-01-01


def ts_to_str(ts_us):
    try:
        return (datetime(1970, 1, 1) + timedelta(microseconds=ts_us - TIME_CONV)).strftime("%H:%M:%S.%f")[:-3]
    except Exception:
        return str(ts_us)


def parse(path, handle_filter=None):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != BTSNOOP_MAGIC:
        print("Not a btsnoop file (bad magic): %r" % data[:8], file=sys.stderr)
        return []
    ver, dlt = struct.unpack(">II", data[8:16])
    print("# btsnoop version=%d datalink=%d size=%d" % (ver, dlt, len(data)), file=sys.stderr)
    off = 16
    pend = {}
    out = []
    while off + 24 <= len(data):
        olen, ilen, flags, drops, ts = struct.unpack(">IIIIq", data[off:off + 24])
        off += 24
        pkt = data[off:off + ilen]
        off += ilen
        if not pkt:
            continue
        if pkt[0] != 0x02:      # ACL only
            continue
        if len(pkt) < 5:
            continue
        direction = flags & 0x01
        h, = struct.unpack("<H", pkt[1:3])
        acl_handle = h & 0x0FFF
        pb = (h >> 12) & 0x3
        dtl, = struct.unpack("<H", pkt[3:5])
        payload = pkt[5:5 + dtl]
        if pb == 0x1:           # continuation
            st = pend.get(acl_handle)
            if st is None:
                continue
            st["buf"] += payload
        else:                   # first fragment
            if len(payload) < 4:
                continue
            l2len, cid = struct.unpack("<HH", payload[0:4])
            pend[acl_handle] = {"buf": bytearray(payload[4:]), "l2len": l2len,
                                "cid": cid, "dir": direction, "ts": ts}
        st = pend.get(acl_handle)
        if st is None:
            continue
        if len(st["buf"]) >= st["l2len"]:
            frame = bytes(st["buf"][:st["l2len"]])
            cid, d, t = st["cid"], st["dir"], st["ts"]
            del pend[acl_handle]
            if cid != 0x0004 or not frame:
                continue
            opc = frame[0]
            kind = None
            if opc in (0x52, 0x12):
                kind = "WRITE"
            elif opc == 0x1b:
                kind = "NOTIFY"
            elif opc == 0x1d:
                kind = "INDICATE"
            if kind and len(frame) >= 3:
                ah, = struct.unpack("<H", frame[1:3])
                val = frame[3:]
                if handle_filter is not None and ah != handle_filter:
                    continue
                out.append((kind, opc, ah, val, d, t))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    path = args[0]
    hf = int(args[args.index("--handle") + 1], 0) if "--handle" in args else None
    writes_only = "--writes" in args
    recs = parse(path, hf)
    if writes_only:
        recs = [r for r in recs if r[0] == "WRITE"]
    if "--last" in args:
        recs = recs[-int(args[args.index("--last") + 1]):]
    print("# %d ATT write/notify PDUs" % len(recs))
    for kind, opc, ah, val, d, t in recs:
        dirs = "TX" if d == 0 else "RX"
        op0 = ("op=0x%02x " % val[0]) if val else ""
        print("%s %s %-8s att_h=0x%04x len=%2d %s%s" % (ts_to_str(t), dirs, kind, ah, len(val), op0, val.hex()))


if __name__ == "__main__":
    main()
