#!/usr/bin/env python3
# Fits for docs/notes/aa-voltage.csv: how the firmware's % maps to the AA's voltage, per pairing of
# methods, scored against cjf vr' current line. Run: python3 -I docs/notes/aa-voltage-fit.py
import csv
import sys
from collections import defaultdict
from pathlib import Path

CURRENT = (1.13, 1.48)
SPLIT = 50  # the per-range scores split at this %

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("aa-voltage.csv")
cells = defaultdict(lambda: defaultdict(dict))  # (test, side) -> what -> min -> value
with path.open() as f:
    rows = csv.DictReader(line for line in f if not line.startswith("#"))
    for r in rows:
        m = float(r["min"]) if r["min"] else None
        cells[(r["test"], r["side"])][r["what"]][m] = float(r["value"])


def first(d, what, minute="any"):
    vals = d.get(what, {})
    if minute == "any":
        return vals[min(vals, key=lambda k: -1 if k is None else k)] if vals else None
    return vals.get(minute)


def late(d, what, after=5):
    vals = {m: v for m, v in d.get(what, {}).items() if m is not None and m >= after}
    return vals[max(vals)] if vals else None


def rest_v(d):
    # A resting voltage: out of the controller, else in place after 15 minutes or more.
    if "v_out" in d:
        return first(d, "v_out")
    late = [m for m in d.get("v_in", {}) if m is not None and m >= 15]
    return d["v_in"][max(late)] if late else None


# Each pairing: name, what it is, and a function from one cell's readings to (%, V) or None.
PAIRINGS = [
    ("out/on0", "resting V out, then % right after power-on (older method)",
     lambda d: (first(d, "pct_on", 0), first(d, "v_out"))),
    ("run/in0", "% running, then V in place at once (recent method)",
     lambda d: (first(d, "pct_run"), first(d, "v_in", 0))),
    ("run/rest", "% running against resting V: what cjf vr means",
     lambda d: (first(d, "pct_run"), rest_v(d))),
    ("on5/rest", "% 5 min or more after power-on against resting V",
     lambda d: (late(d, "pct_on"), rest_v(d))),
    ("on/load", "% after power-on against V under load at the same minute",
     lambda d: next(((p, d["v_on"][m]) for m, p in sorted(d.get("pct_on", {}).items(),
                                                       key=lambda x: -(x[0] or 0))
                     if m in d.get("v_on", {})), (None, None))),
]


def line_fit(pts):
    n = len(pts)
    mp = sum(p for p, _ in pts) / n
    mv = sum(v for _, v in pts) / n
    sxx = sum((p - mp) ** 2 for p, _ in pts)
    b = sum((p - mp) * (v - mv) for p, v in pts) / sxx
    return mv - b * mp, b, sxx, mp


def score(pts, a, b):
    if not pts:
        return "-"
    r = [v - (a + b * p) for p, v in pts]
    rms = (sum(x * x for x in r) / len(r)) ** 0.5 * 1000
    worst = max(map(abs, r)) * 1000
    mean = sum(r) / len(r) * 1000
    return f"n={len(r):2d} rms {rms:4.1f} worst {worst:3.0f} mean {mean:+5.1f} mV"


ca, cb = CURRENT[0], CURRENT[1] - CURRENT[0]
for name, desc, pick in PAIRINGS:
    pts = []
    for d in cells.values():
        p, v = pick(d)
        if p is not None and v is not None:
            pts.append((p / 100, v))
    if not pts:
        continue
    lo = [x for x in pts if x[0] * 100 < SPLIT]
    hi = [x for x in pts if x[0] * 100 >= SPLIT]
    span = f"{min(p for p, _ in pts) * 100:.0f}-{max(p for p, _ in pts) * 100:.0f}%"
    print(f"{name}: {desc}, {span}")
    print(f"  current {CURRENT[0]:.2f}-{CURRENT[1]:.2f}: all {score(pts, ca, cb)}")
    print(f"      below {SPLIT}%: {score(lo, ca, cb)}   from {SPLIT}%: {score(hi, ca, cb)}")
    if len(pts) >= 3 and len({p for p, _ in pts}) >= 2:
        a, b, sxx, mp = line_fit(pts)
        n = len(pts)
        s2 = sum((v - a - b * p) ** 2 for p, v in pts) / (n - 2)
        e0 = (s2 * (1 / n + mp ** 2 / sxx)) ** 0.5 * 1000
        e1 = (s2 * (1 / n + (1 - mp) ** 2 / sxx)) ** 0.5 * 1000
        print(f"  own fit {a:.3f}-{a + b:.3f} V (±{e0:.0f} / ±{e1:.0f} mV at the ends): "
              f"all {score(pts, a, b)}")
        print(f"      below {SPLIT}%: {score(lo, a, b)}   from {SPLIT}%: {score(hi, a, b)}")
    print()

# What the side-by-side tests show: recovery after load, and drift after power-on.
for (test, side), d in sorted(cells.items()):
    vin = {m: v for m, v in d.get("v_in", {}).items() if m is not None}
    pon = {m: v for m, v in d.get("pct_on", {}).items() if m is not None}
    von = {m: v for m, v in d.get("v_on", {}).items() if m is not None}
    if len(vin) < 2 and len(pon) < 2:
        continue
    print(f"{test} {side}: % running {first(d, 'pct_run')}")
    if vin:
        base = vin[min(vin)]
        rec = ", ".join(f"{m:g} min {1000 * (v - base):+.0f}" for m, v in sorted(vin.items()))
        out = first(d, "v_out")
        extra = f", out {1000 * (out - base):+.0f}" if out is not None else ""
        print(f"  V in place {base:.3f}, recovery mV: {rec}{extra}")
    if pon:
        print("  % after power-on: " + ", ".join(f"{m:g} min {v:g}" for m, v in sorted(pon.items())))
    if von:
        rest = rest_v(d)
        sag = ", ".join(f"{m:g} min {v:.3f}" + (f" ({1000 * (v - rest):+.0f})" if rest else "")
                        for m, v in sorted(von.items()))
        print(f"  V under load (mV from resting): {sag}")
