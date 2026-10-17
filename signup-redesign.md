# Signup page

The singer signup page (`/add_song`) puts the People's Choice list up front. Singers choose a song at leisure before
signup opens; the SIGNUP tap after it opens sends the song, and the moment the song is created sets their place in line.
The same page serves the rest of the evening for latecomers and extra songs.

## The page

- **Top.** The green add-song look and heading. Under the heading, a song slot sticks under the navbar while the
  list scrolls beneath it: before a song is chosen it is the line "Sing anything Broadway or Disney: enter your own song
  or pick one below.", whose link opens the form; once the form has a song it is a "Your song" card with an Edit button.
- **The form** (song, musical, notes, partners) opens in a popup, opened from either. It is one form holding one song.
- **People's Choice** is embedded below with the suggestions site's look, built from its `.pc-*` card classes. The
  heading row is the sash (`img/coronation-sash.png`; the "Miss Congeniality" `peoples_choice/img/sash.png` is
  admin-only), "PEOPLE'S CHOICE" and the silver crown (`img/silver-crown.png`), over "Sash + crown + live reactions
  😍🔥👏" and an "I chose a song online" button. The list shows only while `PEOPLES_CHOICE_EVENT_DATE` and
  `PEOPLES_CHOICE_EVENT_SKU` are set.
- **The bar.** A fixed bar above the footer holds the SIGNUP button and a line of text under it. The whole bar is the
  tap target, so getting in first is about timing, not aim. One tap sends one request: the button disables until the
  answer arrives.

## Opening signup

The page starts in the state the server rendered (the `CAN_SIGNUP` flag) and polls `/signup_disabled` every 500 ms.

- **Closed:** a tilted "Signup isn't open yet!" stamp sits over the top edge of the button. The button is grey with no
  song, dimmed red once a song is chosen. The line under it reads "Get your song ready before signup opens", then
  "You're all set. Tap here as soon as we open!".
- **Opening:** the stamp pops away in 0.25 s, faster than anyone can react, and the button is red and tappable at that
  same instant. What people see is exactly what works: nothing to know, no artificial wait. When signup opens while
  the page is showing, the line under the button reads "We're open! Tap here!" so the bar keeps its size.
- **Open on load:** the template renders the stamp already lifted, so there is no stamp, no animation, and no line
  under the button.
- **Closing again:** the stamp reappears at once; only the lift animates.
- A successful submit goes to home with `?song=`.

## People's Choice choices

A song is chosen when it has a name on it (`chosen_by`); `SongSuggestion.chosen_in_app` says it was chosen on this
page rather than on the suggestions site.

- The list loads from `list_song_suggestions/<PEOPLES_CHOICE_EVENT_SKU>` and reloads every 5 seconds. Open songs come
  first, in vote order (counts not shown) and numbered: the top 10, then "Show all", each with "I'll sing this!". The
  song the singer chose on this page keeps its place and number, on the site's highlighted card with a disabled
  "Chosen by you!" button. Songs anyone else chose sit at the bottom with the site's "Chosen by …" ribbon and a disabled
  "Already chosen" button.
- "I'll sing this!" fills the form and chooses the song under the singer's full name with `in_app`. The choose endpoint
  unchooses any other song in the event chosen under the same name, so choosing another song moves the choice.
- "I chose a song online" lists the songs chosen on the suggestions site (`chosen_in_app` false). Its "That's mine"
  makes the same choose call, rewriting the choice under the singer's name; the website name is not kept.
- When the form holds a different song from the singer's own in-app choice (song and musical, ignoring case and
  spaces), closing the song form popup, however it closes, unchooses that song. An empty form unchooses nothing.
- After a reload the form is empty but the choice survives, so on page load the page refills an empty form from the
  singer's own choice.
- Song edits in My Songs don't touch choices.
- Choices are friction, not protection. Two singers on one song is a regular duplicate, decided by signup time.

## Duplicates

A duplicate is a song tonight with the same name and musical (ignoring case) as another singer's. Only the singer who
chose it second is told; the first singer's song is never marked.

