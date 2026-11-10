import { getCookie } from "./utils.js";

// The signup page. The People's Choice list is the page; the song form opens in a popup; the bar's SIGNUP button
// sends it. Before signup opens people pick their song at leisure, and the tap after opening sets their place.

const config = window.signupConfig;
const csrftoken = getCookie("csrftoken");
const TOP_COUNT = 10;
const LIST_REFRESH_MS = 5000;
const SIGNUP_POLL_MS = 500;
// The form's contents are kept in sessionStorage under this key, so a refresh, or the phone dropping the page while the
// singer is in another app, doesn't empty it. Every use of it is wrapped in try/catch: a browser that blocks storage
// throws, and the page must still sign up, with a form that just isn't kept.
const FORM_STORAGE_KEY = "signup-form";

const state = {
    open: config.canSignup,
    openedLive: false,       // Signup opened while this page was showing: the go-time moment
    suggestions: [],
    showAll: false,
    sending: false,
    signedUpSong: null,      // {id, name}: the song the last tap created, for "pick another"
    changing: false,         // After "pick another": the button changes signedUpSong instead of adding a song
};

const form = document.getElementById("new-song-form");
const songInput = form.elements["song-name"];
const musicalInput = form.elements["musical"];
const notesInput = form.elements["notes"];
const partnersSelect = form.elements["partners"];
const noSongLine = document.getElementById("no-song-line");
const songCard = document.getElementById("song-card");
const pcList = document.getElementById("pc-list");
const showAllButton = document.getElementById("show-all");
const songFormPopup = document.getElementById("song-form-popup");
const bar = document.getElementById("signup-bar");
const signupButton = document.getElementById("signup-button");
const underButtonLine = document.getElementById("under-button-line");
const stamp = document.getElementById("closed-stamp");
const duplicateSongPopup = document.getElementById("duplicate-song-popup");
const infoPopup = document.getElementById("info-popup");
const websiteChoicesPopup = document.getElementById("website-choices-popup");

// Text from people (song names, names typed on the website) goes into the page as text, never as HTML
const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// Song names compare equal regardless of case and extra spaces, as the server tidies them the same way
const normalizeForComparing = (text) => text.trim().replace(/\s+/g, " ").toLowerCase();
const isSameText = (a, b) => normalizeForComparing(a) === normalizeForComparing(b);
const hasSong = () => songInput.value.trim() && musicalInput.value.trim();
// A list song is the current user's choice when it's the song in their form. This holds even if the server says someone
// else chose it, because the server's choices are only there to show other singers which songs are taken.
const isMyChoice = (s) => isSameText(s.song_name, songInput.value) && isSameText(s.musical, musicalInput.value);
// The suggestion whose button (anything carrying data-suggestion-id) was tapped, or undefined for a tap elsewhere
const tappedSuggestion = (e) => {
    const button = e.target.closest("[data-suggestion-id]");
    return button && state.suggestions.find((s) => s.id === Number(button.dataset.suggestionId));
};
// The song is signed up, so the kept form is dropped: the next visit to the page starts empty
function goHome(songName) {
    try {
        sessionStorage.removeItem(FORM_STORAGE_KEY);
    } catch {}
    window.location.replace(`/home?song=${encodeURIComponent(songName)}`);
}

// ---------- People's Choice list ----------

async function loadSuggestions() {
    if (!config.suggestionsUrl) return;
    const response = await fetch(config.suggestionsUrl);
    state.suggestions = response.ok ? await response.json() : [];  // 404 when the event has no suggestions yet
    renderPeoplesChoice();
}

