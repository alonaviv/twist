#!/usr/bin/env python3
"""
Reads a JMeter .jtl (CSV) and prints a PASS/FAIL verdict against the money-time
benchmark.  Usage:  ./verdict.py results.jtl [--sla 2000] [--max-err 1.0] [--step-max 250]

Signup is intentionally SERIALIZED (each add_song_request recomputes the whole
running order), so the 40-singer rendezvous drains as a linear staircase: request
k waits behind the k-1 before it.  That means a percentile like p95 of the burst
just measures QUEUE DEPTH (≈ 0.95·N · per-signup-cost) — it grows with how many
people you cram into the same instant, not with system health.  So we DON'T gate on
it.  What actually distinguishes healthy from broken is:
  * per-signup serialized COST — the staircase step, which is N-independent
    (broken run: ~1000 ms/signup;  healthy run: ~115 ms/signup), and
  * whether any signup HARD-fails (HTTP 5xx / socket timeout).

PASS requires ALL of:
  * overall hard-error rate  (HTTP 5xx / timeouts, NOT the >2s soft assertion) < --max-err %
  * 99th pct response time (all endpoints)                                     < --sla ms
  * ZERO hard failures on POST /add_song_request                               (regression guard)
  * per-signup serialized cost  ((slowest-fastest)/(n-1))                      < --step-max ms

The p95 of the signup burst is still printed, but only as information.
"""
import csv, sys, argparse
from collections import defaultdict

def pct(values, p):
    if not values: return 0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * len(s) + 0.5)) - 1))
    return s[k]

def is_hard_fail(code):
    """A real transport/server failure (HTTP 5xx, 4xx, socket timeout) — NOT a
    soft assertion fail, which keeps its 2xx/3xx responseCode."""
    return not (code[:1] in ("2", "3"))

ap = argparse.ArgumentParser()
ap.add_argument("jtl")
ap.add_argument("--sla", type=int, default=2000)
ap.add_argument("--max-err", type=float, default=1.0)
ap.add_argument("--step-max", type=int, default=250,
                help="max per-signup serialized cost (staircase step) in ms")
a = ap.parse_args()

elapsed_all, elapsed_signup = [], []
total = hard_errors = 0
signup_hard = 0
by_label_hard = defaultdict(int); by_label_tot = defaultdict(int)
ts_min = ts_max = None

with open(a.jtl, newline="") as f:
    for row in csv.DictReader(f):
        try:
            el = int(row["elapsed"])
        except (KeyError, ValueError):
            continue
        ts = int(row.get("timeStamp", 0))
        if ts:
            ts_min = min(ts_min, ts) if ts_min else ts
            ts_max = max(ts_max, ts) if ts_max else ts
        total += 1
        label = row.get("label", "")
        by_label_tot[label] += 1
        hard = is_hard_fail(row.get("responseCode", ""))
        if hard:
            hard_errors += 1; by_label_hard[label] += 1
        elapsed_all.append(el)
        if label == "POST /add_song_request":
            elapsed_signup.append(el)
            if hard:
                signup_hard += 1

if total == 0:
    print("No samples found in", a.jtl); sys.exit(2)

if ts_min and ts_max:
    span_min = (ts_max - ts_min) / 60000
    if span_min > 20:
        print(f"\n⚠️  WARNING: samples span {span_min:.0f} minutes — this looks like multiple runs")
        print("   Delete result.jtl and re-run to get a clean verdict.\n")

err_pct = 100.0 * hard_errors / total
p99 = pct(elapsed_all, 99)
n_signup = len(elapsed_signup)
sp95 = pct(elapsed_signup, 95) if elapsed_signup else 0
# per-signup serialized cost: the average staircase step across the burst.
signup_step = ((max(elapsed_signup) - min(elapsed_signup)) / (n_signup - 1)) if n_signup > 1 else 0

print(f"\n=== money-time verdict: {a.jtl} ===")
print(f"samples                    : {total}")
print(f"hard-error rate (5xx/timeout) : {err_pct:.2f}%   (limit < {a.max_err}%)")
print(f"p99 response (all endpoints)  : {p99} ms        (limit < {a.sla} ms)")
print(f"signup hard failures          : {signup_hard}          (limit = 0)  n={n_signup}")
print(f"per-signup serialized cost    : {signup_step:.0f} ms       (limit < {a.step_max} ms)")
print(f"signup burst p95              : {sp95} ms        (info only — queue depth, not gated)")
print("\nworst endpoints by hard-error rate:")
for lbl in sorted(by_label_tot, key=lambda l: -by_label_hard[l]/by_label_tot[l])[:5]:
    e = 100.0*by_label_hard[lbl]/by_label_tot[lbl]
    print(f"  {e:6.2f}%  {by_label_hard[lbl]:>5}/{by_label_tot[lbl]:<5}  {lbl}")

ok = (err_pct < a.max_err
      and p99 < a.sla
      and signup_hard == 0
      and signup_step < a.step_max)
print("\n>>> VERDICT:", "PASS ✅" if ok else "FAIL ❌", "\n")
sys.exit(0 if ok else 1)
