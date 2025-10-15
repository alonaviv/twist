const lyricsText = document.getElementById("lyrics-text");
const lyricsWrapper = document.getElementById("lyrics-wrapper");
const nav = document.querySelector("nav");
const footer = document.querySelector("footer");
const logo = document.getElementById("lyrics-logo");
const logo_img = document.getElementById("logo-img");
const passcodeWrapper = document.getElementById("passcode-reveal-wrapper");
const passcodeReveal = document.getElementById("passcode-reveal");
const smallLogo = logo.getAttribute('data-small-logo');
const bigLogo = logo.getAttribute('data-big-logo');
let started = true;
let demoLyrics;

// Allow dragging on computers - useful for projector screen
if (!/Android|iPhone/i.test(navigator.userAgent)) {
    $("#lyrics-text").draggable({ containment: "#lyrics-wrapper" });
    nav.classList.add('screen');
    footer.classList.add('screen');
    lyricsWrapper.classList.add('screen');
    lyricsText.classList.add('screen');
    logo.classList.add('screen');
}


function toggleStarted() {
    if (started) {
        logo.classList.remove('not-started');
        logo_img.src = smallLogo;
        lyricsText.innerHTML = `
            <h2>${demoLyrics.song_name}</h2>
            <h3>${demoLyrics.artist_name}</h3><br>
            <pre dir="auto">${demoLyrics.lyrics || ''}</pre>
        `;
        passcodeWrapper.classList.remove('displayed');
        passcodeReveal.innerHTML = '';
    } else {
        document.body.scrollTop = document.documentElement.scrollTop = 0;
        logo.classList.add('not-started');
        logo_img.src = bigLogo;
        lyricsText.innerHTML = '';
        passcodeWrapper.classList.add('displayed');
        passcodeReveal.innerHTML = 'testing';
    }
}

// Fetch demo lyrics once
fetch("/demo_current_lyrics")
    .then(res => res.json())
    .then(data => {
        demoLyrics = data;
        toggleStarted();
    })
    .catch(() => { });

document.addEventListener('click', () => {
    started = !started;
    toggleStarted();
});


