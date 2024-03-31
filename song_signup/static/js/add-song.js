const newSongForm = document.getElementById("new-song-form");
const dialogModal = document.getElementById('duplicate-song-dialog');
const dialogReset = dialogModal.querySelector('.reset');
const dialogContinue = dialogModal.querySelector('.continue');


function getUserModalRes() {
    return new Promise((resolve, reject) => {
        dialogModal.showModal();

        dialogReset.onclick = () => {
            dialogModal.close();
            resolve('reset');
        }
        dialogContinue.onclick = () => {
            dialogModal.close();
            resolve('continue');
        }
        dialogModal.onclose = () => resolve('closed');
    });
}

async function postSongRequest(formData) {
    const response = await fetch("/add_song_request", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) {
        throw Error(data.error);
    }
    return data

}

async function addSong(e) {
    e.preventDefault();
    const formData = new FormData(newSongForm);

    try {
        let data = await postSongRequest(formData);

        if (data.duplicate) {
            dialogModal.showModal();
            const choice = await getUserModalRes();
            if (choice === 'reset' || choice === 'close') {
                newSongForm.reset();
                return;
            }
            else {
                formData.append('approve-duplicate', true);
                data = await postSongRequest(formData);
            }
        }
        window.location.replace(`/home/${data.requested_song}`);
    } catch (error) {
        alert(error);
    }
}

newSongForm.addEventListener('submit', addSong);


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