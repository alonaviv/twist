(function () {
    const config = window.peoplesChoiceConfig || {};
    const API_URL = config.apiUrl;
    const CREATE_SONG_URL = config.createSongUrl;
    const CHOOSE_SONG_URL = config.chooseSongUrl;
    const EVENT_SKU = config.eventSku || 'default-event-sku';
    const POLL_INTERVAL = Number(config.pollIntervalMs) || 6000;
    const STORAGE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 1 week
    const STORAGE_PREFIX = EVENT_SKU ? `pc-${EVENT_SKU}-` : 'pc-default-';
    const MODE_STORAGE_KEY = `${STORAGE_PREFIX}user-mode`;
    const SINGER_NAME_STORAGE_KEY = `${STORAGE_PREFIX}singer-name`;
    const VOTE_STORAGE_KEY = `${STORAGE_PREFIX}vote-memory`;
    const CHOSEN_SONG_STORAGE_KEY = `${STORAGE_PREFIX}chosen-song`;

    if (!API_URL) {
        console.warn('Audience suggestions: API url missing');
        return;
    }

    const topListEl = document.getElementById('pc-top-list');
    const restListEl = document.getElementById('pc-rest-list');
    const lastUpdatedEl = document.getElementById('pc-last-updated');
    const eventDateTextEl = document.getElementById('pc-event-date-text');
    const refreshButton = document.getElementById('pc-refresh-button');
    const modeSelectionModal = document.getElementById('pc-mode-selection-modal');
    const layout = document.querySelector('.pc-layout');
    const modeStatusWrapper = document.getElementById('pc-mode-status');
    const modeStatusText = document.getElementById('pc-current-mode');
    const changeModeBtn = document.getElementById('pc-change-mode-btn');

    if (!topListEl || !restListEl) {
        return;
    }

    const getPersistentItem = (key) => {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') {
                localStorage.removeItem(key);
                return null;
            }
            if (Date.now() - parsed.timestamp > STORAGE_TTL_MS) {
                localStorage.removeItem(key);
                return null;
            }
            return parsed.value;
        } catch (error) {
            console.warn('Failed to parse storage for', key, error);
            localStorage.removeItem(key);
            return null;
        }
    };

    const setPersistentItem = (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify({
                value,
                timestamp: Date.now(),
            }));
        } catch (error) {
            console.warn('Unable to persist data for', key, error);
        }
    };

    const removePersistentItem = (key) => {
        localStorage.removeItem(key);
    };

    // Mode management
    let currentMode = getPersistentItem(MODE_STORAGE_KEY) || null;
    if (currentMode) setPersistentItem(MODE_STORAGE_KEY, currentMode);
    let singerName = getPersistentItem(SINGER_NAME_STORAGE_KEY) || null;
    if (singerName) setPersistentItem(SINGER_NAME_STORAGE_KEY, singerName);

    const voteMemory = new Map();
    const storedVotes = getPersistentItem(VOTE_STORAGE_KEY);
    if (Array.isArray(storedVotes)) {
        storedVotes.forEach((id) => voteMemory.set(Number(id), true));
        setPersistentItem(VOTE_STORAGE_KEY, storedVotes);
    }

    const persistVotes = () => {
        const votedIds = Array.from(voteMemory.entries())
            .filter(([, value]) => value === true)
            .map(([id]) => id);
        setPersistentItem(VOTE_STORAGE_KEY, votedIds);
    };
    let claimedSongId = null; // Track the single claimed song (only one allowed)
    const storedClaimed = getPersistentItem(CHOSEN_SONG_STORAGE_KEY);
    if (storedClaimed && storedClaimed.singer === singerName) {
        claimedSongId = Number(storedClaimed.id);
    }

    const persistClaimedSong = () => {
        if (claimedSongId && singerName) {
            setPersistentItem(CHOSEN_SONG_STORAGE_KEY, {
                id: claimedSongId,
                singer: singerName,
            });
        } else {
            removePersistentItem(CHOSEN_SONG_STORAGE_KEY);
        }
    };
    let pollTimer = null;

    const heartSvg = `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 20.5s-7-4.55-7-10a4.2 4.2 0 0 1 7-3 4.2 4.2 0 0 1 7 3c0 5.45-7 10-7 10z"></path>
        </svg>
    `;

    const buildCard = (song, rank, isHeroSection) => {
        const songId = Number(song.id);
        const voted = voteMemory.get(songId) === true;
        // Check if this song is chosen by the current singer
        const isChosen = song.chosen === true && song.chosen_by;
        const rawChosenBy = (song.chosen_by || '').trim();
        const isChosenByMe = isChosen && rawChosenBy === singerName;
        const isChosenBySomeoneElse = isChosen && rawChosenBy && rawChosenBy !== singerName;
        const isClaimed = isChosenByMe || claimedSongId === songId;
        const isSingerMode = currentMode === 'singer';
        const isUuidLike =
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(rawChosenBy) ||
            rawChosenBy.startsWith('singer-');
        const displayChosenName = rawChosenBy && !isUuidLike ? rawChosenBy : null;
        const chosenRibbon = isChosen && displayChosenName
            ? `<div class="pc-card-ribbon">Chosen by ${displayChosenName}</div>`
            : '';

        let footerButton = '';
        if (isSingerMode) {
            footerButton = `
                <button
                    class="pc-sing-btn ${isChosenByMe ? 'is-chosen-by-me' : ''} ${isClaimed && !isChosenByMe ? 'is-claimed' : ''} ${isChosenBySomeoneElse ? 'is-disabled' : ''}"
                    type="button"
                    data-song-id="${songId}"
                    ${isChosenBySomeoneElse ? 'disabled' : ''}
                >
                    ${isChosenByMe ? "Chosen by you!" : (isChosenBySomeoneElse ? "Already chosen" : "I'll sing this!")}
                </button>
            `;
        } else {
            footerButton = `
                <button class="pc-vote-btn ${voted ? 'is-voted' : ''}" type="button" data-song-id="${songId}" aria-pressed="${voted}">
                    <span class="pc-heart">${heartSvg}</span>
                    <span class="pc-vote-label">${voted ? 'Voted' : 'Vote'}</span>
                </button>
            `;
        }

        const cardClass = isSingerMode && isClaimed ? 'pc-card--claimed' : '';

        return `
            <article class="pc-card ${isHeroSection ? 'pc-card--hero' : ''} ${cardClass}" data-song-id="${songId}">
                ${chosenRibbon}
                <div class="pc-card-rank">${rank}</div>
                <div class="pc-card-body">
                    <h3 class="pc-card-title">${song.title}</h3>
                    <p class="pc-card-show">${song.show}</p>
                    <div class="pc-card-footer">
                        ${footerButton}
                    </div>
                </div>
            </article>
        `;
    };

    const attachVoteHandlers = (container) => {
        if (currentMode !== 'audience') {
            return;
        }

        container.querySelectorAll('.pc-vote-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const songId = Number(btn.dataset.songId);
                const isVoted = btn.classList.contains('is-voted');
                const newState = !isVoted;

                // Toggle UI
                btn.classList.toggle('is-voted', newState);
                btn.setAttribute('aria-pressed', String(newState));
                btn.querySelector('.pc-vote-label').textContent = newState ? 'Voted' : 'Vote';
                voteMemory.set(songId, newState);
                persistVotes();

                // Send request
                try {
                    const voteUrl = `/peoples-choice/vote_song_suggestion/${songId}/`;
                    await fetch(voteUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify({
                            action: newState ? 'increment' : 'decrement'
                        }),
                    });
                    fetchSongs();
                } catch (error) {
                    // Revert on error
                    btn.classList.toggle('is-voted', isVoted);
                    btn.setAttribute('aria-pressed', String(isVoted));
                    btn.querySelector('.pc-vote-label').textContent = isVoted ? 'Voted' : 'Vote';
                    voteMemory.set(songId, isVoted);
                    persistVotes();
                }
            });
        });
    };

    const unclaimPreviousSong = () => {
        if (claimedSongId === null) {
            return;
        }

        // Check both containers for the previous song
        const allContainers = [topListEl, restListEl];
        for (const container of allContainers) {
            if (!container) continue;
            const prevCard = container.querySelector(`[data-song-id="${claimedSongId}"]`);
            if (prevCard) {
                const prevBtn = prevCard.querySelector('.pc-sing-btn');
                if (prevBtn) {
                    prevBtn.classList.remove('is-claimed');
                }
                prevCard.classList.remove('pc-card--claimed');
                break;
            }
        }
    };

    const updateModeStatus = () => {
        if (!modeStatusWrapper || !modeStatusText) {
            return;
        }

        if (!currentMode) {
            modeStatusWrapper.style.display = 'none';
            modeStatusWrapper.classList.remove('is-visible');
            return;
        }

        modeStatusWrapper.classList.add('is-visible');
        modeStatusWrapper.style.display = 'inline-flex';
        modeStatusText.textContent = currentMode === 'singer'
            ? 'Viewing as Singer'
            : 'Viewing as Audience';
    };

    const attachSingHandlers = (container) => {
        if (currentMode !== 'singer' || !singerName) {
            return;
        }

        const CHOOSE_SONG_URL = config.chooseSongUrl;
        if (!CHOOSE_SONG_URL) {
            console.warn('Choose song URL not configured');
            return;
        }

        container.querySelectorAll('.pc-sing-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                if (btn.disabled) {
                    return;
                }
                const songId = Number(btn.dataset.songId);
                if (!songId || isNaN(songId)) {
                    console.error('Invalid song ID:', btn.dataset.songId);
                    alert('Invalid song ID. Please refresh the page.');
                    return;
                }
                const isCurrentlyClaimed = claimedSongId === songId;
                const action = isCurrentlyClaimed ? 'unchoose' : 'choose';

                // Optimistically update UI
                if (isCurrentlyClaimed) {
                    claimedSongId = null;
                    btn.classList.remove('is-claimed');
                    const card = btn.closest('.pc-card');
                    if (card) {
                        card.classList.remove('pc-card--claimed');
                    }
                    persistClaimedSong();
                } else {
                    unclaimPreviousSong();
                    claimedSongId = songId;
                    btn.classList.add('is-claimed');
                    const card = btn.closest('.pc-card');
                    if (card) {
                        card.classList.add('pc-card--claimed');
                    }
                    persistClaimedSong();
                }

                // Send request to backend
                try {
                    // Construct URL - the template already removed /0/, so we just append the song ID
                    if (!CHOOSE_SONG_URL) {
                        throw new Error('Choose song URL not configured');
                    }

                    let chooseUrl = CHOOSE_SONG_URL.trim();
                    // Ensure URL ends with / before appending song ID
                    if (!chooseUrl.endsWith('/')) {
                        chooseUrl = chooseUrl + '/';
                    }
                    chooseUrl = chooseUrl + `${songId}/`;

                    const response = await fetch(chooseUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify({
                            action: action,
                            chosen_by: singerName,
                        }),
                    });

                    if (!response.ok) {
                        let errorMessage = 'Failed to update song choice';
                        // Clone response so we can read it multiple times
                        const clonedResponse = response.clone();
                        try {
                            // Try to parse as JSON first
                            const data = await response.json();
                            errorMessage = data.detail || errorMessage;
                        } catch (jsonError) {
                            // If JSON parsing fails, try to read as text from cloned response
                            try {
                                const text = await clonedResponse.text();
                                console.error('Non-JSON error response:', text.substring(0, 200));
                            } catch (textError) {
                                console.error('Error reading error response:', textError);
                            }
                        }
                        throw new Error(errorMessage);
                    }

                    // Parse successful response
                    try {
                        await response.json();
                    } catch (parseError) {
                        // If response is not JSON, that's okay - we'll just refresh
                        console.warn('Response was not JSON, but status was OK');
                    }

                    // Refresh song list to get updated state
                    fetchSongs();
                } catch (error) {
                    console.error('Failed to update song choice', error);
                    // Revert UI on error
                    if (isCurrentlyClaimed) {
                        claimedSongId = songId;
                        btn.classList.add('is-claimed');
                        const card = btn.closest('.pc-card');
                        if (card) {
                            card.classList.add('pc-card--claimed');
                        }
                        persistClaimedSong();
                    } else {
                        unclaimPreviousSong();
                        claimedSongId = null;
                        btn.classList.remove('is-claimed');
                        const card = btn.closest('.pc-card');
                        if (card) {
                            card.classList.remove('pc-card--claimed');
                        }
                        persistClaimedSong();
                    }
                    alert(error.message || 'Failed to update song choice. Please try again.');
                }
            });
        });
    };

    const renderSongs = (payload) => {
        const songs = (payload?.songs || []).slice().sort((a, b) => b.votes - a.votes);

        // If in singer mode, find which song is already chosen by this singer
        if (currentMode === 'singer' && singerName) {
            const chosenSong = songs.find(
                (song) => song.chosen === true && song.chosen_by === singerName
            );
            claimedSongId = chosenSong ? Number(chosenSong.id) : null;
            if (claimedSongId) {
                persistClaimedSong();
            }
        } else {
            const storedChoice = getPersistentItem(CHOSEN_SONG_STORAGE_KEY);
            if (storedChoice && singerName && storedChoice.singer === singerName) {
                claimedSongId = Number(storedChoice.id);
            } else {
                claimedSongId = null;
            }
        }

        const topSongs = songs.slice(0, 10);
        const restSongs = songs.slice(10);

        const eventDate = payload?.event_date || 'Upcoming Date';
        eventDateTextEl.textContent = eventDate;
        document.title = `Broadway With a Twist - ${eventDate}`;

        if (!songs.length) {
            const emptyMarkup = '<div class="pc-empty-state">Be the first to suggest a song!</div>';
            topListEl.innerHTML = emptyMarkup;
            restListEl.innerHTML = emptyMarkup;
            return;
        }

        topListEl.innerHTML = topSongs
            .map((song, index) => buildCard(song, index + 1, true))
            .join('');

        restListEl.innerHTML = restSongs.length
            ? restSongs.map((song, index) => buildCard(song, index + 11, false)).join('')
            : '<div class="pc-empty-state">Everyone\'s already in the Top 10!</div>';

        attachVoteHandlers(topListEl);
        attachVoteHandlers(restListEl);
        attachSingHandlers(topListEl);
        attachSingHandlers(restListEl);
    };

    const setUpdatedTimestamp = () => {
        const now = new Date();
        const formatted = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        lastUpdatedEl.textContent = `Last updated: ${formatted}`;
    };

    const fetchSongs = async () => {
        try {
            refreshButton.disabled = true;
            refreshButton.textContent = 'Refreshing...';
            const response = await fetch(API_URL);
            const payload = await response.json();
            renderSongs(payload);
            setUpdatedTimestamp();
        } catch (error) {
            console.error('Failed to load songs', error);
            lastUpdatedEl.textContent = 'Connection issue — retrying shortly.';
        } finally {
            refreshButton.disabled = false;
            refreshButton.textContent = 'Refresh now';
        }
    };

    const startPolling = () => {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(fetchSongs, POLL_INTERVAL);
    };

    // Mode selection handlers
    const setupModeSelection = () => {
        if (!modeSelectionModal) {
            return;
        }

        const singerNameWrapper = document.getElementById('pc-singer-name-input');
        const singerNameField = document.getElementById('pc-singer-name');
        const singerNameSubmit = document.getElementById('pc-mode-submit-btn');
        const modeButtons = modeSelectionModal.querySelectorAll('.pc-mode-button');

        const hideModal = () => modeSelectionModal.classList.add('is-hidden');
        const showModal = () => {
            modeSelectionModal.classList.remove('is-hidden');
            if (singerNameWrapper) {
                singerNameWrapper.style.display = 'none';
            }
            if (singerNameField) {
                singerNameField.value = singerName || '';
            }
        };

        // Reset invalid singer mode if name missing
        if (currentMode === 'audience' || (currentMode === 'singer' && singerName)) {
            hideModal();
            applyMode(currentMode);
        } else {
            showModal();
        }

        const proceedAsAudience = () => {
            currentMode = 'audience';
            setPersistentItem(MODE_STORAGE_KEY, 'audience');
            singerName = null;
            removePersistentItem(SINGER_NAME_STORAGE_KEY);
            hideModal();
            applyMode('audience');
            fetchSongs();
            startPolling();
        };

        const proceedAsSinger = () => {
            if (!singerNameField) {
                return;
            }
            const name = singerNameField.value.trim();
            if (!name) {
                alert('Please enter your name to continue as a singer.');
                singerNameField.focus();
                return;
            }
            singerName = name;
            setPersistentItem(SINGER_NAME_STORAGE_KEY, singerName);
            currentMode = 'singer';
            setPersistentItem(MODE_STORAGE_KEY, 'singer');
            hideModal();
            applyMode('singer');
            fetchSongs();
            startPolling();
        };

        modeButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const selectedMode = btn.value;
                if (selectedMode === 'audience') {
                    proceedAsAudience();
                } else if (singerNameWrapper) {
                    singerNameWrapper.style.display = 'flex';
                    if (singerNameField) {
                        singerNameField.value = singerName || '';
                        singerNameField.focus();
                    }
                }
            });
        });

        if (singerNameSubmit) {
            singerNameSubmit.addEventListener('click', proceedAsSinger);
        }

        if (singerNameField) {
            singerNameField.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    proceedAsSinger();
                }
            });
        }

        if (changeModeBtn) {
            changeModeBtn.addEventListener('click', () => {
                showModal();
                currentMode = null;
                singerName = null;
                removePersistentItem(MODE_STORAGE_KEY);
                removePersistentItem(SINGER_NAME_STORAGE_KEY);
                updateModeStatus();
            });
        }

        updateModeStatus();
    };

    const applyMode = (mode) => {
        if (!layout) {
            return;
        }

        const floatingBtn = document.getElementById('pc-floating-add-btn');
        const singerHint = document.getElementById('pc-singer-hint');
        const heroDescription = document.getElementById('pc-hero-description');
        const peopleChoiceNotice = document.getElementById('pc-people-choice-notice');

        if (mode === 'singer') {
            layout.classList.add('is-singer-mode');
            if (floatingBtn) {
                floatingBtn.style.setProperty('display', 'none', 'important');
                floatingBtn.style.setProperty('visibility', 'hidden', 'important');
                floatingBtn.style.setProperty('opacity', '0', 'important');
            }
            if (singerHint) {
                singerHint.style.display = 'block';
            }
            if (peopleChoiceNotice) {
                peopleChoiceNotice.style.display = 'none';
            }
            if (heroDescription) {
                heroDescription.textContent = "Our audience would love to hear you sing these songs!";
            }
        } else {
            layout.classList.remove('is-singer-mode');
            if (floatingBtn) {
                floatingBtn.style.removeProperty('display');
                floatingBtn.style.removeProperty('visibility');
                floatingBtn.style.removeProperty('opacity');
            }
            if (singerHint) {
                singerHint.style.display = 'none';
            }
            if (peopleChoiceNotice) {
                peopleChoiceNotice.style.display = 'block';
            }
            if (heroDescription) {
                heroDescription.textContent = "What songs would you like to hear? Let our singers know what the people want!";
            }
        }

        updateModeStatus();
    };

    refreshButton.addEventListener('click', fetchSongs);

    // Initialize mode selection first
    setupModeSelection();

    // Always populate song lists so content is visible behind the modal
    fetchSongs();

    // Only start polling once a mode has been selected
    if (currentMode) {
        startPolling();
    }

    window.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            clearInterval(pollTimer);
        } else {
            fetchSongs();
            startPolling();
        }
    });

    // Modal toggle functionality
    const modal = document.getElementById('pc-add-song-modal');
    const floatingBtn = document.getElementById('pc-floating-add-btn');
    const headerBtn = document.getElementById('pc-header-suggest-btn');
    const modalBackdrop = document.getElementById('pc-modal-backdrop');
    const modalClose = document.getElementById('pc-modal-close');

    const openModal = () => {
        if (modal) {
            modal.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        }
    };

    const closeModal = () => {
        if (modal) {
            modal.classList.remove('is-open');
            document.body.style.overflow = '';
            // Clear form message when closing
            const formMessage = document.getElementById('pc-form-message');
            if (formMessage) {
                formMessage.textContent = '';
                formMessage.className = 'pc-form-message';
            }
        }
    };

    if (floatingBtn) {
        floatingBtn.addEventListener('click', openModal);
    }

    if (headerBtn) {
        headerBtn.addEventListener('click', openModal);
    }

    if (modalBackdrop) {
        modalBackdrop.addEventListener('click', closeModal);
    }

    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.classList.contains('is-open')) {
            closeModal();
        }
    });

    // Add song form handling
    const addSongForm = document.getElementById('pc-add-song-form');
    const formMessage = document.getElementById('pc-form-message');
    const submitBtn = document.getElementById('pc-submit-song-btn');

    if (addSongForm && CREATE_SONG_URL) {
        addSongForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(addSongForm);
            const songData = {
                song_name: formData.get('song_name'),
                musical: formData.get('musical'),
                event_sku: EVENT_SKU,
            };

            // Clear previous messages
            formMessage.textContent = '';
            formMessage.className = 'pc-form-message';

            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.textContent = 'Adding...';

            try {
                const response = await fetch(CREATE_SONG_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(songData),
                });

                const data = await response.json();

                if (response.ok) {
                    addSongForm.reset();
                    // Refresh the song list
                    fetchSongs();
                    // Close modal immediately
                    closeModal();
                } else {
                    const errorMsg = data.detail || data.error || 'Failed to add song';
                    formMessage.textContent = errorMsg;
                    formMessage.className = 'pc-form-message pc-form-message--error';
                }
            } catch (error) {
                console.error('Failed to add song', error);
                formMessage.textContent = 'Connection error. Please try again.';
                formMessage.className = 'pc-form-message pc-form-message--error';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Add Song';
            }
        });
    }

    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
})();

