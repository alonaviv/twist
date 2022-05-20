// Open up dashboard tips
const tips = document.getElementById("tips");
const dashboardWrapper = document.getElementById("dashboard-wrapper");
expandTips = false;
const originalHeight = window.getComputedStyle(dashboardWrapper).height;

document.getElementById("expand-tips").addEventListener("click", toggleTips);

function toggleTips() {
  console.log("HEllo");
  if (!expandTips) {
    tips.style.transform = "scaleY(1)";
    dashboardWrapper.style.height = "65vh";
    expandTips = true;
  } else {
    tips.style.transform = "scaleY(0)";
    dashboardWrapper.style.height = originalHeight;
    expandTips = false;
  }
}

// Fetch and populate data in the home page
const currentSinger = document.querySelector(".headliner").firstElementChild;
const currentSong = document.querySelector(".current-song").firstElementChild;
const nextSinger = document.getElementById("next-singer");
const nextSong = document.getElementById("next-song");
const upNextElem = document.querySelector(".up-next");

const dashboardElem = document.getElementById("dashboard");
const noSongElem = document.getElementById("no-song");

setInterval(populateNowSinging, 1000);
window.addEventListener("DOMContentLoaded", populateNowSinging);

function populateNowSinging() {
  fetch("/dashboard_data")
    .then((response) => response.json())
    .then((data) => {
      const currentSongData = data.current_song;
      const nextSongData = data.next_song;
      const userNextSong = data.user_next_song;

      if (currentSongData) {
        currentSinger.innerHTML = currentSongData.singer;
        currentSong.innerHTML = currentSongData.name;
      } else {
        currentSinger.innerHTML = "No One Yet";
        currentSong.innerHTML = "We're waiting for you! Pick a Song!";
      }

      if (nextSongData) {
        upNextElem.style.visibility = "visible";
        nextSinger.innerHTML = nextSongData.singer;
        nextSong.innerHTML = nextSongData.name;
      } else {
        upNextElem.style.visibility = "hidden";
      }

      if (userNextSong) {
        dashboardElem.classList.remove("hidden");
        noSongElem.classList.add("hidden");
        document.getElementById("user-next-song").innerHTML =
          userNextSong.name;
      } else {
        dashboardElem.classList.add("hidden");
        noSongElem.classList.remove("hidden");
      }
    });
}