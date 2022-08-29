function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

const songListUl = document.getElementById("song-list");

window.addEventListener("DOMContentLoaded", loadWait(populateSongList));

// In order to prevent flickering, disable entire body until promise is complete
async function loadWait(promiseCallback) {
  document.body.style.display = "none";
  await promiseCallback();
  document.body.style.display = "block";
}


async function get_current_user() {
    const response = await fetch("/get_current_user");
    const data = await response.json();
    return data;
}


async function populateSongList() {
    let data;
    let current_user;
    try {
        const response = await fetch("get_current_songs");
        data = await response.json();
        current_user = await get_current_user();
    } catch (err) {
        alert(`Error: ${err}`);
    }

    if (data.length === 0) {
        window.location.replace("/add_song");
    }

    const lis = data.map((song) => {
        const li = document.createElement("li");
        li.innerHTML = `
                    <div class="song-wrapper" id=song-${song.id}>
                    ${getSongHtml(song, current_user)}
                    </div>`;
        

        if (song.duet_partner && song.singer.id == current_user.id) {
            li.innerHTML += `
                    <div class="other-singers">
                        <p>Together with: ${song.duet_partner.first_name} ${song.duet_partner.last_name}</p>
                    </div>`;
        }
        setupListeners(li, song.id);
        return li;
    });
    songListUl.replaceChildren(...lis);
}

function setupListeners(parentElement, songId) {
    const deleteBtn = parentElement.querySelector(`#delete-${songId}`);
    if (deleteBtn) {
        deleteBtn.addEventListener("click", deleteSong);
    }
    const renameBtn = parentElement.querySelector(`#rename-${songId}`);
    if (renameBtn) {
        renameBtn.addEventListener("click", displayRenameForm);
    }
}


function getSongHtml(song, current_user) {
    const res = `
            <p class="song-name">${song.song_name}${song.singer.id != current_user.id ? ` (Added by ${song.singer.first_name} ${song.singer.last_name})` : ""}</p>
            ${song.singer.id === current_user.id ? `<i class="fa-solid fa-pen rename-song" data-song-id=${song.id} id="rename-${song.id}"></i>
            <i class="fa-solid fa-trash-can delete-song" data-song-id=${song.id} id="delete-${song.id}"></i>` : ""}`;
    return res;
}


async function deleteSong(e) {
    e.preventDefault();

    const songPK = e.currentTarget.dataset.songId;
    const songWrapper = e.currentTarget.parentElement;
    let data;

    try {
        const response = await fetch(`/get_song/${songPK}`);
        data = await response.json();
    } catch (err) {
        alert(`Error: ${err}`);
        return;
    }

    if (confirm(`Are you sure you want to remove ${data.song_name}?`)) {
        fetch(`/delete_song/${songPK}`)
            .then(() => songWrapper.remove())
            .catch((error) => alert(`Error: ${error}`));
    }
  }

function toggleNewSongBtn() {
    const newSongBtn = document.getElementById("new-song-btn");

    if (document.getElementsByClassName('edit-song-form').length > 0) {
        newSongBtn.classList.add('hidden');

    } else {
        newSongBtn.classList.remove('hidden');
    }
}

async function displayRenameForm(e) {
    e.preventDefault();

    const songPK = e.currentTarget.dataset.songId;
    const songWrapper = e.currentTarget.parentElement;
    let song;

    try {
        const response = await fetch(`/get_song/${songPK}`);
        song = await response.json();
    } catch (err) {
        alert(`Error: ${err}`);
    }

    songWrapper.innerHTML = `
            <form action="" class="edit-song-form" autocomplete="off" id="rename-form-${songPK}" data-song-id=${songPK}>
                <textarea name="edit-song-${songPK}" class="edit-song-name" required>${song.song_name}</textarea>
                <button type="submit" class="approve-rename-btn">
                    <i class="fa-solid fa-check"></i>
                </button>                 
            </form>
        `;
    const textArea = songWrapper.querySelector('.edit-song-name');
    // Set testarea height to match the content height
    textArea.style.height = "1px";
    textArea.style.height = textArea.scrollHeight + "px";
    songWrapper.querySelector(`#rename-form-${songPK}`).addEventListener("submit", sendRename);
    toggleNewSongBtn();
}
  
async function sendRename(e) {
    e.preventDefault();

    const songPK = e.currentTarget.dataset.songId;
    const textInput = e.currentTarget.firstElementChild;
    const songWrapper = e.currentTarget.parentElement;

    const current_user = await get_current_user();
    
    await fetch(`/rename_song`, {
      method: "PUT",
      headers: {
        "X-CSRFToken": csrftoken,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        song_id: songPK,
        song_name: textInput.value,
      }),
    })
        .then(async response => {
            const song = await response.json();

            if (!response.ok) {
                return Promise.reject(song.error);
            }

            songWrapper.innerHTML = getSongHtml(song, current_user);
            setupListeners(songWrapper, song.id);
            toggleNewSongBtn();
        })
        .catch((error) => { alert(`Error: ${error}`) });
    
}