- **Signing up.** `add_song_request` answers "You already signed up with this song tonight" when the song is the
  singer's own. Otherwise it always creates the song, storing the other singer's name in `SongRequest.duplicate_of`
  when there is one, and answers `requested_song`, `song_id`, `duplicate_of` and `partner_warning`. A set
  `duplicate_of` opens the duplicate song popup: "<song> was already chosen by <name>. Your place in line is saved
  either way.", with "I'll pick another song" and "I still want to sing it". Closing it with back or Escape keeps the
  song.
- **Pick another.** The page empties the form, keeps the `song_id`, relabels the button "CHANGE MY SONG" and sends the
  next tap to `update_song`, which overwrites song, musical, notes and partners. A taken song opens the popup again.
- **My Songs.** `update_song` reruns the lookup only when the name or musical changes, setting or clearing
  `duplicate_of`. After any save that returns `duplicate_of`, the same popup opens; "I'll pick another song" reopens
  the edit form. A song with `duplicate_of` shows a "Chosen by <name> as well" badge in the list.
- A singer submitting a song they are already a partner on gets a regular duplicate.

## Partners at signup

The song is created first, which stamps its request time and so the place. Partners are then added one at a time, each
in its own transaction: a partner who already used their once-per-night slot is skipped, the others are added, and the
messages come back as `partner_warning`, shown before going home. Partners are fixed in My Songs.

## Ties in signup time

Request times are stored to the microsecond, and no past event has two equal ones. Every sort in the line ordering ends
with the singer's id, so a tie always resolves the same way: `(last_performance_time or first_request_time, pk)` while
signup is open, `(first_request_time, pk)` and `(last_performance_time, pk)` once it closes.

## Tests

- `song_signup/tests/test_views.py` (`TestAddSongRequestPlaces`): every rejected partner reported while the valid ones
  are added, a duplicate and a rejected partner together, a duplicate getting its own place behind the first, duplicate
  matching ignoring case and spacing, the same song from another musical not matching, a duplicate of a performed
  song, the duplicate naming the singer rather than partners, the singer's own song again creating nothing, a raffle
  winner's duplicate staying standby, and audience being refused.