// One People's Choice card. Its "I'll sing this!" button carries the song's id in data-suggestion-id, for the list's
// click listener (in Events below).
function cardHtml(s, rank) {
    const isMine = isMyChoice(s);
    const button = isMine
        ? `<button class="pc-sing-btn is-disabled" type="button" disabled>Chosen by you!</button>`
        : s.chosen
        ? `<button class="pc-sing-btn is-disabled" type="button" disabled>Already chosen</button>`
        : `<button class="pc-sing-btn" type="button" data-suggestion-id="${s.id}">I'll sing this!</button>`;
    return `
        <article class="pc-card ${isMine ? "pc-card--claimed" : s.chosen ? "pc-card--taken" : ""}">
            ${s.chosen && !isMine ? `<div class="pc-card-ribbon" dir="auto">Chosen by ${escapeHtml(s.chosen_by)}</div>` : ""}
            <div class="pc-card-rank">${rank}</div>
            <div class="pc-card-body">
                <h3 class="pc-card-title">${escapeHtml(s.song_name)}</h3>
                <p class="pc-card-musical">${escapeHtml(s.musical)}</p>
                <div class="pc-card-footer">${button}</div>
            </div>
        </article>`;
}

function renderPeoplesChoice() {
    if (!pcList) return;
    // Open songs (and the current user's choice, in its place) by votes, as the server orders them; songs chosen by
    // anyone else last
    const ordered = [...state.suggestions.filter((s) => !s.chosen || isMyChoice(s)),
                     ...state.suggestions.filter((s) => s.chosen && !isMyChoice(s))];
    const shown = state.showAll ? ordered : ordered.slice(0, TOP_COUNT);
    // Numbers count the songs still open to pick. The current user's choice keeps its number, so choosing an open song
    // doesn't renumber the songs after it; songs chosen by someone else get none (their empty number circle is hidden).
    let rank = 0;
    pcList.innerHTML = shown.map((s) => cardHtml(s, s.chosen && !isMyChoice(s) ? "" : ++rank)).join("");
    showAllButton.textContent = `Show all ${ordered.length} songs`;
    showAllButton.classList.toggle("hidden", state.showAll || ordered.length <= TOP_COUNT);
}

// The app's People's Choice endpoints keep the server's choice in step with the form, so the other singers see the song
// as taken: set chooses the song (and unchooses the user's other app choices), clear unchooses them all. The server
// leaves a song someone else chose alone, and does nothing once the user has a song in the lineup.
async function postToServer(url) {
    await fetch(url, { method: "POST", headers: { "X-CSRFToken": csrftoken } });
}
const setAppPeoplesChoiceSelection = (suggestion) =>
    postToServer(`/peoples-choice/set_app_peoples_choice_selection/${suggestion.id}/`);
const clearAppPeoplesChoiceSelection = () => postToServer("/peoples-choice/clear_app_peoples_choice_selection/");

// "I'll sing this!" and "That's mine" both put the song in the form
async function choose(suggestion) {
    songInput.value = suggestion.song_name;
    musicalInput.value = suggestion.musical;
    saveForm();
    renderSongSlot();
    renderBar();
    await setAppPeoplesChoiceSelection(suggestion);
    loadSuggestions();
}

// Runs whenever the song form popup closes (Done, back gesture or Escape): sets the list song now in the form as the
// user's choice, or clears their choice when the form holds no list song (a song of their own, or none)
async function updateAppPeoplesChoiceSelection() {
    if (!config.suggestionsUrl) return;
    const myPeoplesChoiceSong = state.suggestions.find(isMyChoice);
    await (myPeoplesChoiceSong ? setAppPeoplesChoiceSelection(myPeoplesChoiceSong) : clearAppPeoplesChoiceSelection());
    loadSuggestions();
}

// Each "That's mine" button carries its song's id in data-suggestion-id, for the popup list's click listener (in Events
// below). The song in the user's form isn't listed: it's already theirs.
function openWebsiteChoicesPopup() {
    const chosenOnWebsite = state.suggestions.filter((s) => s.chosen && !s.chosen_in_app && !isMyChoice(s));
    document.getElementById("website-choices-list").innerHTML = chosenOnWebsite.length
        ? chosenOnWebsite.map((s) => `
            <li>
                <div class="website-choice-text"><strong>${escapeHtml(s.song_name)}</strong> · ${escapeHtml(s.musical)}<small dir="auto">Chosen by ${escapeHtml(s.chosen_by)}</small></div>
                <button type="button" data-suggestion-id="${s.id}">That's mine</button>
            </li>`).join("")
        : `<li>No songs were chosen online.</li>`;
    websiteChoicesPopup.showModal();
}

