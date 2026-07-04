#!/usr/bin/env python3
"""
Per-parser lyrics coverage report for a money-time.jmx run (from OUTSIDE, over HTTPS).

Unlike check_lyrics.py (which just asks "did ANY lyrics show up, PASS/FAIL"), this
breaks the result down BY PARSER so you can see which lyrics site found which song.
It is a SUMMARY to skim, not a pass/fail gate — it always exits 0.

How it attributes a lyric to a parser: the /alternative_lyrics/<id> page renders every
SongLyrics as "<title> | <artist> | <url>". The url's domain identifies the site, and
each site maps 1:1 to a parser (genius.com is the exception — both GeniusExaParser and
GeniusApiParser write genius.com urls, so they're reported together as "genius").

Flow:
  1. For singer indices 1..N, log in as the load-test singer (Loadsinger <run_id>n<i>)
     and read GET /get_current_songs to learn that singer's song id + name.
  2. Log in as a SUPERUSER and poll GET /alternative_lyrics/<id> (celery is async +
     rate-limited, so back off and retry until coverage stops growing).
  3. Print a per-song parser matrix and a per-parser tally.

Usage:
  ./check_parsers.py --run-id 1782288825 --count 40
"""
import argparse, re, sys, time, unicodedata
from collections import defaultdict
from urllib.parse import urlparse
import requests


