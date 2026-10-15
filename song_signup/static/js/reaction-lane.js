// Floats the audience's people's choice reactions up both sides of the live lyrics screen.
// Runs only on the projector: a superuser on a computer.

const POLL_INTERVAL = 1000;
const TEXT_SPACING = 1000;

const lanes = [document.getElementById("reaction-lane-left"), document.getElementById("reaction-lane-right")];
const triviaWrapper = document.querySelector(".trivia-wrapper.live-lyrics-trivia");
const raffleWrapper = document.querySelector(".raffle-winner-wrapper");
// Emojis and texts each alternate sides, so neither side gets most of them
let nextTextLane = 0;
let nextEmojiLane = 0;

if (isSuperuser && !/Android|iPhone/i.test(navigator.userAgent)) {
    pollReactions();
}

// The next poll is scheduled only after this one finishes, so slow requests never pile up
async function pollReactions() {
    // The lanes sit above the logo, which sits above trivia and the raffle, so step aside while those show
    const covered = !triviaWrapper.classList.contains("hidden") || !raffleWrapper.classList.contains("hidden");
    lanes.forEach(lane => lane.classList.toggle("hidden", covered));
    try {
        const res = await fetch("/reaction_feed");
        if (res.ok) {
            showReactions((await res.json()).reactions);
        }
    } catch (e) {
        // A failed poll skips a round. Reactions the server already handed out in it (and marked as displayed) are
        // lost; any it didn't get to show on the next poll.
    }
    setTimeout(pollReactions, POLL_INTERVAL);
}

function showReactions(reactions) {
    const emojis = reactions.filter(reaction => !reaction.is_text);
    const texts = reactions.filter(reaction => reaction.is_text);
    // Evenly spaced over the gap until the next poll, so they rise as a steady stream with no near-doubles
    emojis.forEach((reaction, i) => {
        setTimeout(() => launchEmoji(reaction.content), i * POLL_INTERVAL / emojis.length);
    });
    texts.forEach((reaction, i) => {
        setTimeout(() => launchText(reaction.content), i * TEXT_SPACING);
    });
}

// Each lane cycles through these start columns (% of the lane), kept so an emoji is never cut off at its edge
const EMOJI_COLUMNS = [15, 35, 55];
const nextEmojiColumn = lanes.map(() => 0);

function launchEmoji(emoji) {
    const laneIndex = nextEmojiLane;
    nextEmojiLane = (nextEmojiLane + 1) % lanes.length;
    const column = EMOJI_COLUMNS[nextEmojiColumn[laneIndex]];
    nextEmojiColumn[laneIndex] = (nextEmojiColumn[laneIndex] + 1) % EMOJI_COLUMNS.length;

    const float = document.createElement("span");
    float.className = "reaction-float";
    float.textContent = emoji;
    float.style.left = `${column + (Math.random() - 0.5) * 6}%`;
    float.style.setProperty("--drift", `${(Math.random() - 0.5) * 4}vw`);
    float.addEventListener("animationend", () => float.remove());
    lanes[laneIndex].appendChild(float);
}

function launchText(text) {
    const bubble = document.createElement("div");
    bubble.className = "reaction-bubble";
    bubble.dir = "auto";
    // textContent, never innerHTML: the text is typed by the audience
    bubble.textContent = text;
    bubble.addEventListener("animationend", () => bubble.remove());
    lanes[nextTextLane].appendChild(bubble);
    nextTextLane = (nextTextLane + 1) % lanes.length;
}