// ---------- The song slot and the song form popup ----------

// Shows the "Your song" card once the form has a song, and the "enter your own song" line until then
function renderSongSlot() {
    noSongLine.classList.toggle("hidden", hasSong());
    songCard.classList.toggle("hidden", !hasSong());
    document.getElementById("song-card-name").textContent = songInput.value;
    document.getElementById("song-card-musical").textContent = musicalInput.value;
}

// Called on every edit of the form, and after code fills or empties it
function saveForm() {
    try {
        sessionStorage.setItem(FORM_STORAGE_KEY, JSON.stringify({
            songName: songInput.value,
            musical: musicalInput.value,
            notes: notesInput.value,
            partners: Array.from(partnersSelect.selectedOptions).map((option) => option.value),
        }));
    } catch {}
}

// Runs on page load. The form comes only from here, never from the server, so a singer back for another song starts
// with an empty form.
function restoreSavedForm() {
    try {
        const saved = JSON.parse(sessionStorage.getItem(FORM_STORAGE_KEY));
        if (!saved) return;
        songInput.value = saved.songName;
        musicalInput.value = saved.musical;
        notesInput.value = saved.notes;
        for (const option of partnersSelect.options) option.selected = saved.partners.includes(option.value);
    } catch {}
}

// ---------- The bar ----------

function renderBar() {
    signupButton.textContent = state.changing ? "CHANGE MY SONG" : "SIGNUP!";
    signupButton.disabled = !state.open || !hasSong() || state.sending;
    // "waiting": signup is closed but the form has a song, so the disabled button shows dimmed red rather than grey,
    // ready to light up when signup opens
    signupButton.classList.toggle("waiting", !state.open && hasSong());

    stamp.classList.toggle("lifted", state.open);

    underButtonLine.textContent = underButtonLineText();
    underButtonLine.classList.toggle("hidden", !underButtonLine.textContent);
}

// The line under the SIGNUP button; the first case that applies wins
function underButtonLineText() {
    if (!state.open && hasSong()) return "You're all set. Tap here as soon as we open!";
    if (!state.open) return "Get your song ready before signup opens";
    if (state.changing) return "Your place is saved, you can change your song";
    if (!hasSong()) return "Choose a song first";
    if (state.openedLive) return "We're open! Tap here!";  // At go time the line stays, so the bar keeps its size
    return "";
}

// Polled every half second, so the page learns signup opened at most half a second late. The button works, and looks
// like it, at that same instant.
function checkSignupOpenState() {
    fetch("/signup_disabled")
        .then((response) => response.json())
        .then((data) => {
            const open = !data.result;
            if (open === state.open) return;
            state.open = open;
            state.openedLive = open;
            renderBar();
        });
}

// ---------- Sending ----------

// A popup with a message and OK, for errors and the partner warning; onOk runs when it closes
let afterInfoPopupCloses = null;
function showInfoPopup(text, onOk = null) {
    document.getElementById("info-popup-text").textContent = text;
    afterInfoPopupCloses = onOk;
    infoPopup.showModal();
}
// onOk runs whenever the popup closes: by OK, or by the back gesture or Escape
infoPopup.addEventListener("close", () => afterInfoPopupCloses?.());
document.getElementById("info-popup-ok").addEventListener("click", () => infoPopup.close());

function showDuplicateSongPopup(songName, duplicateOf, partnerWarning) {
    document.getElementById("duplicate-text").innerHTML =
        `<strong>${escapeHtml(songName)}</strong> was already chosen by <strong>${escapeHtml(duplicateOf)}</strong>.<br>` +
        `Your place in line is saved either way.` + (partnerWarning ? `<br><br>${escapeHtml(partnerWarning)}` : "");
    duplicateSongPopup.showModal();
}

