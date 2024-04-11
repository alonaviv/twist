import { loadWait } from "./utils.js";

// Explanation menu
const overlay = document.getElementById("explanation-overlay");
const label = document.getElementById("explanation-label");
const body = document.getElementById("explanation-body");

let explanationExpanded = false;

function expandExplanation() {
    explanationExpanded = !explanationExpanded;
    overlay.classList.toggle('expanded', explanationExpanded);
    label.classList.toggle('expanded', explanationExpanded);
    body.classList.toggle('expanded', explanationExpanded);
}
overlay.addEventListener("click", expandExplanation);


// Populate lineup data
setInterval(populateLineup, 1000);
window.addEventListener('DOMContentLoaded', loadWait(populateLineup));

function formatSong(song, current_song = false) {
    let content;
    if (!song.song_name) {
        content = `<p class="song-name">No songs chosen yet!</p>`;
    } else {
        content = `<p class="song-name">${song.song_name}</p>
                   <p class="song-musical">${song.musical}</p>
                   <p class="singers"> - ${song.singers}</p>
                   ${current_song ? '<p class="view-lyrics">(Click for lyrics)</p>' : ''}
                   `;
    }

    return `
        <div class="song-wrapper">
            <div class="song-details">
                ${content}
            </div>
        </div>`;
}


const currentlySinging = document.getElementById("currently-singing");
const linupList = document.getElementById("lineup-list");
const nowPerforming = document.getElementById("now-performing");

async function populateLineup() {
    const startedRes = await fetch("/evening_started");
    const eveningStarted = (await startedRes.json()).started

    if (!eveningStarted) {
        currentlySinging.innerHTML = `
        <div class="song-wrapper">
            <div class="song-details">
                <p class="song-name" >Wait for it, wait for it..</p>
                <p class="song-musical">Grab a beer and get comfy, <br> the magic is about to happen :)</p>
            </div>
        </div>
        `
        nowPerforming.classList.add('hidden');
        linupList.classList.add('hidden');
        return;
    } else {
        nowPerforming.classList.remove('hidden');
        linupList.classList.remove('hidden');
    }

    const res = await fetch("/get_lineup");
    const data = await res.json();

    currentlySinging.innerHTML = formatSong(data.current_song, true);

    if (data.next_songs.length !== 0) {
        linupList.innerHTML = '<h2>Up next</h2>';
        const songListElement = document.createElement('ol');
        songListElement.id = 'song-list';

        data.next_songs.forEach((song, index, array) => {
            const li = document.createElement("li");
            li.innerHTML = formatSong(song);
            songListElement.appendChild(li);
            if (index !== array.length - 1) {
                songListElement.appendChild(document.createElement("hr"));
            }

        });

        linupList.appendChild(songListElement);
    } else {
        linupList.innerHTML = '';
    }
}

