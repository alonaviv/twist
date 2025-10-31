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
const csrftoken = getCookie('csrftoken');

populateVotingList();
setInterval(populateVotingList, 3000);

function votingListItem(suggestion) {
    const li = document.createElement("li");

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
        </div>
    `;

    li.querySelector('.vote-btn').addEventListener('click', async (e) => {
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
}


