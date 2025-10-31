import { getCookie } from "./utils.js";

const VOTE_LABEL = 'Vote';
const UNVOTE_LABEL = 'Unvote';

function setVoteButtonState(button, voted) {
    if (voted) {
        button.classList.add('voted');
        button.textContent = UNVOTE_LABEL;
    } else {
        button.classList.remove('voted');
        button.textContent = VOTE_LABEL;
    }
}

const wrapper = document.getElementById("song-voting-wrapper");
const container = wrapper.querySelector(".container");
const votingList = document.getElementById('voting-list');
const topSuggestionCount = parseInt(votingList?.dataset?.topCount || '0', 10) || 0;
const csrftoken = getCookie('csrftoken');

populateVotingList();
setInterval(populateVotingList, 3000);

function votingListItem(suggestion) {
    const li = document.createElement("li");
    if (suggestion.is_used) {
        li.classList.add('used');
    }
    li.dataset.used = suggestion.is_used ? 'true' : 'false';
    const votedClass = suggestion.user_voted ? "voted" : "";
    const buttonText = suggestion.user_voted ? UNVOTE_LABEL : VOTE_LABEL;

    li.innerHTML = `
        <div class="song-wrapper">
            <div class="song-details">
                <div class="song-name">
                    <p>${suggestion.song_name}</p>
                </div>
                <div class="song-musical">From ${suggestion.musical}</div>
            </div>
            <div class="vote-controls">
                <button class="btn vote-btn ${votedClass}" data-id="${suggestion.id}">${buttonText}</button>
            </div>
            ${suggestion.is_used ? `<div class="chosen-banner">Chosen by ${suggestion.chosen_by || 'a singer'}!</div>` : ''}
        </div>
    `;

    const btn = li.querySelector('.vote-btn');
    if (suggestion.is_used && btn) {
        btn.disabled = true;
    }

    btn && btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const id = e.currentTarget.dataset.id;
        const btn = e.currentTarget;

        // Optimistic UI: toggle immediately
        const wasVoted = btn.classList.contains('voted');
        setVoteButtonState(btn, !wasVoted);

        // Confirm with backend; if discrepancy, correct state
        const result = await toggleVote(id);
        if (result && typeof result.voted === 'boolean') {
            setVoteButtonState(btn, result.voted);
        } else {
            // Revert on error
            setVoteButtonState(btn, wasVoted);
        }
    });

    return li;
}

async function toggleVote(suggestionId) {
    const res = await fetch(`/toggle_vote/${suggestionId}`, {
        method: "POST",
        headers: {
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/json",
        },
    });
    try {
        return await res.json();
    } catch (e) {
        return null;
    }
}

async function populateVotingList() {
    const response = await fetch("/get_suggested_songs");
    const data = await response.json();

    if (!data || data.length === 0) {
        votingList.replaceChildren();
        return;
    }

    const lis = data.map(votingListItem);
    votingList.replaceChildren(...lis);

    markPeoplesChoiceItems();
    drawPeoplesChoiceFrame();
}

function drawPeoplesChoiceFrame() {
    const count = topSuggestionCount;
    if (!votingList || count <= 0) {
        const existing = document.getElementById('peoples-choice-frame');
        if (existing) existing.remove();
        return;
    }

    const children = Array.from(votingList.children);
    if (children.length === 0) {
        const existing = document.getElementById('peoples-choice-frame');
        if (existing) existing.remove();
        return;
    }

    // Find the index of the last element needed to cover 'count' non-used items
    let remaining = count;
    let lastIndex = -1;
    for (let i = 0; i < children.length; i++) {
        const li = children[i];
        lastIndex = i;
        if (li.dataset.used !== 'true') {
            remaining -= 1;
            if (remaining === 0) break;
        }
    }

    const firstWrapper = children[0]?.querySelector('.song-wrapper');
    const lastWrapper = children[lastIndex]?.querySelector('.song-wrapper');
    if (!firstWrapper || !lastWrapper) return;

    const listRect = votingList.getBoundingClientRect();
    const firstRect = firstWrapper.getBoundingClientRect();
    const lastRect = lastWrapper.getBoundingClientRect();

    const BANNER_HEIGHT = 60; // must match SCSS banner height
    const top = 0; // start frame at top of list; banner space is via padding
    const height = Math.max(BANNER_HEIGHT, (lastRect.bottom - listRect.top));

    let frame = document.getElementById('peoples-choice-frame');
    if (!frame) {
        frame = document.createElement('div');
        frame.id = 'peoples-choice-frame';
        votingList.appendChild(frame);
    }
    frame.style.top = `${top}px`;
    frame.style.height = `${height}px`;
}

function markPeoplesChoiceItems() {
    const count = topSuggestionCount;
    const children = Array.from(votingList.children);
    let remaining = count;
    children.forEach((li) => {
        li.classList.remove('peoples-choice-item');
    });
    for (const li of children) {
        const isUsed = li.dataset.used === 'true';
        if (!isUsed && remaining > 0) {
            li.classList.add('peoples-choice-item');
            remaining -= 1;
        }
    }
}

// Recompute frame on resize
window.addEventListener('resize', drawPeoplesChoiceFrame);


