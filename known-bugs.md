# Known bugs

Bugs in the singer signup page and People's Choice that are known and left unfixed for now, with what they cause
and how to live with them.

## A returning singer's People's Choice song is refilled into the form, then released

A singer who signed up with a song from the People's Choice list and comes back to the signup page to add another
song finds the form already filled with the song they signed up with. This is `restoreMyChoice` in
`song_signup/static/js/add-song.js`, which refills an empty form from the singer's choice; it is meant for a reload
before signing up. As soon as they enter a different song, `unchooseStaleChoice` releases their choice, so the song
they are signed up to sing shows as open in the list and on the People's Choice website.

- Tapping SIGNUP with the refilled song shows "You already signed up with this song tonight". Nothing is lost; the
  singer changes the song and signs up.
- Another singer can choose the released song. When they sign up with it, the duplicate song popup still names the
  first singer.
- The sash and coronation are unaffected: a song counts as People's Choice by matching its name against the
  suggestions (`SongRequest.is_peoples_choice`), not by the chosen mark.

Workaround, if it confuses people: once the opening rush is over, clear `PEOPLES_CHOICE_EVENT_DATE` in the admin's
constance settings. The signup page then shows no list, so nothing is refilled or released; the People's Choice
website shows as inactive. Set the date again before the next reset (`reset_db` refuses to run without it).

Fix: pass the singer's signed-up songs to the page, and have `restoreMyChoice` and `unchooseStaleChoice` skip a
choice the singer already signed up with.

## Choosing a second People's Choice song releases the first

`choose_song_suggestion` in `peoples_choice/views.py` unchooses every earlier choice under the same name in the event.
A singer who signs up with one list song and later chooses another for a second song loses the chosen mark on the
first. The effects are the same as above: the first song shows as open, and the duplicate check still catches anyone
who signs up with it.

## A double tap on SIGNUP can flash an error before the home page

After a successful signup, `send()` in `add-song.js` starts loading the home page and its `finally` block re-enables
the bar while the page is still leaving. A second tap in that gap sends the signup again; the server refuses it ("You
already signed up with this song tonight") and the page can show that error for a moment before the home page
replaces it. The singer has exactly one song in the right place. The refused request is one extra request per
double tap during the rush.

Fix: on success, return right after `goHome` with the bar still disabled, and re-enable the bar only after the
popups or an error, instead of in `finally`.

## A singer can sign up twice with a song another singer also has

`add_song_request` refuses a song the singer already has by looking at one matching song only, the one earliest in
the lineup (`.first()`, with songs ordered by position). When another singer's copy is earlier, the singer's own
copy is not seen, and a second signup with the same song creates a second copy for them. `update_song` has the same
blind spot when deciding the duplicate mark. It needs the same singer to submit the same taken song twice.

Fix: check "does this singer already have it" with `filter(..., singer=current_user).exists()`, and find the other
singer with `.exclude(singer=current_user).first()`, in both views.

## A refresh before opening empties a typed song

A song the singer typed into the form lives only in the page, so refreshing the signup page empties the form. A
song chosen from the People's Choice list comes back after a refresh (`restoreMyChoice`), because the server keeps
the choice. A singer who typed their own song and refreshes just before signup opens has to type it again at go
time.

Fix: keep the typed song and musical in `sessionStorage` and refill an empty form from it on load.

## The Edit button shows a light focus ring after the song form closes

When the song form popup closes, the browser returns focus to the Edit button that opened it, and Chrome draws its
focus outline around it on the dark card until the singer taps elsewhere. Cosmetic.

Fix: hide the focus outline on `#edit-song` in `song_signup/static/scss/_add_song.scss`.
