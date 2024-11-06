import {getCookie, loadWait} from "./utils.js";

const csrftoken = getCookie('csrftoken');

const songListUl = document.getElementById("song-list");

window.addEventListener("DOMContentLoaded", loadWait(populateSongList));


async function get_current_user() {
    const response = await fetch("/get_current_user");
    const data = await response.json();
    return data;
}


async function populateSongList() {
    let data;
    let current_user;
    try {
        const response = await fetch("/get_current_songs");
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
            <div class="song-details">
                <p class="song-name">${song.song_name}${song.singer.id != current_user.id ? ` (Added by ${song.singer.first_name} ${song.singer.last_name})` : ""}</p>
                <p class="song-musical">${song.musical}</p>
        
        ${(song.partners.length > 0 && song.singer.id == current_user.id) ? `<div class="other-singers">
                    <p>Partners:<br> ${song.partners_str}</p>
                </div>`: ""}
            </div>
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
    let possible_partners

    try {
        let response = await fetch(`/get_song/${songPK}`);
        song = await response.json();

        response = await fetch('/get_possible_partners')
        possible_partners = await response.json()

    } catch (err) {
        alert(`Error: ${err}`);
    }
    let optionsHtml = possible_partners.map(partner => {
        const isSelected = song.partners.some(songPartner => songPartner.id === partner.id);
        return `<option value="${partner.id}" ${isSelected ? 'selected' : ''}>${partner.is_superuser ? `--- ${partner.first_name} ---` : `${partner.first_name} ${partner.last_name}`}</option>`
    }).join('\n');

    songWrapper.innerHTML = `
            <form action="" class="edit-song-form" autocomplete="off" id="rename-form-${songPK}" data-song-id=${songPK}>
                <div class="song-details">
                    <textarea name="edit-song-name-${songPK}" class="edit-song edit-song-name" required>${song.song_name}</textarea>
                    <textarea name="edit-song-musical-${songPK}" class="edit-song edit-song-musical song-musical" required>${song.musical}</textarea>
                    <label for="partners">Partners:</label>
                    <select name="partners" id="edit-partners" multiple>
                        ${optionsHtml}
                    </select>
                </div>
                <button type="submit" class="approve-rename-btn">
                    <i class="fa-solid fa-check"></i>
                </button>                 
            </form>
        `;

    // Set textarea height to match the content height
    const editSong = songWrapper.querySelector('.edit-song-name');
    editSong.style.height = "1px";
    editSong.style.height = editSong.scrollHeight + "px";

    // Set textarea height to match the content height
    const editMusical = songWrapper.querySelector('.edit-song-musical');
    editMusical.style.height = "1px";
    editMusical.style.height = editMusical.scrollHeight + "px";

    songWrapper.querySelector(`#rename-form-${songPK}`).addEventListener("submit", sendRename);
    toggleNewSongBtn();
}
  
async function sendRename(e) {
    e.preventDefault();

    const songPK = e.currentTarget.dataset.songId;
    const songNameInput = e.currentTarget.querySelector('.edit-song-name');
    const songMusicalInput = e.currentTarget.querySelector('.edit-song-musical');
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
          song_name: songNameInput.value,
          musical: songMusicalInput.value
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