- `song_signup/tests/test_views.py`: add creates and marks duplicates (the first singer's song stays unmarked), a duet
  partner submitting the duet gets a duplicate, rejected partners become a warning with the song kept; two evening
  scenarios where singer 1 signs up third with a duplicate, or with a rejected partner, two more singers sign up, and
  singer 1 then fixes it from the popup: singer 1 is still third in the lineup; and
  `update_song` marks a song edited into a taken one; and a duplicate signed up through `add_song_request` loses its
  mark when changed to a free song, switches it when changed to another taken song, and keeps it when only the notes
  change.
- `song_signup/tests/test_disney_algo.py` (`TestOrderingTieBreak`): with the clock frozen, songs added in the same
  instant next to ones before and after, performances in the same instant, and a performance in the same instant as
  another singer's first request; then the Disneyland order (and the song positions) is checked, with signup open and
  closed. Before reading the order, singer 1 logs in again, which makes the database return them last, so the tests
  fail without the id breaking ties. Removing the id from the keys fails all three; putting it before the time fails
  two.
- `peoples_choice/tests.py`: the choose endpoint across its cases: choosing an open song from the site or the app, a
  missing name, taking over someone else's choice from either, unchoosing the same name's previous choice (website or
  app, within the event only), re-choosing your own song from the site or the app, unchoosing your own, someone
  else's, or an open song, and an invalid action; every song involved has its full choice state checked.
- `TestRaffle.test_get_raffle_participants_excludes_inactive` fails on the branch before these changes too (4 != 6).

## Manual test on production

After deploy, with the People's Choice date and SKU set, signup closed, and three phones logged in as singers A, B and
C (an Android phone for the back-gesture checks).

**Before opening**
1. The page loads with the stamp over a grey button, the line "Get your song ready before signup opens" under it, and
   the list: numbered open songs first, website choices at the bottom with ribbons. "Show all" expands it.
2. A taps "I'll sing this!": the card stays in place with its number and "Chosen by you!", the "Your song" card
   appears and stays pinned while scrolling, the button turns dimmed red, the line under it reads "You're all set…".
   Within 5 seconds B sees that song at the bottom as "Chosen by A".
3. A picks a different song: the choice moves, and B sees the first song open again.
4. **Found in testing:** A reloads the page: the form comes back with A's song, not empty.
5. A opens Edit and types a song of their own, closing once with Done and once with the Android back gesture: A's choice
   is unchosen both times (B sees it open). Editing only the notes keeps the choice.
6. B taps "I chose a song online", then "That's mine": it becomes B's ("Chosen by you!"), and leaves A's online list.

**Opening**
7. Shani opens signup from the admin while the pages are showing: the stamp pops away, the button turns red at once,
   the line under it reads "We're open! Tap here!", and the bar doesn't change size.
8. A taps the line under the button (not the button): it signs up and lands on home. A double tap creates one song only.
9. A page loaded while signup is already open shows no stamp and no line under the button.

**Duplicates and partners**
10. B submits A's song: the duplicate song popup names A. The Android back gesture closes it and lands on home with
    the song kept.
11. Again with C: "I'll pick another song" empties the form and the button reads "CHANGE MY SONG". Picking another taken
    song opens the popup again; picking a free one lands on home. In My Songs the song is renamed and C's place is
    unchanged.
12. **Found in testing:** after "I'll pick another song", opening and closing the empty form doesn't unchoose
    C's current song.
13. C signs up with a partner who is already someone's partner tonight: the info popup says the place is saved and names
    the partner; OK, and also the back gesture, land on home; the song exists without that partner.
14. After C's partner was left out, a singer with no songs yet tonight signs up (log a phone in as D). Then C comes
    back, opens My Songs and edits the song with another partner: it saves with that partner, and C is still ahead of
    D in the lineup.
15. A partner on A's duet submits the duet themselves: they get the duplicate song popup naming A, and keep a place.

**My Songs**
16. B edits a song to one A has: the duplicate song popup opens; "I still want to sing it" leaves a "Chosen by A as
    well" badge. Editing only the notes asks again. Editing to a free song removes the badge. A's song never shows a
    badge.

**The rest of the evening**
17. A latecomer's first song goes to the back of the line; a second song for A doesn't change A's place.
18. Shani closes signup: the stamp comes back, and the line reorders with singers who haven't sung yet first.
19. The admin lineup shows the duplicates and positions as expected; a raffle winner's song still goes in as standby.
20. A song picked from the list shows the sash in the admin (this depends on the SKU question below).
21. The People's Choice website still works: its cards show each song and musical (it reads `song_name` and
    `musical`), voting, choosing and unchoosing there, and in-app choices show the singer's name.
22. The reactions window and coronation still work during a People's Choice song.
23. With the People's Choice date or SKU cleared, the signup page works without the list.
24. The footer reads 2026.

## Still to do

1. **Stress test of the rush.** Every add recalculates the whole line under a lock on all songs, so adds run one at a
   time: about 5 queries per singer in line (~350-480 ms for 50 singers on the dev box), several seconds for 40
   simultaneous taps. Real 2026 rushes already bring 9-17 first songs within 2 seconds; with nothing to type, most of
   ~40 should land within 1-2 seconds. Waiting adds hold gunicorn sync workers, so the site can stall for those
   seconds (the worker timeout is 30 s). The song is committed before the recalculation, so the place survives even a
   failed one. Run `jmeter/money-time.jmx` (40 singers released together from a rendezvous) on the expanded production
   tier, with the People's Choice list reload (every 5 seconds) added to the singers, and check that every singer's
   song exists in arrival order and that repeated recalculations keep the same order. The priority is that nobody
   loses their place.
2. **People's Choice SKU.** The list and choices use `PEOPLES_CHOICE_EVENT_SKU`; the sash match on songs
   (`is_peoples_choice`) uses `EVENT_SKU`. If they point at different events, a song picked from the list doesn't get
   the sash.
