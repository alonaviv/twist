const lyricsText = document.getElementById("lyrics-text");
const lyricsWrapper = document.getElementById("lyrics-wrapper");
const nav = document.querySelector("nav");
const footer = document.querySelector("footer");
const logo = document.getElementById("lyrics-logo");
const logo_img = document.getElementById("logo-img");
const passcodeWrapper = document.getElementById("passcode-reveal-wrapper");
const passcodeReveal = document.getElementById("passcode-reveal");
const bohoWrapper = document.getElementById("boho-wrapper")
const questionText = document.querySelector(".question-text.live-lyrics-trivia");
const questionImage = document.getElementById("question-image-lyrics");
const triviaQuestionsWrapper = document.querySelector(".trivia-questions-wrapper.live-lyrics-trivia");
const triviaWinnerWrapper = document.querySelector(".trivia-winner-wrapper.live-lyrics-trivia");
const triviaWrapper = document.querySelector(".trivia-wrapper.live-lyrics-trivia");
const triviaWinnerName = document.querySelector(".trivia-winner-name.live-lyrics-trivia");
const triviaAnswer = document.querySelector(".trivia-answer.live-lyrics-trivia");
const triviaAnswerTitle = document.querySelector(".trivia-answer-title.live-lyrics-trivia");
const raffleWinnerWrapper = document.querySelector(".raffle-winner-wrapper");
const raffleWinnerTitle = document.querySelector(".raffle-winner-title");
const raffleWinnerName = document.querySelector(".raffle-winner-name");
const raffleWinnerDescription = document.querySelector(".raffle-winner-description");
let currentSong = '';
let showPasscode = false;
let activeRaffleWinner = false;


// Allow dragging on computers - useful for projector screen
if (!/Android|iPhone/i.test(navigator.userAgent)) {
    $("#lyrics-text").draggable({ containment: "#lyrics-wrapper" });
    nav.classList.add('screen');
    footer.classList.add('screen');
    lyricsWrapper.classList.add('screen');
    lyricsText.classList.add('screen');
    logo.classList.add('screen');
    if (isSuperuser) {
        showPasscode = true;
    }
}


const bohoDaysLyrics = `
<h4 id="bsod-title">Broadway With a Twist</h4>
<pre dir="auto" id="bsod-text">
An error has occurred.
We are restarting your pianist and/or MC in order to resume the evening.
In the meantime.. You know what to do:
</pre>
<h2>Boho Days</h2>
<h3>Tick, Tick... Boom!</h3>
<pre dir="auto">

Clap-clap, clap
Clap-clap, clap
Clap-clap, clap
Clap-clap, clap

This is the life, bo-bo, bo-bo-bo
This is the life, bo-bo, bo-bo-bo
This is the life, bo-bo, bo-bo-bo
Bohemia

Shower's in the kitchen, there might be some soap
Dishes in the sink, brush your teeth if you can cope
Toilet's in the closet, you better hope
There's a light bulb in there ( not today )

Revolving door roommates prick up your ears
14 people in just four years
Ann, and Max, and Jonathan, and Carolyn, and Kerri
David, Tim, no, Tim was just a guest from June to January
Margaret, Lisa, David, Susie, Stephen, Joe, and Sam
And Elsa, the bill collector's dream who still is on the lam

Don't forget the neighbors, Michelle and Gay
More like a family than your family, hey
The time is flying and everything is dying
I thought by now I'd have a dog, a kid, and wife
The ship is sort of sinking, so let's start drinking
Before we start thinking, "Is this the life?" ( Yeah )

This is the life, bo-bo, bo-bo-bo
This is the life, bo-bo, bo-bo-bo
This is the life, bo-bo, bo-bo-bo
Bohemia ( ya-ya-ya )

Bohemia ( woo-oo-oo )
One more time!
Bohemia
Bo-bo, bo-bo-bo, whoa!
</pre>
`

setInterval(populateLyrics, 1000);

