import { loadWait } from "./utils.js";

// Fetch and populate data in the home page
const currentSinger = document.querySelector(".headliner").firstElementChild;
const currentSong = document.querySelector(".current-song").firstElementChild;
const nextSinger = document.getElementById("next-singer");
const nextSong = document.getElementById("next-song");
const upNextElem = document.querySelector(".up-next");

const dashboardElem = document.getElementById("home-dashboard");
const noSongElem = document.getElementById("no-song");

setInterval(populateSpotlight, 1000);
window.addEventListener("DOMContentLoaded", loadWait(populateSpotlight));


function populateSpotlight() {
    return fetch("/spotlight_data")
        .then((response) => response.json())
        .then((data) => {
            const currentSongData = data.current_song;
            const nextSongData = data.next_song;

            if (currentSongData) {
                currentSinger.innerHTML = currentSongData.singer;
                currentSong.innerHTML = currentSongData.name;
            } else {
                currentSinger.innerHTML = "No One Yet";
                currentSong.innerHTML = "We're waiting the first brave soul!";
            }

            if (nextSongData) {
                upNextElem.style.visibility = "visible";
                nextSinger.innerHTML = nextSongData.singer;
                nextSong.innerHTML = nextSongData.name;
            } else {
                upNextElem.style.visibility = "hidden";
            }
        });
}

function populateDashboard() {
    return fetch("/dashboard_data")
        .then((response) => response.json())
        .then((data) => {
            const userNextSong = data.user_next_song;

            if (userNextSong) {
                dashboardElem.classList.remove("hidden");
                noSongElem.classList.add("hidden");

                document.getElementById(
                    "user-next-song-title"
                ).innerHTML = `Your next song ${userNextSong.wait_amount
                        ? `(coming up in ${userNextSong.wait_amount} songs):`
                        : ":"
                    }`;
                document.getElementById("user-next-song-name").innerHTML =
                    userNextSong.name;
                document.getElementById("user-next-song-lyrics").href = "/lyrics/" + userNextSong.id;
            } else {
                dashboardElem.classList.add("hidden");
                noSongElem.classList.remove("hidden");
            }
        });
}

if (isSinger) {
    setInterval(populateDashboard, 1000);
    window.addEventListener("DOMContentLoaded", loadWait(populateDashboard));

    // Open up dashboard tips
    const tips = document.getElementById("home-tips");
    const dashboardWrapper = document.getElementById("dashboard-wrapper");
    let expandTips = false;
    const originalHeight = window.getComputedStyle(dashboardWrapper).height;

    document.getElementById("expand-tips").addEventListener("click", toggleTips);

    function toggleTips() {
        if (!expandTips) {
            tips.style.transform = "scaleY(1)";
            dashboardWrapper.style.height = "75vh";
            expandTips = true;
        } else {
            tips.style.transform = "scaleY(0)";
            dashboardWrapper.style.height = originalHeight;
            expandTips = false;
        }
    }
}

// If new song added banner is on page - remove it after a few seconds
const songAddedElem = document.getElementById("song-added");
if (songAddedElem) {
    setTimeout(() => (songAddedElem.style.display = "none"), 10000);
}
