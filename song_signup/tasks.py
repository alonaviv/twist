import dataclasses
import os
import re
import time
from logging import getLogger
from typing import Iterable, Optional
from urllib.parse import urlparse
from exa_py import Exa

import bs4
import requests
import sherlock
from celery import shared_task
from redis import Redis

from .models import GroupSongRequest, SongLyrics, SongRequest

logger = getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
LOCATION = "Austin,Texas,United States"

# Browser-like headers to avoid being blocked
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.azlyrics.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
}

exa_key = os.environ["EXA_KEY"]
genius_key = os.environ["GENIUS_KEY"]

# Lock for throttling requests to the same site. Will only be acquired, not released, and then let to expire.
sherlock.configure(
    backend=sherlock.backends.REDIS, expire=1, client=Redis(host="redis")
)

# Using exa.ai as replacement for google search
exa = Exa(api_key=exa_key)

@dataclasses.dataclass
class LyricsResult:
    lyrics: str
    title: str
    artist: str
    url: str | None

#############################################################################
### MAKE SURE TO ADD NEW WORKER TO start-celery.sh WHEN ADDING NEW PARSER ###
###########################################################################
class LyricsWebsiteParser:
    URL_FORMAT = re.compile("")
    SITE = ""

    def exa_search(self, query):
        # For testing - use query: "mama I'm a big girl now lyrics hairspray site:allmusicals.com"

        res = exa.search(
            query,
            include_domains=[self.SITE]
        )

        return [result.url for result in res.results]


    def fix_url(self, url):
        # Perform any necessary fixups on URL before requesting
        return url

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> Optional[LyricsResult]:
        return None

    def get_url(self, url: str) -> requests.Response:
        return requests.get(url, headers={"User-Agent": USER_AGENT})

    def get_lyrics(self, song_name: str, author: str) -> Iterable[LyricsResult]:
        lock = sherlock.Lock(self.SITE)
        seen_urls = set()
        search_query = '"{}" lyrics "{}"'.format(song_name, author)

        for _ in range(3):
            search_results = self.exa_search(search_query)
            if len(search_results) > 0:
                break
            logger.info("No search results, retrying")

        for search_result in search_results:
            url = self.fix_url(search_result)

            if url in seen_urls:
                continue
            seen_urls.add(url)

            if not self.URL_FORMAT.search(url):
                continue

            lock.acquire()  # Expires on its own after an interval (for throttling)
            logger.info(f"Performing query on {url}")

            try:
                r = self.get_url(url)
            except Exception:
                logger.exception(f"Received exception when requesting URL {url}")
                continue

            if not r.status_code == 200:
                logger.warning(f"Received status {r.status_code} for URL {url}")
                continue

            soup = bs4.BeautifulSoup(r.text, features="html.parser")

            try:
                result = self.parse_lyrics(soup)

                if not result:
                    logger.warning(
                        f"Unable to parse search result {search_result}"
                    )
                    # Something is broken in the parser, let's skip it
                    break

                result.url = url
                yield result
            except Exception as e:
                # Skip exceptions in individual parsers
                logger.exception(f"Exception in parser for url {search_result}")


class GeniusExaParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("genius\.com\/.*-lyrics$")
    SITE = "genius.com"

    def fix_url(self, url):
        # Common URLs that are close enough that we can just fixup
        return url.removesuffix("/q/writer").removesuffix("/q/producer")

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> LyricsResult:
        page_title = soup.find("title").text
        artist, title = page_title.split("–")[
            :2
        ]  # Note that this is a unicode character
        artist = artist.strip()
        if "Lyrics" in title:
            title = title[: title.index("Lyrics")]
        title = title.strip()

        for br in soup.find_all("br"):
            br.replace_with("\n")

        lyrics_parts = []
        for verse in soup.findAll("div", {"data-lyrics-container": "true"}):
            # Remove elements marked for exclusion (headers, navigation, etc.)
            for excluded in verse.find_all(attrs={"data-exclude-from-selection": "true"}):
                excluded.decompose()
            lyrics_parts.append(verse.get_text())

        return LyricsResult(
            lyrics="\n\n".join(lyrics_parts),
            artist=artist,
            title=title,
            url=None,
        )