async function addSong() {
    const response = await fetch("/add_song_request", { method: "POST", body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) throw Error(data.error);
    state.signedUpSong = { id: data.song_id, name: data.requested_song };
    return { duplicateOf: data.duplicate_of, partnerWarning: data.partner_warning };
}

// Used only after "I'll pick another song". It sends everything now in the form to the song that addSong created
// when the singer signed up (state.signedUpSong), so it's the same song with the same place in line.
// Partners work differently from signing up. If one already used their once-per-night slot, the server refuses the
// whole change and the info popup shows why; nothing is saved, and the singer can fix the partners and tap again.
// So this never returns a partner warning.
async function changeSong() {
    const response = await fetch("/update_song", {
        method: "PUT",
        headers: { "X-CSRFToken": csrftoken, "Content-Type": "application/json" },
        body: JSON.stringify({
            song_id: state.signedUpSong.id,
            song_name: songInput.value,
            musical: musicalInput.value,
            notes: notesInput.value,
            partners: Array.from(partnersSelect.selectedOptions).map((option) => option.value),
        }),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error);
    state.signedUpSong.name = data.song_name;
    return { duplicateOf: data.duplicate_of, partnerWarning: "" };
}

async function send() {
    if (signupButton.disabled) return;
    state.sending = true;  // One tap, one request
    renderBar();
    try {
        const { duplicateOf, partnerWarning } = state.changing ? await changeSong() : await addSong();
        if (duplicateOf) showDuplicateSongPopup(state.signedUpSong.name, duplicateOf, partnerWarning);
        else if (partnerWarning) showInfoPopup(`Your place is saved. ${partnerWarning}`, () => goHome(state.signedUpSong.name));
        else goHome(state.signedUpSong.name);
    } catch (error) {
        showInfoPopup(error.message);
    } finally {
        state.sending = false;
        renderBar();
    }
}

// ---------- Events ----------

bar.addEventListener("click", send);

document.getElementById("enter-own-song").addEventListener("click", () => songFormPopup.showModal());
document.getElementById("edit-song").addEventListener("click", () => songFormPopup.showModal());
document.getElementById("song-form-done").addEventListener("click", () => songFormPopup.close());
// However the popup closes (Done, back gesture, Escape)
songFormPopup.addEventListener("close", () => {
    renderSongSlot();
    renderBar();
    updateAppPeoplesChoiceSelection();
});
form.addEventListener("submit", (e) => e.preventDefault());
form.addEventListener("input", saveForm);

// The People's Choice list and the website choices popup are redrawn often, so each has one listener on the whole list
// rather than one per button
pcList?.addEventListener("click", (e) => {
    const suggestion = tappedSuggestion(e);
    if (suggestion) choose(suggestion);
});
document.getElementById("website-choices-list").addEventListener("click", (e) => {
    const suggestion = tappedSuggestion(e);
    if (!suggestion) return;
    websiteChoicesPopup.close();
    choose(suggestion);
});
showAllButton?.addEventListener("click", () => {
    state.showAll = true;
    renderPeoplesChoice();
});
document.getElementById("website-choices-open")?.addEventListener("click", openWebsiteChoicesPopup);
document.getElementById("website-choices-close").addEventListener("click", () => websiteChoicesPopup.close());

document.getElementById("sing-anyway").addEventListener("click", () => goHome(state.signedUpSong.name));
document.getElementById("pick-another").addEventListener("click", () => {
    state.changing = true;
    duplicateSongPopup.close();
    form.reset();
    saveForm();
    renderSongSlot();
    renderPeoplesChoice();
    renderBar();
    window.scrollTo({ top: 0 });
});
// The back gesture or Escape on the duplicate song popup counts as "I still want to sing it": the song is already
// saved, so go home. "I'll pick another song" still keeps the singer on the page.
duplicateSongPopup.addEventListener("cancel", () => goHome(state.signedUpSong.name));

restoreSavedForm();
renderSongSlot();
renderBar();
loadSuggestions();
setInterval(loadSuggestions, LIST_REFRESH_MS);
setInterval(checkSignupOpenState, SIGNUP_POLL_MS);
