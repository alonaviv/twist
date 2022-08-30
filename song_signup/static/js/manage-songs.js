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

async function get_current_user() {
    return fetch("/get_user_id").then((response) => response.json())
}

function populateSongList() {
  return fetch("/get_current_songs")
    .then((response) => response.json())
    .then((data) => {
        if (data.current_songs.length === 0) {
            window.location.replace("/add_song");
        }
    
      const lis = data.current_songs.map((song) => {
        const li = document.createElement("li");
        li.innerHTML = `
                    <div class="song-wrapper">
                        <p class="song-name">${song.song_name}${
          !song.user_song ? ` (Added by ${song.primary_singer})` : ""
        }</p>
                        ${
                          song.user_song
                            ? `<i class="fa-solid fa-xmark delete-song" id=${song.pk}></i>`
                            : ""
                        }
                    </div>`;


        if (song.duet_partner && song.user_song) {
          li.innerHTML += `
                    <div class="other-singers">
                        <p>Together with: ${song.duet_partner}</p>
                    </div>`;
        }
        return li;
      });
      songListUl.replaceChildren(...lis);
      setDeletelinks();
    })
    .catch((error) => console.error(error));
}


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

