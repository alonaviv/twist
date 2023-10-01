from celery import shared_task
from duckduckgo_search import DDGS
from .models import GroupSongRequest, SongRequest, SongLyrics

import bs4
import re
import requests

GENIUS_URL_FORMAT = re.compile("genius\.com\/.*-lyrics$")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

@shared_task
def get_lyrics(song_id: int | None = None, group_song_id: int | None = None):
    if song_id is not None:
        assert group_song_id is None
        song = SongRequest.objects.get(id=song_id)

        # Delete old lyrics
        SongLyrics.objects.filter(song_request = song).delete()
    else:
        assert group_song_id is not None
        song = GroupSongRequest.objects.get(id=group_song_id)

        # Delete old lyrics
        SongLyrics.objects.filter(group_song_request = song).delete()

    with DDGS() as ddgs:
        search_results = ddgs.text("{} lyrics {} site:genius.com".format(song.song_name, song.musical))
        for result in search_results:
            url = result['href']

            # Common close URLs
            url = url.removesuffix("/q/writer")
            url = url.removesuffix("/q/producer")

            if not GENIUS_URL_FORMAT.search(url):
                continue

            r = requests.get(url, headers={"User-Agent": USER_AGENT})
            if not r.status_code == 200:
                continue

            soup = bs4.BeautifulSoup(r.content.decode(), features="html.parser")

            page_title = soup.find("title").text
            artist, title = page_title.split("–") # Note that this is a unicode character
            artist = artist.strip()
            title = title[:title.index("Lyrics")].strip()

            for br in soup.find_all("br"):
                br.replace_with("\n")

            lyrics = '\n\n'.join(
                verse.get_text() for verse in 
                soup.findAll("div", {"data-lyrics-container": "true"})
            )

            SongLyrics.objects.create(
                song_name = title,
                artist_name = artist,
                url = url,
                lyrics = lyrics,
                song_request = song if song_id is not None else None,
                group_song_request = song if group_song_id is not None else None,
            )

            # TODO - grab more than 1 lyrics in case first one is wrong
            break