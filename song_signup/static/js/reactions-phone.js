// The full-screen reactions window on audience phones while a people's choice song is live.
// Taps and text are collected locally and sent together every second.
const STATE_INTERVAL = 4000;
const SEND_INTERVAL = 1000;

const wrapper = document.getElementById("reactions-wrapper");
const closeButton = document.getElementById("reactions-close");
const textForm = document.getElementById("reactions-text-form");
const textInput = document.getElementById("reactions-text");
const textCount = document.getElementById("reactions-text-count");
const sentNote = document.getElementById("reactions-sent");
// From the form's own token, so sending works on any page whether or not the CSRF cookie was set elsewhere
const csrftoken = textForm.querySelector("[name=csrfmiddlewaretoken]").value;

let open = false;
let dismissed = false;  // ✕ pressed; lasts until reactions close or the page changes
let emojiCounts = {};
let pendingTexts = [];

document.querySelectorAll(".reactions-emoji").forEach(button => {
    button.addEventListener("click", () => {
        const emoji = button.dataset.emoji;
        emojiCounts[emoji] = (emojiCounts[emoji] || 0) + 1;
        popEmoji(button, emoji);
    });
});

closeButton.addEventListener("click", () => {
    dismissed = true;
    render();
});

function updateTextCount() {
    textCount.textContent = `${textInput.value.length}/${textInput.maxLength}`;
}

textInput.addEventListener("input", updateTextCount);

textForm.addEventListener("submit", e => {
    e.preventDefault();
    const text = textInput.value.trim();
    if (!text) {
        return;
    }
    pendingTexts.push(text);
    textInput.value = "";
    updateTextCount();
    sentNote.classList.remove("shown");
    void sentNote.offsetWidth;  // Restart the animation when sending twice in a row
    sentNote.classList.add("shown");
});

checkState();
sendBatch();

// The next check is scheduled only after this one finishes, so slow requests never pile up
async function checkState() {
    try {
        const res = await fetch("/reactions_state");
        if (res.ok) {
            open = (await res.json()).open;
            if (!open) {
                dismissed = false;
                emojiCounts = {};
                pendingTexts = [];
            }
            render();
        }
    } catch (e) {
        // Keep the current state until the next check
    }
    setTimeout(checkState, STATE_INTERVAL);
}

async function sendBatch() {
    if (open && (Object.keys(emojiCounts).length || pendingTexts.length)) {
        const body = { emojis: emojiCounts, texts: pendingTexts };
        emojiCounts = {};
        pendingTexts = [];
        try {
            await fetch("/send_reaction", {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrftoken,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(body),
            });
        } catch (e) {
            // A lost batch is just a few reactions that don't make it to the screen
        }
    }
    setTimeout(sendBatch, SEND_INTERVAL);
}

// Same entrance and exit as the trivia overlay: unhide, then slide in; slide out, then hide
const SLIDE_DURATION = 1000;
let shown = false;

function render() {
    const show = open && !dismissed;
    if (show === shown) {
        return;
    }
    shown = show;
    if (show) {
        wrapper.classList.remove("hidden");
        setTimeout(() => wrapper.classList.add("active"), 5);
    } else {
        wrapper.classList.remove("active");
        setTimeout(() => {
            if (!shown) {
                wrapper.classList.add("hidden");
            }
        }, SLIDE_DURATION);
    }
}

function popEmoji(button, emoji) {
    const pop = document.createElement("span");
    pop.className = "reactions-pop";
    pop.textContent = emoji;
    pop.style.setProperty("--drift", `${(Math.random() - 0.5) * 60}px`);
    pop.addEventListener("animationend", () => pop.remove());
    button.appendChild(pop);
}
