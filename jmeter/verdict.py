#!/usr/bin/env python3
"""
Reads a JMeter .jtl (CSV) and prints a PASS/FAIL verdict against the money-time
benchmark.  Usage:  ./verdict.py results.jtl [--sla 2000] [--max-err 1.0]

PASS requires ALL of:
  * overall error rate            <  --max-err  %
  * 99th pct response time (all)  <  --sla      ms
  * 95th pct of POST /add_song_request (the signup burst) < 1.5 x --sla ms
"""
import csv, sys, argparse
from collections import defaultdict

def pct(values, p):
    if not values: return 0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * len(s) + 0.5)) - 1))
    return s[k]

ap = argparse.ArgumentParser()
ap.add_argument("jtl")
ap.add_argument("--sla", type=int, default=2000)
ap.add_argument("--max-err", type=float, default=1.0)
a = ap.parse_args()

elapsed_all, elapsed_signup = [], []
total = errors = 0
by_label_err = defaultdict(int); by_label_tot = defaultdict(int)

with open(a.jtl, newline="") as f:
    for row in csv.DictReader(f):
        try:
            el = int(row["elapsed"])
        except (KeyError, ValueError):
            continue
        total += 1
        label = row.get("label", "")
        by_label_tot[label] += 1
        ok = row.get("success", "true") == "true"
        if not ok:
            errors += 1; by_label_err[label] += 1
        elapsed_all.append(el)
        if label == "POST /add_song_request":
            elapsed_signup.append(el)

if total == 0:
    print("No samples found in", a.jtl); sys.exit(2)

err_pct = 100.0 * errors / total
p99 = pct(elapsed_all, 99)
sp95 = pct(elapsed_signup, 95) if elapsed_signup else 0

print(f"\n=== money-time verdict: {a.jtl} ===")
print(f"samples              : {total}")
print(f"error rate           : {err_pct:.2f}%   (limit < {a.max_err}%)")
print(f"p99 response (all)   : {p99} ms        (limit < {a.sla} ms)")
print(f"p95 signup burst     : {sp95} ms        (limit < {int(a.sla*1.5)} ms)  n={len(elapsed_signup)}")
print("\nworst endpoints by error rate:")
for lbl in sorted(by_label_tot, key=lambda l: -by_label_err[l]/by_label_tot[l])[:5]:
    e = 100.0*by_label_err[lbl]/by_label_tot[lbl]
    print(f"  {e:6.2f}%  {by_label_err[lbl]:>5}/{by_label_tot[lbl]:<5}  {lbl}")

ok = err_pct < a.max_err and p99 < a.sla and sp95 < a.sla*1.5
print("\n>>> VERDICT:", "PASS ✅" if ok else "FAIL ❌", "\n")
sys.exit(0 if ok else 1)