class GeniusApiParser(LyricsWebsiteParser):
    """
    Genius parser using the official Genius API (via RapidAPI).
    This is separate from GeniusExaParser which uses Exa search to scrape the website.
    """
    URL_FORMAT = re.compile("genius\.com")
    SITE = "genius.com"

    @property
    def api_headers(self):
        return {
            "X-RapidAPI-Key": genius_key,
            "X-RapidAPI-Host": "genius-song-lyrics1.p.rapidapi.com"
        }

    def search_api(self, query) -> list:
        """
        Returns list of matching song ids
        """
        endpoint = "https://genius-song-lyrics1.p.rapidapi.com/search/"
        params = {'q': query}
        res = requests.get(endpoint, params=params, headers=self.api_headers)
        return [hit['result']['id'] for hit in res.json()['hits']]

    def lyric_api(self, song_id) -> dict:
        endpoint = "https://genius-song-lyrics1.p.rapidapi.com/song/lyrics/"
        params = {'id': song_id, 'text_format': 'plain'}
        res = requests.get(endpoint, params=params, headers=self.api_headers)
        return res.json()['lyrics']

    def get_lyrics(self, song_name: str, author: str) -> Iterable[LyricsResult]:
        search_query = f"{author} {song_name}"
        song_ids = self.search_api(search_query)
        for song_id in song_ids:
            try:
                res = self.lyric_api(song_id)
            except Exception:
                logger.exception(f"Exception when requesting lyrics via Genius API for song {song_id}")
                continue

            try:
                lyrics = res['lyrics']['body']['plain']
                title = res['tracking_data']['title']
                album = res['tracking_data']['primary_album'] or res['tracking_data']['primary_artist']
                url = "https://" + self.SITE + res['path']
            except Exception:
                logger.exception(f"Exception when extracting API lyrics data for song {song_id}")
                continue

            yield LyricsResult(
                lyrics=lyrics,
                artist=album or author,
                title=title,
                url=url,
            )


class AllMusicalsParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("allmusicals\.com\/lyrics\/.*\.htm$")
    SITE = "allmusicals.com"

    def get_url(self, url: str) -> requests.Response:
        # AllMusicals is using a cert that is not always trusted
        return requests.get(url, headers={"User-Agent": USER_AGENT}, verify=False)

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> LyricsResult:
        page_title = soup.find("title").text
        if "-" in page_title:
            title, artist = page_title.split("-")[:2]
        elif "—" in page_title:
            # This is a different dash character
            title, artist = page_title.split("—")[:2]
        else:
            raise Exception(f"Unknown page title format: {page_title}")

        if "Lyrics" in title:
            title = title[: title.index("Lyrics")]
        title = title.strip()
        artist = artist.strip()

        for element in soup.find_all(attrs={"class": "muted"}):
            element.replace_with("")

        for element in soup.find_all(attrs={"class": "visible-print"}):
            element.replace_with("")

        lyrics_container = soup.find("div", {"id": "page"})
        if lyrics_container is None:
            lyrics_container = soup.find("div", {"class": "main-text"})

        if lyrics_container is None:
            raise Exception(f"No lyrics container found for {page_title}")

        return LyricsResult(
            lyrics=lyrics_container.text.strip(),
            artist=artist,
            title=title,
            url=None,
        )


class AzLyricsParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("azlyrics.com\/lyrics\/.*html$")
    SITE = "azlyrics.com"

    def __init__(self):
        # Use a session to maintain cookies between requests
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)

    def get_url(self, url: str) -> requests.Response:
        # Use session with browser-like headers to avoid being blocked
        if not hasattr(self, '_session_initialized'):
            # First visit homepage to establish session and cookies
            self.session.get("https://www.azlyrics.com/", timeout=10)
            time.sleep(0.5)  # Small delay to simulate human behavior
            # Visit a search page to establish browsing context
            self.session.get("https://www.azlyrics.com/search.html", timeout=10)
            self._session_initialized = True
        
        # Extract base path from URL to set appropriate Referer
        # URLs are like https://www.azlyrics.com/lyrics/artist/song.html
        # So referer should be like https://www.azlyrics.com/lyrics/artist/ or homepage
        try:
            parsed = urlparse(url)
            if '/lyrics/' in parsed.path:
                # Extract artist path for more realistic referer
                path_parts = parsed.path.split('/')
                if len(path_parts) >= 3:
                    referer_path = '/'.join(path_parts[:3]) + '/'
                    referer = f"{parsed.scheme}://{parsed.netloc}{referer_path}"
                else:
                    referer = f"{parsed.scheme}://{parsed.netloc}/"
            else:
                referer = f"{parsed.scheme}://{parsed.netloc}/"
        except Exception:
            referer = "https://www.azlyrics.com/"
        
        # Update Referer to make request appear to come from browsing the site
        headers = BROWSER_HEADERS.copy()
        headers["Referer"] = referer
        
        # Small delay before request to avoid appearing automated
        time.sleep(0.3)
        
        return self.session.get(url, headers=headers, timeout=10)

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> Optional[LyricsResult]:
        page_title = soup.find("title").text
        artist, title = page_title.split("-")[:2]

        if "Lyrics" in title:
            title = title[: title.index("Lyrics")]
        title = title.strip()
        artist = artist.strip()

        if "request for access" in title:
            # Oops we're blocked, need to find workaround later :(
            return None

        return LyricsResult(
            lyrics=max(soup.findAll("div", {"class": None}), key=len).text.strip(),
            artist=artist,
            title=title,
            url=None,
        )


class TheMusicalLyricsParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("themusicallyrics\.com\/.*\/.*-lyrics\/.*-lyrics\.html$")
    SITE = "themusicallyrics.com"

    def fix_url(self, url):
        # Something is broken with the SSL cert on this site when using
        # requests (but not when using browser). For now just use http
        return url.replace("https://", "http://")

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> LyricsResult:
        page_title = soup.find("title").text
        artist, title = page_title.split("-")[:2]

        if "Lyrics" in title:
            title = title[: title.index("Lyrics")]
        title = title.strip()
        artist = artist.strip()

        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Remove extra title
        for tag in soup.find_all("strong"):
            tag.replace_with("")

        # The correct p has a script tag in the middle that injects a tracking tag
        # First try: p tags that contain script as a child
        p_with_script_child = [p for p in soup.find_all("p") if p.find("script")]
        
        if p_with_script_child:
            lyrics = p_with_script_child[0].text.strip()
        else:
            # Second try: find the longest p tag that has a script relationship (sibling or child)
            p_with_script_relationship = [
                p for p in soup.find_all("p")
                if p.find("script") or p.find_next_sibling("script") or p.find_previous_sibling("script")
            ]
            if p_with_script_relationship:
                # Pick the longest one (lyrics are typically the longest text)
                lyrics = max(p_with_script_relationship, key=lambda p: len(p.text.strip())).text.strip()
            else:
                raise Exception("Could not find lyrics paragraph with script tag")

        return LyricsResult(
            lyrics=lyrics,
            artist=artist,
            title=title,
            url=None,
        )


class LyricsTranslateParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("lyricstranslate\.com\/.*-lyrics$")
    SITE = "lyricstranslate.com"

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> LyricsResult:
        page_title = soup.find("title").text
        artist, title = page_title.split("-")[:2]

        if "[" in title:
            title = title[: title.index("[")]

        if "lyrics" in title:
            title = title[: title.index("lyrics")]
        title = title.strip()
        artist = artist.strip()

        for br in soup.find_all("br"):
            br.replace_with("\n")

        return LyricsResult(
            lyrics="\n\n".join(
                verse.get_text() for verse in soup.find_all("div", {"class": "par"})
            ),
            artist=artist,
            title=title,
            url=None,
        )


class ShironetParser(LyricsWebsiteParser):
    URL_FORMAT = re.compile("type=lyrics")
    SITE = "shironet.mako.co.il"

    def parse_lyrics(self, soup: bs4.BeautifulSoup) -> LyricsResult:
        artist = ""
        title = ""

        title_tag = soup.find("h1", {"class": "artist_song_name_txt"})
        if title_tag:
            title = title_tag.text.strip()
        artist_tag = soup.find("a", {"class": "artist_singer_title"})
        if artist_tag:
            artist = artist_tag.text.strip()

        for br in soup.find_all("br"):
            br.replace_with("\n")

        return LyricsResult(
            lyrics=soup.find("span", {"itemprop": "Lyrics"}).text.strip(),
            artist=artist,
            title=title,
            url=None,
        )


PARSERS = {parser.__name__: parser for parser in LyricsWebsiteParser.__subclasses__()}


@shared_task
def get_lyrics(song_id: int | None = None, group_song_id: int | None = None):
    if song_id is not None:
        assert group_song_id is None
        song = SongRequest.objects.get(id=song_id)

        # Delete old lyrics
        SongLyrics.objects.filter(song_request=song).delete()
    else:
        assert group_song_id is not None
        song = GroupSongRequest.objects.get(id=group_song_id)

        # Delete old lyrics
        SongLyrics.objects.filter(group_song_request=song).delete()

    for parser_name in PARSERS:
        get_lyrics_for_provider.apply_async(args=(parser_name, song_id, group_song_id), queue=f'parser_{parser_name}_queue')


@shared_task(rate_limit="0.5/s")
def get_lyrics_for_provider(
    parser_name: str, song_id: int | None, group_song_id: int | None
):
    parser = PARSERS[parser_name]

    if song_id is not None:
        assert group_song_id is None
        song = SongRequest.objects.get(id=song_id)
    else:
        assert group_song_id is not None
        song = GroupSongRequest.objects.get(id=group_song_id)

    for i, result in enumerate(parser().get_lyrics(song.song_name, song.musical)):
        SongLyrics.objects.create(
            song_name=result.title,
            artist_name=result.artist,
            url=result.url,
            lyrics=result.lyrics,
            song_request=song if song_id is not None else None,
            group_song_request=song if group_song_id is not None else None,
        )

        # 3 lyrics per site
        if i == 2:
            break
