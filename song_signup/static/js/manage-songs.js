const newSongForm = document.getElementById("new-song-form");
const songListUl = document.getElementById("song-list");
songListWrapper = document.getElementById("song-list-wrapper");

window.addEventListener("DOMContentLoaded", loadWait(populateSongList));
setInterval(populateSongList, 10000);

// In order to prevent flickering, disable entire body until promise is complete
async function loadWait(promiseCallback) {
  document.body.style.display = "none";
  await promiseCallback();
  document.body.style.display = "block";
}

function populateSongList() {
  return fetch("/get_current_songs")
    .then((response) => response.json())
    .then((data) => {
      if (data.current_songs.length > 0) {
        songListWrapper.classList.remove("hideonpageload");
        songListWrapper.classList.remove("hidden");
      } else {
        songListWrapper.classList.add("hidden");
      }
      const lis = data.current_songs.map((song) => {
        const li = document.createElement("li");
        li.innerHTML = `
                    <div class="song-wrapper">
                        <i class="fa-solid fa-star"></i>
                        <p class="song-name">${song.name}${
          !song.user_song ? ` (Added by ${song.primary_singer})` : ""
        }</p>
                        ${
                          song.user_song
                            ? `<i class="fa-solid fa-xmark delete-song" id=${song.pk}></i>`
                            : ""
                        }
                    </div>`;

        if (song.singers) {
          li.innerHTML += `
                    <div class="other-singers">
                        <p>Together with: ${song.singers}</p>
                    </div>`;
        }
        return li;
      });
      songListUl.replaceChildren(...lis);
      setDeletelinks();
    })
    .catch((error) => console.error(error));
}

newSongForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(newSongForm);

  fetch("/add_song_request", { method: "POST", body: formData })
    .then(async (response) => {
      const data = await response.json();
      if (!response.ok) {
        throw Error(data.error);
      }
        window.location.replace(`/home/${data.requested_song}?group_song=${data.group_song}`);
    })
    .catch((error) => alert(error));
});

function setDeletelinks() {
  const deleteSongLinks = document.querySelectorAll(".delete-song");
  deleteSongLinks.forEach((link) => {
    link.addEventListener("click", async (e) => {
      e.preventDefault();

      const songPK = e.currentTarget.id;
      const response = await fetch(`/get_song/${songPK}`);
      const data = await response.json();

      if (!response.ok) {
        alert(`Error: ${data.error}`);
        return;
      }

      if (confirm(`Are you sure you want to remove ${data.name}?`)) {
        fetch(`/delete_song/${songPK}`)
          .then(() => populateSongList())
          .catch((error) => console.error(error));
      }
    });
  });
}

// Disable signup if server says so
const signupsDisabledBanner = document.getElementById("singups-disabled");

const formFields = newSongForm.querySelectorAll("input, select");
function checkDisableSignup() {
  fetch("/signup_disabled")
    .then((response) => response.json())
    .then((data) => {
      if (data.result) {
        signupsDisabledBanner.style.opacity = "1";
        formFields.forEach((field) => {
          field.disabled = true;
          field.style.background = "#666";
        });
      } else {
        signupsDisabledBanner.style.opacity = "0";
        formFields.forEach((field) => {
          field.disabled = false;
          field.style.background = "#333";
        });
      }
    });
}

setInterval(checkDisableSignup, 10000);
window.addEventListener("DOMContentLoaded", checkDisableSignup);
