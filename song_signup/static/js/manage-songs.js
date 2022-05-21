const newSongForm = document.getElementById("new-song-form");

const songListUl = document.getElementById("song-list");

window.addEventListener("DOMContentLoaded", populateSongList);
setInterval(populateSongList, 10000);

function populateSongList() {
  fetch("/get_current_songs")
    .then((response) => response.json())
    .then((data) => {
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
    .catch((error) => alert(`Error connecting to server: ${error}`));
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
      window.location.replace(`/home/${data.requested_song}`);
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

      confirm(`Are you sure you want to remove ${data.name}?`);
      fetch(`/delete_song/${songPK}`)
        .then(() => populateSongList())
        .catch((error) => alert(error));
    });
  });
}
