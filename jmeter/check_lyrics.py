#!/usr/bin/env python3
"""
Validates (from OUTSIDE, over HTTPS) that exa.ai actually found lyrics for the songs
created by a money-time.jmx run. Celery processes lyrics asynchronously and is rate-limited,
so this polls with backoff before giving up.

How it works:
  1. For singer indices 1..N it logs in as the existing load-test singer (Loadsinger <run_id>n<i>)
     and reads GET /get_current_songs to learn that singer's song id + name.
  2. It logs in as a SUPERUSER (name-based login, just needs the event passcode — no admin password)
     and polls GET /alternative_lyrics/<song_id>, counting the per-lyric links the page renders.
  3. PASS once at least --threshold of the sampled songs have >=1 lyric.

Usage:
  ./check_lyrics.py --run-id 1782288825 --count 10
  (run-id must match the -Jrun_id you used for the load test)
"""
import argparse, re, sys, time
import requests

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
LYRIC_LINK_RE = re.compile(r'lyrics_by_id')

def login(base, first, last, passcode, freebie, ticket="singer", existing=True):
    """Return an authenticated requests.Session, or raise."""
    s = requests.Session()
    s.headers["Referer"] = base + "/"
    r = s.get(base + "/login", timeout=30)
    m = CSRF_RE.search(r.text)
    if not m:
        raise RuntimeError("no csrf token on /login page")
    data = {
        "ticket-type": ticket, "first-name": first, "last-name": last,
        "passcode": passcode, "order-id": freebie, "no-upload": "on",
        "csrfmiddlewaretoken": m.group(1),
    }
    if existing:
        data["logged-in"] = "on"
    r = s.post(base + "/login", data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"login {first} {last} failed: HTTP {r.status_code} {r.text[:200]}")
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, help="the -Jrun_id used in the load test")
    ap.add_argument("--count", type=int, default=10, help="how many singers to sample")
    ap.add_argument("--host", default="broadwaywithatwist.xyz")
    ap.add_argument("--protocol", default="https")
    ap.add_argument("--passcode", default="dev")
    ap.add_argument("--freebie", default="123456")
    ap.add_argument("--superuser", default="Alon Aviv", help="first last of a superuser")
    ap.add_argument("--retries", type=int, default=12)
    ap.add_argument("--interval", type=int, default=15, help="seconds between poll rounds")
    ap.add_argument("--threshold", type=int, default=1, help="min songs-with-lyrics to PASS")
    a = ap.parse_args()
    base = f"{a.protocol}://{a.host}"

    # --- phase 1: collect each sampled singer's song id ------------------------
    songs = {}  # song_id -> song_name
    print(f"Collecting songs for {a.count} singers (run_id={a.run_id})...")
    for i in range(1, a.count + 1):
        last = f"{a.run_id}n{i}"
        try:
            s = login(base, "Loadsinger", last, a.passcode, a.freebie)
            r = s.get(base + "/get_current_songs", timeout=30)
            for song in r.json():
                songs[song["id"]] = song.get("song_name", "?")
        except Exception as e:
            print(f"  singer {i}: skipped ({e})")
    if not songs:
        print("No songs found — check --run-id / --count / passcode."); sys.exit(2)
    print(f"Found {len(songs)} songs to check.\n")

    # --- phase 2: poll the superuser lyrics page with backoff ------------------
    su_first, su_last = a.superuser.split(" ", 1)
    su = login(base, su_first, su_last, a.passcode, a.freebie)
    found = {}  # song_id -> lyric count
    for attempt in range(1, a.retries + 1):
        for sid, name in songs.items():
            if found.get(sid):
                continue
            r = su.get(f"{base}/alternative_lyrics/{sid}", timeout=30)
            n = len(LYRIC_LINK_RE.findall(r.text))
            if n:
                found[sid] = n
        got = len(found)
        print(f"[round {attempt}/{a.retries}] songs with lyrics: {got}/{len(songs)}"
              f"  (lyrics found so far: {sum(found.values())})")
        if got >= a.threshold and got == len(songs):
            break
        if attempt < a.retries:
            time.sleep(a.interval)

    print("\n=== lyrics validation ===")
    for sid, name in songs.items():
        print(f"  {'OK ' if found.get(sid) else 'no '} song {sid:>5}  {found.get(sid,0)} lyrics  {name}")
    got = len(found)
    ok = got >= a.threshold
    print(f"\n{got}/{len(songs)} songs got lyrics from exa.ai  (threshold {a.threshold})")
    print(">>> VERDICT:", "PASS ✅" if ok else "FAIL ❌", "\n")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
