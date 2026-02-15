Photo Viewer Interaction State Model
==================================

Last saved: 2026-02-15

Core runtime states
------------------

- `idle`: gallery grid is interactive, no overlay.
- `opening`: overlay is animating into detail position.
- `expanded`: overlay is active and user input is accepted.
- `closing`: overlay is animating back to source tile.

Tracked flags
-------------

- `isNavigating`: slide transition for left/right photo navigation is in-flight.
- `isModeFading`: high/color opacity transition is in-flight.
- `singleClickTimer`: deferred single-click handling for BW toggle.
- `navigationTimer`: navigation fallback timer / hardening.
- `openTimer`/`closeTimer`: open/close transition hardening.

Mode model
----------

- Grid starts in BW.
- Overlay starts in BW.
- On open completion, overlay switches to:
  - per-image preferred non-BW mode derived from state.
  - if image is down-rated, preferred mode is the stored down mode (`high` or `color`).
  - otherwise preferred mode is per-image `nonBwMode` or fallback `high`.
- On left/right navigation, incoming image mode is selected from that image's preferred state (not previous image transition path).
- Single click in overlay: `bw <-> nonBwMode` (toggle to/from BW).
- Right click or double-click (mac): `high <-> color`.
- Keyboard `c`: `high <-> color`.

Rating model
------------

- `ratings[index]`: `up | down | undefined` for image index.
- `ratingModes[index]`: stores down-mark state by restoration mode:
  - `high`, `color`, or `both`.
  - legacy fallback: if image is `down` with no mode key, treat as `high`.
- On setting rating:
  - update `ratings`.
  - if rating is `down`, add the active restoration mode to `ratingModes` (independent high/color stickiness).
  - marker visibility is immediate on keypress; class application occurs in the same event.
  - a `down` marker is version-bound and mode-specific:
    - down in `high` only marks `high`.
    - down in `color` only marks `color`.
    - both can be marked independently and persist.
    - never appears in BW.
  - shortcut keys are idempotent assignments:
    - `1` always sets `up`.
    - `2` always sets `down`.
    - repeat keydown does not clear existing ratings.
  - apply classes to both:
    - `.tile[data-index="..."]`
    - `.tile-overlay[data-index="..."]`
  - persist storage and refresh summary.
- Summary text: `Thumbs: 👍 {up} / 👎 {down} ({total rated})`.

Critical transition safeguards
-----------------------------

- Mode completion must be driven by CSS `transitionend` on opacity.
- Mode fade only blocks navigation queuing; rating updates still apply immediately and stay bound to the version captured at keypress.
- Rating and mode transitions should remain idempotent to avoid lost UI states.

Reference / audit points
------------------------

- State definition and mutation: `viewer.js`
- Rating class rendering: `viewer.js` + `viewer.css`
- Entry points to verify each change:
  - `openZoom`
  - `applyZoomMode`
  - `setRating`
  - `syncRatingForIndex`
  - `navigateToPhoto`
  - `closeZoom`
