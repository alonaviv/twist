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
const raffleParticipantsWrapper = document.querySelector(".raffle-participants");
const raffleSlotAbove = document.querySelector(".raffle-slot-above");
const raffleSlotMiddle = document.querySelector(".raffle-slot-middle");
const raffleSlotBelow = document.querySelector(".raffle-slot-below");
const raffleSubtitle = document.querySelector(".raffle-subtitle");
const fireworksContainer = document.querySelector(".fireworks");
let fireworksInstance = null;
let fireworksRunning = false;
const rafflePhaseNumber = document.getElementById("raffle-phase-number");
let currentSong = '';
let showPasscode = false;
let activeRaffleWinner = false;
let slotAnimationRunning = false;
let slotAnimationCompleted = false;


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
    const raffleParticipantsRes = await fetch("/get_raffle_participants");
    const raffleParticipants = await raffleParticipantsRes.json();

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

    // Only show raffle view if participants list is non-empty (backend only returns list if active winner exists)
    const hasParticipants = raffleParticipantsRes.status === 200 &&
        raffleParticipants &&
        Array.isArray(raffleParticipants.participants) &&
        raffleParticipants.participants.length > 0 &&
        isSuperuser;

    if (hasParticipants) {
        activeRaffleWinner = true;

        lyricsWrapper.classList.add('hidden');
        triviaWrapper.classList.add('hidden');
        raffleWinnerWrapper.classList.remove('hidden');

        // Start slot machine animation (only once, if not already completed)
        if (!slotAnimationRunning && !slotAnimationCompleted) {
            slotAnimationRunning = true;
            runSlotMachineAnimation(raffleParticipants.participants);
        }
        raffleParticipantsWrapper.classList.remove("hidden");
    }
    else {
        activeRaffleWinner = false;
        lyricsWrapper.classList.remove('hidden');
        triviaWrapper.classList.add('hidden');
        raffleWinnerWrapper.classList.add('hidden');
        if (raffleParticipantsWrapper) {
            raffleParticipantsWrapper.classList.add("hidden");
        }
        if (raffleSlotMiddle) {
            raffleSlotMiddle.classList.remove("raffle-slot-middle-winner");
        }
        if (raffleSlotAbove) {
            raffleSlotAbove.classList.remove("raffle-slot-faded");
        }
        if (raffleSlotBelow) {
            raffleSlotBelow.classList.remove("raffle-slot-faded");
        }
        if (raffleSubtitle) {
            raffleSubtitle.classList.remove("raffle-subtitle-faded");
        }
        slotAnimationRunning = false;
        slotAnimationCompleted = false;
        // Stop fireworks when leaving raffle view
        if (fireworksInstance && fireworksRunning) {
            fireworksInstance.stop();
            fireworksRunning = false;
        }
        if (raffleParticipantsWrapper) {
            raffleParticipantsWrapper.classList.add("hidden");
        }
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

function runSlotMachineAnimation(participants) {
    // Backend only returns list if there's a winner, so winner is guaranteed to exist
    if (!participants || participants.length === 0 || !raffleSlotMiddle) {
        slotAnimationRunning = false;
        return;
    }

    // Find the winner index - backend guarantees winner exists with is_winner=true
    const winnerIndex = participants.findIndex(p => p.is_winner);

    let currentIndex = 0;
    let currentDelay = 80; // Start fast

    function animateSlot() {
        if (!slotAnimationRunning) return;

        // Show participants in slots (one above, middle, one below)
        const aboveIndex = currentIndex > 0 ? currentIndex - 1 : null;
        const middleIndex = currentIndex;
        const belowIndex = currentIndex < participants.length - 1 ? currentIndex + 1 : null;

        // Update slots
        if (raffleSlotAbove) {
            raffleSlotAbove.textContent = aboveIndex !== null ? participants[aboveIndex].full_name : "";
        }
        if (raffleSlotMiddle) {
            raffleSlotMiddle.textContent = participants[middleIndex].full_name;
        }
        if (raffleSlotBelow) {
            raffleSlotBelow.textContent = belowIndex !== null ? participants[belowIndex].full_name : "";
        }

        // Check if we've reached the winner in the middle slot
        if (middleIndex === winnerIndex) {
            // Winner is in the middle - stop here and mark as completed
            if (raffleSlotMiddle) {
                raffleSlotMiddle.classList.add("raffle-slot-middle-winner");
            }
            if (raffleSlotAbove) {
                raffleSlotAbove.classList.add("raffle-slot-faded");
            }
            if (raffleSlotBelow) {
                raffleSlotBelow.classList.add("raffle-slot-faded");
            }
            if (raffleSubtitle) {
                raffleSubtitle.classList.add("raffle-subtitle-faded");
            }
            slotAnimationRunning = false;
            slotAnimationCompleted = true;
            startFireworksOnce();
            return;
        }

        // Three-phase animation based on progress towards the winner
        const progressToWinner = currentIndex / winnerIndex;

        let currentPhase = 1;
        if (progressToWinner < 0.5) {
            currentPhase = 1;
            currentDelay = Math.min(currentDelay * 1.02, 150);
        } else if (progressToWinner < 0.9) {
            currentPhase = 2;
            currentDelay = Math.min(currentDelay * 1.08, 900);
        } else {
            currentPhase = 3;
            currentDelay = Math.min(currentDelay * 1.08, 300);
        }

        if (rafflePhaseNumber) {
            rafflePhaseNumber.textContent = currentPhase;
        }

        // Move to next index - scroll through list until we reach the winner
        currentIndex++;
        setTimeout(animateSlot, currentDelay);
    }

    // Start animation
    animateSlot();
}

function startFireworksOnce() {
    if (!fireworksContainer || typeof Fireworks === "undefined" || !Fireworks || !Fireworks.default) {
        return;
    }

    if (!fireworksInstance) {
        // Make fireworks bigger and more intense
        fireworksInstance = new Fireworks.default(fireworksContainer, {
            autoresize: true,
            opacity: 0.5,
            acceleration: 1.05,
            friction: 0.97,
            gravity: 1.5,
            particles: 260,
            traceLength: 3,
            traceSpeed: 8,
            explosion: 8,
            intensity: 55,
            flickering: 45,
            lineStyle: 'round',
        });
    }

    if (!fireworksRunning) {
        fireworksInstance.start();
        fireworksRunning = true;
    }
}
