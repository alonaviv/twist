import {loadWait} from "./utils.js";

const suggestionListWrapper = document.getElementById("suggestion-list-wrapper");
const suggestionContainer = suggestionListWrapper.querySelector('.container');

window.addEventListener("DOMContentLoaded", loadWait(populateSuggestionList));
setInterval(populateSuggestionList, 10000);

function get_song_lis(data) {
    const lis = data.map((song) => {
        const li = document.createElement("li");

        if (song.is_used) {
            li.classList.add("claimed");
        }
        
        li.innerHTML = `
        <a href="/add_song?song_name=${song.song_name}&musical=${song.musical}&suggested_by=${song.suggested_by.id}" class="song-wrapper">
                <div class="song-name">
                    <i class="fa-solid fa-star"></i>
                    <p>${song.song_name} ${song.is_used ? " - Claimed" : ""}</p>
                </div>
        </a>
        <div class="musical-name">
            <p> From ${song.musical}</p>
        </div>
        <div class="suggested-by">
            <p>Suggested by ${song.suggested_by.first_name} ${song.suggested_by.last_name}</p>
        </div>`;
        return li;
    });
    return lis;
}


async function populateSuggestionList() {
    const response = await fetch("/get_suggested_songs");
    const data = await response.json();
    if (data.length === 0) {
            suggestionContainer.innerHTML = `
                <h1>Song Suggestions</h1>
                    <p id="explanation-text">No suggestions yet :(<br><br>
                    What would you love to hear tonight? <br> Give someone an idea for great song to sing!</p>
                    <div class="center">
                        <a href="/suggest_group_song" class="btn btn-secondary-inverted" id="suggest-again-btn">Suggest a Song</a> 
                    </div>
            `
    } else {
        suggestionContainer.innerHTML = `
            <h1>Song Suggestions</h1>
                <p id="explanation-text">Wondering what to sing tonight? <br> Select an audience suggestion with a click</p>
                <ul id="suggestion-list"></ul>
                <div class="center">
                    <a href="/suggest_group_song" class="btn btn-secondary-inverted" id="suggest-again-btn">Make Another Suggestion</a> 
                </div>
        `
        document.getElementById('suggestion-list').replaceChildren(...get_song_lis(data));
    }
}
