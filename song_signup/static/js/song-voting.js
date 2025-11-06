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
const emptyState = document.getElementById('empty-state');
const csrftoken = getCookie('csrftoken');

populateVotingList();
setInterval(populateVotingList, 3000);

function votingListItem(suggestion) {
    const li = document.createElement("li");
    if (suggestion.is_used) {
        li.classList.add('used');
    }
    if (suggestion.is_peoples_choice) {
        li.classList.add('peoples-choice-item');
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
            // Refresh the list to get updated People's Choice status
            populateVotingList();
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
        if (emptyState) {
            emptyState.classList.remove('hidden');
        }
        // Still draw the banner even when there are no songs
        drawPeoplesChoiceFrame();
        return;
    }

    if (emptyState) {
        emptyState.classList.add('hidden');
    }

    const lis = data.map(votingListItem);
    votingList.replaceChildren(...lis);

    drawPeoplesChoiceFrame();
}

function drawPeoplesChoiceFrame() {
    if (!votingList) {
        const existing = document.getElementById('peoples-choice-frame');
        if (existing) existing.remove();
        return;
    }

    // Find all People's Choice items (already marked by backend)
    const peoplesChoiceItems = Array.from(votingList.querySelectorAll('.peoples-choice-item'));

    const BANNER_HEIGHT = 60; // must match SCSS banner height
    const top = 0; // start frame at top of list; banner space is via padding

    let height = BANNER_HEIGHT; // default to banner height

    // If there are People's Choice items, calculate height based on the last one
    if (peoplesChoiceItems.length > 0) {
        const lastWrapper = peoplesChoiceItems[peoplesChoiceItems.length - 1]?.querySelector('.song-wrapper');
        if (lastWrapper) {
            const listRect = votingList.getBoundingClientRect();
            const lastRect = lastWrapper.getBoundingClientRect();
            height = Math.max(BANNER_HEIGHT, (lastRect.bottom - listRect.top));
        }
    }

    // Always create/update the frame, even if there are no People's Choice items
    let frame = document.getElementById('peoples-choice-frame');
    if (!frame) {
        frame = document.createElement('div');
        frame.id = 'peoples-choice-frame';
        // Insert at the beginning of the list so it appears at the top
        votingList.insertBefore(frame, votingList.firstChild);
    }
    frame.style.top = `${top}px`;
    frame.style.height = `${height}px`;
}

// Recompute frame on resize
window.addEventListener('resize', drawPeoplesChoiceFrame);

// Modal handling for suggesting a song
const suggestSongBtn = document.getElementById('suggest-song-floating-btn');
const suggestSongModal = document.getElementById('suggest-song-modal');
const closeModalBtn = document.getElementById('close-modal-btn');
const suggestSongForm = document.getElementById('suggest-song-form');

// Open modal when button is clicked
suggestSongBtn.addEventListener('click', () => {
    suggestSongModal.showModal();
});

// Close modal when close button is clicked
closeModalBtn.addEventListener('click', () => {
    suggestSongModal.close();
    suggestSongForm.reset();
});

// Close modal when clicking on backdrop
suggestSongModal.addEventListener('click', (e) => {
    if (e.target === suggestSongModal) {
        suggestSongModal.close();
        suggestSongForm.reset();
    }
});

// Handle form submission
suggestSongForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(suggestSongForm);

    try {
        const response = await fetch('/suggest_song', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken,
            },
            redirect: 'follow',
        });

        // The endpoint redirects on success, so check for redirect or success status
        if (response.ok || response.redirected) {
            // Close modal and reset form
            suggestSongModal.close();
            suggestSongForm.reset();
            // Refresh the voting list to show the new suggestion
            populateVotingList();
        } else {
            // Handle error - could show a message to user
            console.error('Failed to submit suggestion');
        }
    } catch (error) {
        console.error('Error submitting suggestion:', error);
    }
});