def _dw(s):
    """Display width of a string: combining marks (Hebrew niqqud) 0, CJK wide 2, else 1."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def _pad(s, width, align):
    gap = max(0, width - _dw(s))
    if align == "r":
        return " " * gap + s
    if align == "c":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


def print_table(headers, rows, aligns):
    """Render a simple box-drawing table, alignment-aware for Hebrew/wide chars."""
    cols = len(headers)
    widths = [_dw(headers[i]) for i in range(cols)]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], _dw(str(r[i])))

    def rule(l, m, rr):
        return l + m.join("─" * (widths[i] + 2) for i in range(cols)) + rr

    def line(cells):
        return "│ " + " │ ".join(_pad(str(cells[i]), widths[i], aligns[i]) for i in range(cols)) + " │"

    print(rule("┌", "┬", "┐"))
    print(line(headers))
    print(rule("├", "┼", "┤"))
    for r in rows:
        print(line(r))
    print(rule("└", "┴", "┘"))

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
# One rendered lyric line: <a href="/lyrics_by_id/ID"> title | artist | url </a>
LYRIC_ANCHOR_RE = re.compile(r'lyrics_by_id/(\d+)"[^>]*>(.*?)</a>', re.DOTALL)

# domain (sans www.) -> parser bucket.  Mirrors the SITE of each parser in tasks.py.
DOMAIN_TO_PARSER = {
    "genius.com": "genius",                       # GeniusExaParser + GeniusApiParser
    "allmusicals.com": "allmusicals",
    "azlyrics.com": "azlyrics",
    "themusicallyrics.com": "themusicallyrics",
    "lyricstranslate.com": "lyricstranslate",
    "shironet.mako.co.il": "shironet",
}
# Fixed column order for the summary (so a parser that found nothing still shows as 0).
ALL_PARSERS = ["genius", "allmusicals", "azlyrics",
               "themusicallyrics", "lyricstranslate", "shironet"]


def login(base, first, last, passcode, freebie, existing=True):
    """Return an authenticated requests.Session, or raise."""
    s = requests.Session()
    s.headers["Referer"] = base + "/"
    r = s.get(base + "/login", timeout=30)
    m = CSRF_RE.search(r.text)
    if not m:
        raise RuntimeError("no csrf token on /login page")
    data = {
        "ticket-type": "singer", "first-name": first, "last-name": last,
        "passcode": passcode, "order-id": freebie, "no-upload": "on",
        "csrfmiddlewaretoken": m.group(1),
    }
    if existing:
        data["logged-in"] = "on"
    r = s.post(base + "/login", data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"login {first} {last} failed: HTTP {r.status_code} {r.text[:200]}")
    return s


def parsers_for_song(html):
    """Given an /alternative_lyrics page, return {parser: lyric_count} for that song."""
    counts = defaultdict(int)
    for _lid, text in LYRIC_ANCHOR_RE.findall(html):
        url = text.split("|")[-1].strip()
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        parser = DOMAIN_TO_PARSER.get(netloc)
        if parser:
            counts[parser] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, help="the -Jrun_id used in the load test")
    ap.add_argument("--count", type=int, default=40, help="how many singer indices to sample")
    ap.add_argument("--host", default="broadwaywithatwist.xyz")
    ap.add_argument("--protocol", default="https")
    ap.add_argument("--passcode", default="dev")
    ap.add_argument("--freebie", default="123456")
    ap.add_argument("--superuser", default="Alon Aviv", help="first last of a superuser")
    ap.add_argument("--retries", type=int, default=15)
    ap.add_argument("--interval", type=int, default=15, help="seconds between poll rounds")
    a = ap.parse_args()
    base = f"{a.protocol}://{a.host}"

    # --- phase 1: collect every sampled singer's song id + name ---------------
    # song_id -> (song_name, musical placeholder).  /get_current_songs gives song_name.
    songs = {}
    print(f"Collecting songs for up to {a.count} singers (run_id={a.run_id})...")
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
        print("No songs found — check --run-id / --count / passcode.")
        sys.exit(2)
    print(f"Found {len(songs)} song requests to inspect.\n")

    # --- phase 2: poll superuser lyrics pages, attribute each lyric to a parser
    su_first, su_last = a.superuser.split(" ", 1)
    su = login(base, su_first, su_last, a.passcode, a.freebie)

    per_song = {}  # song_id -> {parser: count}
    for attempt in range(1, a.retries + 1):
        for sid in songs:
            r = su.get(f"{base}/alternative_lyrics/{sid}", timeout=30)
            found = parsers_for_song(r.text)
            # keep the richest reading we've seen for this song (lyrics only accumulate)
            if sum(found.values()) >= sum(per_song.get(sid, {}).values()):
                per_song[sid] = found
        with_any = sum(1 for c in per_song.values() if c)
        total_lyrics = sum(sum(c.values()) for c in per_song.values())
        print(f"[round {attempt}/{a.retries}] songs with >=1 lyric: {with_any}/{len(songs)}"
              f"   total lyrics: {total_lyrics}")
        # stop early once every song has been found by every non-shironet parser
        done = all(
            all(per_song.get(sid, {}).get(p) for p in ALL_PARSERS if p != "shironet")
            for sid in songs
        )
        if done:
            break
        if attempt < a.retries:
            time.sleep(a.interval)

    # --- report: aggregate duplicate song NAMES (40 singers recycle 14 songs) --
    # For each unique song name, union the parsers found across all its instances.
    # Seed EVERY sampled song name first, so songs that found nothing still show
    # up as an all-dots row (and count toward the per-parser denominator).
    by_name = {name: defaultdict(int) for name in songs.values()}
    for sid, name in songs.items():
        for parser, cnt in per_song.get(sid, {}).items():
            by_name[name][parser] = max(by_name[name][parser], cnt)

    # --- pretty per-song table: "how many of how many parsers succeeded" ------
    n_parsers = len(ALL_PARSERS)
    rows = []
    for name in sorted(by_name):
        row = by_name[name]
        cells = [(f"✓{row[p]}" if row.get(p) else "·") for p in ALL_PARSERS]
        nfound = sum(1 for p in ALL_PARSERS if row.get(p))
        rows.append([name] + cells + [f"{nfound}/{n_parsers}"])

    headers = ["song"] + [p[:6] for p in ALL_PARSERS] + ["parsers ok"]
    aligns = ["l"] + ["c"] * n_parsers + ["r"]
    print("\nPER-SONG PARSER COVERAGE   (✓N = that parser found N lyrics · = none)")
    print_table(headers, rows, aligns)

    # --- per-parser summary ---------------------------------------------------
    n_names = len(by_name)
    psum_rows = []
    for p in ALL_PARSERS:
        songs_found = sum(1 for name in by_name if by_name[name].get(p))
        total = sum(by_name[name].get(p, 0) for name in by_name)
        psum_rows.append([p, f"{songs_found}/{n_names}", str(total)])
    print("\nPER-PARSER SUMMARY")
    print_table(["parser", "songs found", "total lyrics"], psum_rows, ["l", "r", "r"])

    print("\nNote: 'genius' = GeniusExaParser + GeniusApiParser combined (both use genius.com).")
    print("      This is a coverage summary, not a pass/fail gate.")
    sys.exit(0)


if __name__ == "__main__":
    main()
