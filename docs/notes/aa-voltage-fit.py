#!/usr/bin/env python3
# Fits for docs/notes/aa-voltage.csv: how the firmware's % maps to the AA's voltage, per pairing of
# methods, scored against cjf vr' current line. Run: python3 -I docs/notes/aa-voltage-fit.py
import csv
import sys
from collections import defaultdict
from pathlib import Path

CURRENT = (1.09, 1.48)  # cjf vr's line: the firmware's % against the AA's voltage under load
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


def rest_v(d, after=15):
    # A resting voltage: out of the controller, else the latest reading in place after `after`
    # minutes or more. An untimed long rest (v_rest) counts as the latest of all.
    if "v_out" in d:
        return first(d, "v_out")
    if "v_rest" in d:
        return first(d, "v_rest")
    late = [m for m in d.get("v_in", {}) if m is not None and m >= after]
    return d["v_in"][max(late)] if late else None


# Each pairing: name, what it is, and a function from one cell's readings to (%, V) or None.
PAIRINGS = [
    ("out/on0", "resting V out, then % right after power-on (older method)",
     lambda d: (first(d, "pct_on", 0), first(d, "v_out"))),
    ("run/in0", "% running, then V in place at once (recent method)",
     lambda d: (first(d, "pct_run"), first(d, "v_in", 0))),
    ("run/load", "% running against V in place at that moment: what the firmware sees, and cjf vr",
     lambda d: (first(d, "pct_run"), first(d, "v_run"))),
    ("run/rest", "% running against resting V (15 min or more)",
     lambda d: (first(d, "pct_run"), rest_v(d))),
    ("run/rest2h", "% running against V after a rest of two hours or more",
     lambda d: (first(d, "pct_run"), rest_v(d, after=120))),
    ("on0/load0", "% right after power-on against V in place at that moment",
     lambda d: (first(d, "pct_on", 0), first(d, "v_on", 0))),
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

# What each session shows: the % and V drop during use, recovery after turn-off, and the %
# the firmware gives again at the next power-on.
def session_order(item):
    (test, side), _ = item
    digits = "".join(c for c in test if c.isdigit())
    return test[0], int(digits) if digits else 0, test, side


print("session: on %/V  ->  run %/V  | off V, recovery mV at minutes (untimed rest as 'rest')")
for (test, side), d in sorted(cells.items(), key=session_order):
    vin = {m: v for m, v in d.get("v_in", {}).items() if m is not None}
    if not vin:
        continue
    on_p, on_v = first(d, "pct_on", 0), first(d, "v_on", 0)
    run_p, run_v = first(d, "pct_run"), first(d, "v_run")
    on = f"{on_p:2.0f}%/{on_v:.3f}" if on_p is not None and on_v is not None else "    -    "
    run = f"{run_p:2.0f}%/{run_v:.3f}" if run_p is not None and run_v is not None else "    -    "
    base = vin[min(vin)]
    rec = f"{base:.3f}" + "".join(f" {1000 * (v - base):+.0f}@{m:g}"
                                 for m, v in sorted(vin.items()) if m > 0)
    if "v_rest" in d:
        rec += f" {1000 * (first(d, 'v_rest') - base):+.0f}@rest"
    print(f"{test:>4} {side}: {on} -> {run} | {rec}")
    von = {m: v for m, v in d.get("v_on", {}).items() if m is not None}
    if len(von) > 1:  # a timed power-on series: the sag under load, minute by minute
        series = " ".join(f"{v:.3f}@{m:g}" for m, v in sorted(von.items()))
        print(f"        on, V at minutes: {series}")

# The NiMH charge against the voltage under load, from this one pair of cells played from full
# to nearly empty. Charge is taken as play time left. Each reading is the % at the end of use,
# the steady voltage under load (a power-on reading after a rest still carries surface charge);
# its play time is the sum of the sessions so far, each from the log's stamps (the rest reading
# before a session is its power-on, the "after use" stamp its end) or UNDATED minutes where the
# log has none. R got EXTRA minutes of unlogged use between u18 (10-28) and u19 (10-30), sized
# from how its lead over L swung from +4 points to -3. What is left below R's last reading comes
# from a fresh Eneloop's 0.1 A curve (eneloop-0.1A.csv), shifted down by OFFSET: these cells read
# that much under it at the same depth. That curve's shape does not fit the log (13 mV rms at
# best, 20-30 mV too high through the middle), so only its tail is used.
UNDATED, EXTRA, OFFSET = 40, 130, 0.03
SESSIONS = [  # (session, minutes or None if undated, R % at end of use, L % at end of use)
    ("r9", 0, 79, 77), ("r10", None, 70, 68), ("r11", None, 71, 69), ("r12", None, 67, 64),
    ("r13", None, 63, 59), ("e60", None, 62, 59), ("u1", None, 56, 52), ("u3", None, 54, 52),
    ("u4", None, 52, 50), ("u5", None, 51, 49), ("u6", None, 50, 48), ("u7", 34, 49, 46),
    ("u8", 22, 48, 45), ("u9", None, 48, 44), ("u9b", None, None, None), ("u10", 35, 42, 41),
    ("u11", 94, 41, 39), ("u12", 22, 40, 37), ("u13", 56, 37, 34), ("u14", 34, 35, 31),
    ("u15", 27, 33, 29), ("u16", 33, 32, 29), ("u17", 22, 32, 28), ("u18", None, 30, 26),
    ("u19", None, 21, 24), ("u20", 90, 16, 21), ("u21", 54, 10, 19),
]
textbook = [(float(r["dod_pct"]), float(r["volts"])) for r in csv.DictReader(
    line for line in path.with_name("eneloop-0.1A.csv").open() if not line.startswith("#"))]


def textbook_left(volts):
    # % of capacity a fresh Eneloop has left at this voltage under 0.1 A
    for (d0, v0), (d1, v1) in zip(textbook, textbook[1:]):
        if v1 <= volts <= v0:
            return 100 - (d0 + (v0 - volts) / (v0 - v1) * (d1 - d0))
    return 100 if volts > textbook[0][1] else 0


def discharge(undated, extra):
    played, r_extra = 0, 0
    out = []  # (session, side, minutes played, V under load)
    for name, minutes, r, l in SESSIONS:
        played += undated if minutes is None else minutes
        if name == "u19":
            r_extra = extra
        if r is not None:
            out.append((name, "R", played + r_extra, ca + cb * r / 100))
        if l is not None:
            out.append((name, "L", played, ca + cb * l / 100))
    r_end = next(m for n, s, m, _ in out if n == "u21" and s == "R")
    tail = textbook_left(ca + cb * 0.10 + OFFSET)
    return out, r_end / (1 - tail / 100), tail


pts, total, tail = discharge(UNDATED, EXTRA)
print(f"\ndischarge: {total:.0f} min of play in all ({total / 60:.1f} h) with {UNDATED} min per "
      f"undated session,\n  {EXTRA} min extra on R, and {tail:.0f}% left at R's last reading by "
      "the textbook")
print("session   V under load   NiMH left")
for name, side, played, volts in pts:
    print(f"{name:>4} {side}   {volts:.3f}         {100 - 100 * played / total:5.1f}%")
print("sensitivity:")
for undated, extra in ((30, EXTRA), (50, EXTRA), (UNDATED, 90), (UNDATED, 170)):
    pts2, total2, _ = discharge(undated, extra)
    mid = next(100 - 100 * m / total2 for n, s, m, _ in pts2 if n == "u13" and s == "R")
    end = next(100 - 100 * m / total2 for n, s, m, _ in pts2 if n == "u21" and s == "L")
    print(f"  undated {undated}, extra {extra}: {total2 / 60:.1f} h in all, "
          f"R at u13 {mid:.0f}% left, L at u21 {end:.0f}% left")
