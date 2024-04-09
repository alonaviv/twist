import { getCookie } from "./utils.js";

const csrftoken = getCookie('csrftoken');

async function setLyricsAsDefault(e) {
    e.preventDefault();

    const lyricsId = e.currentTarget.dataset.lyricsId;

    try {
        const response = await fetch(`/default_lyrics`, {
            method: "PUT",
            headers: {
                "X-CSRFToken": csrftoken,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                lyricsId: lyricsId,
            }),
        });

        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }

        const data = await response.json();

        if (data.is_group_song) {
            window.location.replace('/admin/song_signup/groupsongrequest');
        } else {
            window.location.replace('/admin/song_signup/songrequest');
        }
    } catch (error) {
        alert(`Error: ${error}`);
    }
}


document.querySelector('#default_lyrics').addEventListener('click', setLyricsAsDefault);
