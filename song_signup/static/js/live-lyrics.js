const lyricsText = document.getElementById("lyrics-text");
const lyricsWrapper = document.getElementById("lyrics-wrapper");
const nav = document.querySelector("nav");
const footer = document.querySelector("footer");
const logo = document.querySelector(".fixed-logo");
const passcodeWrapper = document.getElementById("passcode-reveal-wrapper");
const passcodeReveal = document.getElementById("passcode-reveal");
let currentSong = '';

setInterval(populateLyrics, 1000);

// Allow dragging on computers - useful for projector screen
if (!/Android|iPhone/i.test(navigator.userAgent)) {
    $("#lyrics-text").draggable({ containment: "#lyrics-wrapper" });
    nav.classList.add('screen');
    footer.classList.add('screen');
    lyricsWrapper.classList.add('screen');
    lyricsText.classList.add('screen');
    logo.classList.add('screen');
    passcodeWrapper?.classList?.add('screen');
}

async function populateLyrics() {
    const startedRes = await fetch("/evening_started");
    const eveningStarted = (await startedRes.json()).started
    if (!eveningStarted) {
        logo.classList.add('not-started');
        lyricsText.innerHTML = ""

        if (passcodeWrapper) {
            const passcodeRes = await fetch("/passcode");
            const passcode = (await passcodeRes.json()).passcode;
            if (passcode === '') {
                passcodeWrapper.classList.add('hidden');
            } else {
                passcodeWrapper.classList.remove('hidden');
                passcodeReveal.innerHTML = passcode;
            }
        }
        return;
    }
    else {
        logo.classList.remove('not-started');
    }

    const lyricsRes = await fetch("/current_lyrics");
    const lyricsData = await lyricsRes.json();
    if (lyricsData.song_name) {
        var lyrics = lyricsData.lyrics;
        const resDrinking = await fetch("/drinking_word");
        const drinkingWord = (await resDrinking.json()).drinking_word;

        if (drinkingWord !== "") {
            const regex = new RegExp(`\\b(${drinkingWord}s?)\\b`, 'gi');
            lyrics = lyricsData.lyrics.replace(regex, `<span class="drink-highlight">$1</span>`);
        }
        lyricsText.innerHTML = `
        <h2>${lyricsData.song_name}</h2>
            <h3>${lyricsData.artist_name}</h3><br>
        <pre dir="auto">${lyrics}</pre>
    `
    } else {
        lyricsText.innerHTML = "<h2>Loading Lyrics...</h2>"
    }

    if (lyricsData.song_name != currentSong) {
        currentSong = lyricsData.song_name;
        window.scrollTo(0, 0);
    }
}

