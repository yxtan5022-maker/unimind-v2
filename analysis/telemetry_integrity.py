"""
Data-integrity check for the telemetry snapshot set.

Catches the two failure classes we've hit in production:
  1. UTF-8 BOM contamination (from a one-time PowerShell ConvertTo-Json rewrite)
     that makes standard Python json.load fail with 'Expecting value'.
  2. Any truncated/empty/corrupt JSON file.

Also re-writes BOM'd files back to clean no-BOM UTF-8 (in place), so the set is
always readable by every downstream analysis script via plain json.load(open(f)).

Usage:
  python telemetry_integrity.py            # check only
  python telemetry_integrity.py --fix      # check + rewrite BOM files clean
"""
import argparse
import glob
import io
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP = ROOT / "data" / "calib_snapshots"

BACKENDS = ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]


def _files():
    for b in BACKENDS:
        for f in sorted(glob.glob(str(SNAP / b / "*.json"))):
            yield Path(f)


def integrity(fix=False):
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    problems = 0
    bom_fixed = 0
    for f in _files():
        raw = f.read_bytes()
        rel = f.parent.name + "/" + f.name
        if raw[:3] == b"\xef\xbb\xbf":
            print(f"BOM on {rel}", file=out)
            problems += 1
            if fix:
                obj = json.loads(raw.decode("utf-8-sig"))
                f.write_bytes(json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8"))
                bom_fixed += 1
                print(f"  -> rewritten clean: {rel}", file=out)
        try:
            json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"CORRUPT {rel}: {type(e).__name__} size={len(raw)}", file=out)
            problems += 1
    if problems:
        print(f"\n{problems} problem(s) found; {bom_fixed} BOM file(s) fixed", file=out)
    else:
        print("OK: all snapshot JSON readable (no BOM, no corruption)", file=out)
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="rewrite BOM-contaminated files as clean no-BOM UTF-8")
    args = ap.parse_args()
    sys.exit(1 if integrity(fix=args.fix) else 0)
