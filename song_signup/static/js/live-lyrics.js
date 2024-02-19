const lyricsText = document.getElementById("lyrics-text");

setInterval(populateLyrics, 1000);

async function populateLyrics() {
    if (drinkingWord === '') { // From constance, defined in base.html
        lyricsText.innerHTML = "<h2>We need to choose a drinking word!</h2>"
        return;
    }

    const res = await fetch("/current_lyrics");
    const data = await res.json();
    if (data.song_name) {
        const regex = new RegExp(`\\b(${drinkingWord}s?)\\b`, 'gi');
        const lyrics = data.lyrics.replace(regex, `<span class="drink-highlight">$1</span>`);
        lyricsText.innerHTML = `
        <h2>${data.song_name}</h2>
            <h3>${data.artist_name}</h3><br>
        <pre dir="auto">${lyrics}</pre>
    `
    } else {
        lyricsText.innerHTML = "<h2>Live lyrics not loaded yet</h2>"
    }
}

