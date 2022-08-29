const newSongForm = document.getElementById("new-song-form");


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