async function populateLyrics() {
    const startedRes = await fetch("/evening_started");
    const eveningStarted = (await startedRes.json()).started;
    const bohoRes = await fetch("/boho_started");
    const boho = (await bohoRes.json()).boho;
    const questionRes = await fetch("/get_active_question");
    const question = await questionRes.json();
    const raffleWinnerRes = await fetch("/get_active_raffle_winner");
    const raffleWinner = await raffleWinnerRes.json();

    if (questionRes.status === 200 && Object.keys(question).length > 0 && isSuperuser) {
        const winner = question.winner;
        const image = question.image

        if (winner === null) {
            questionText.innerHTML = `<p style="font-size: ${question.question_font_size_live_lyrics}px;">${question.question}</p>`;
            if (image) {
                questionImage.src = image;
                questionImage.classList.remove('hidden');
            }
            else {
                questionImage.classList.add('hidden');
            }

            triviaQuestionsWrapper.classList.remove('hidden');
            triviaWinnerWrapper.classList.add('hidden');

            triviaWinnerName.classList.remove('active');
            triviaAnswer.classList.remove('active');
            triviaAnswerTitle.classList.remove('active');
        }
        else {
            triviaWinnerName.innerHTML = `<p>${winner}</p>`
            triviaAnswer.innerHTML = `<p>${question.answer_text}</p>`
            triviaQuestionsWrapper.classList.add('hidden');
            triviaWinnerWrapper.classList.remove('hidden');
            setTimeout(() => {
                triviaWinnerName.classList.add('active');
                triviaAnswer.classList.add('active');
                triviaAnswerTitle.classList.add('active');
            }, 5000)
        }
        triviaWrapper.classList.remove('hidden');
        logo.classList.remove('not-started');
        logo_img.src = logo.getAttribute('data-small-logo');
        lyricsWrapper.classList.add('hidden');
        triviaWrapper.classList.remove('hidden');
        triviaWrapper.classList.add('active');
        return;
    }
    else {
        lyricsWrapper.classList.remove('hidden');
        triviaWrapper.classList.add('hidden');
        raffleWinnerWrapper.classList.add('hidden');
    }

    if (raffleWinnerRes.status === 200 && Object.keys(raffleWinner).length > 0 && isSuperuser) {
        if (!activeRaffleWinner) {
            setTimeout(() => {
                raffleWinnerTitle.classList.add('active');
                setTimeout(() => {
                    raffleWinnerName.classList.add('active');
                    raffleWinnerDescription.classList.add('active');
                }, 2000)
            }, 500)
        }

        activeRaffleWinner = true;

        lyricsWrapper.classList.add('hidden');
        triviaWrapper.classList.add('hidden');
        raffleWinnerWrapper.classList.remove('hidden');
        raffleWinnerName.innerHTML = `<p>${raffleWinner.full_name}</p>`

    }
    else {
        activeRaffleWinner = false;
        lyricsWrapper.classList.remove('hidden');
        triviaWrapper.classList.add('hidden');
        raffleWinnerWrapper.classList.add('hidden');
        raffleWinnerTitle.classList.remove('active');
        raffleWinnerName.classList.remove('active');
        raffleWinnerDescription.classList.remove('active');
        raffleWinnerName.innerHTML = ``
    }


    if (!eveningStarted) {
        if (!lyricsWrapper.classList.contains('not-started')) {
            document.body.scrollTop = document.documentElement.scrollTop = 0;
        }
        logo.classList.add('not-started');
        logo_img.src = logo.getAttribute('data-big-logo');
        lyricsText.innerHTML = ""

        if (showPasscode) {
            const passcodeRes = await fetch("/passcode");
            const passcode = (await passcodeRes.json()).passcode;
            if (passcode) {
                passcodeWrapper.classList.add('displayed');
                passcodeReveal.innerHTML = passcode;
            } else {
                passcodeWrapper.classList.remove('displayed');
            }
        }
        return;
    }
    else {
        logo.classList.remove('not-started');
        logo_img.src = logo.getAttribute('data-small-logo');
        passcodeWrapper.classList.remove('displayed');
    }

    if (boho) {
        lyricsText.innerHTML = bohoDaysLyrics;
        logo.classList.add('hidden');
        if (!lyricsWrapper.classList.contains('boho')) {
            document.body.scrollTop = document.documentElement.scrollTop = 0;
        }
        lyricsWrapper.classList.add('boho');
        return;
    } else {
        if (lyricsWrapper.classList.contains('boho')) {
            lyricsText.innerHTML = '';
        }
        logo.classList.remove('hidden');
        lyricsWrapper.classList.remove('boho');
    }


    const lyricsRes = await fetch("/current_lyrics");
    const lyricsData = await lyricsRes.json();
    const isGroupSong = lyricsData.is_group_song;

    if (isGroupSong) {
        lyricsWrapper.classList.add('group-song');
    } else {
        lyricsWrapper.classList.remove('group-song');
    }
    if (lyricsData.song_name) {
        var lyrics = lyricsData.lyrics;
        const resDrinking = await fetch("/drinking_words");
        const drinkingWords = (await resDrinking.json()).drinking_words;
        let regex;

        if (drinkingWords.includes('*')) {
            regex = new RegExp(`\\b([\\w']+)\\b`, 'gi');
            lyrics = lyrics.replace(regex, `<span class="drink-highlight">$1</span>`);
        }
        else {
            drinkingWords.forEach(word => {
                regex = new RegExp(`\\b(${word}s?)\\b`, 'gi');
                lyrics = lyrics.replace(regex, `<span class="drink-highlight">$1</span>`);
            })
        }
        
        lyricsText.innerHTML = `${isGroupSong ? "<div id='group-song-title'>GROUP SONG!!!</div>" : ""}
        <h2>${lyricsData.song_name}</h2>
            <h3>${lyricsData.artist_name}</h3><br>
        <pre dir="auto">${lyrics}</pre>
    `
        if (lyricsData.song_name != currentSong) {
            currentSong = lyricsData.song_name;
            window.scrollTo(0, 0);
        }
    }
}
