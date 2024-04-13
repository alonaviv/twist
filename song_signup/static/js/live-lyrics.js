const lyricsText = document.getElementById("lyrics-text");
const lyricsWrapper = document.getElementById("lyrics-wrapper");
const nav = document.querySelector("nav");
const footer = document.querySelector("footer");
const logo = document.querySelector(".fixed-logo");
const passcodeWrapper = document.getElementById("passcode-reveal-wrapper");
const passcodeReveal = document.getElementById("passcode-reveal");
const bohoWrapper = document.getElementById("boho-wrapper")
let currentSong = '';
let showPasscode = false;


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

This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
Bohemia

Don't step on Simone, Renaud, and Philipe
They're still on the living room floor, asleep
Flight was delayed but they got it so cheap
In Amsterdam

The cat jumped off of the fire escape
He's a little shook up but he don't have a scrape
Climb up to the roof, let's make a crepe
You bring the jam

This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
Bohemia

Shower's in the kitchen, there might be some soap
Dishes in the sink, brush your teeth, if you can cope
Toilet's in the closet, you better hope
There's a light bulb in there, bo bo bo

Dino called yesterday, the rent is overdue
ConEd and New York Telephone are mad too
Better screen the calls for a day or two
Or cough up your share

This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
Bohemia

Revolving door roommates
Prick up your ears
Fourteen people in just four years

Ann and Max and Jonathan
And Carolyn and Kerri
David, Tim, no Tim was just a guest
From June to January

Margaret, Lisa, David, Susie
Stephen, Joe, and Sam
And Elsa, the bill collector's dream
Who is still on the lam

Don't forget the neighbors
Michelle and Gay
More like a family
Than a family, hey

The cat's, Lucy, Mr. Beebe
Bouncer, rest his soul
And Finster, who took one look
And stayed for days down in that hole

This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
This is the life, bo-bo, bo bo bo
Bohemia

The garbage trucks
Have turned into limousines
Rat infested diners
Now are fancy restaurants

The gallery opens
You know what that means
There goes the neighborhood
Here come the debutantes

But at 508 the halls
Are still that dingy brown
508, the walls are cracked or falling down
508, we all know the day it changes
Is the day we all should blow this town

The time is flying
And everything is dying
I thought by now
I'd have a dog, a kid, and wife
The ship is sort of sinking
So let's start drinking
Before we start thinking
Is this a life?

Is this a life? Bo-bo, bo bo bo
Is this a life? No no, no no no
Is this a life? Bo-bo, bo bo bo
Bohemia, Bohemia
Bo-he-mi-a, bo, bo, bo, bo
</pre>
`

setInterval(populateLyrics, 1000);

async function populateLyrics() {
    const startedRes = await fetch("/evening_started");
    const eveningStarted = (await startedRes.json()).started;
    const bohoRes = await fetch("/boho_started");
    const boho = (await bohoRes.json()).boho;

    if (!eveningStarted) {
        if (!lyricsWrapper.classList.contains('not-started')) {
            document.body.scrollTop = document.documentElement.scrollTop = 0;
        }
        logo.classList.add('not-started');
        lyricsText.innerHTML = ""

        if (showPasscode) {
            const passcodeRes = await fetch("/passcode");
            const passcode = (await passcodeRes.json()).passcode;
            if (passcode !== '') {
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

        drinkingWords.forEach(word => {
            const regex = new RegExp(`\\b(${word}s?)\\b`, 'gi');
            lyrics = lyrics.replace(regex, `<span class="drink-highlight">$1</span>`);
        })
        lyricsText.innerHTML = `${isGroupSong ? "<div id='group-song-title'>GROUP SONG!!!</div>" : ""}
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
