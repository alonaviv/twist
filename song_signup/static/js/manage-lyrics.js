import { getCookie } from "./utils.js";

const csrftoken = getCookie('csrftoken');

async function setLyricsAsDefault(e) {
    e.preventDefault();

    const lyricsId = e.currentTarget.dataset.lyricsId;

    await fetch(`/default_lyrics`, {
      method: "PUT",
      headers: {
        // TODO - test without
        "X-CSRFToken": csrftoken,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        lyricsId: lyricsId,
      }),
    })
      .then((_) => {
        location.reload();
      })
      .catch((error) => {
        alert(`Error: ${error}`);
      });
  
}

document.querySelector('#default_lyrics').addEventListener('click', setLyricsAsDefault);