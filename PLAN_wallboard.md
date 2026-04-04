# Plan: Wallboard View for schedule_viewer.html

## Overview

Add a "Wallboard" view to the schedule viewer that cycles through divisions (and their interviews) one at a time, showing each for a configurable duration (default 15 seconds). Designed for large screens / projectors at venues.

---

## Tasks

- [x] **Task 1: Add wallboard state and view button**

  1. Add wallboard-related fields to the `state` object:
     - `wallboardInterval: 15` (seconds per division)
     - `wallboardDivIdx: 0` (currently shown division index)
     - `wallboardTimer: null` (setInterval handle)
     - `wallboardPaused: false`
  2. Add a new view button in the HTML view selector:
     ```html
     <button class="view-btn" data-view="wallboard">Wallboard</button>
     ```
  3. Add the `'wallboard'` case to the `render()` dispatcher so it calls `renderWallboardView()` (stub returning empty string for now).
  4. Add keyboard shortcut `4` → `switchView('wallboard')`.
  5. Hide the wallboard view button on mobile (`@media (max-width: 767px)`) — it's a large-screen tool.
  6. Verify the app loads without errors, then commit.

- [x] **Task 2: Implement `renderWallboardView()` — division schedule display**

  1. Create function `renderWallboardView()` that:
     - Gets all divisions via `allDivisions()`.
     - Picks the current division from `state.wallboardDivIdx`.
     - For the selected division, for each day:
       - Collects all assignments where `divisionOf(resource) === currentDivision`.
       - Collects all interview assignments where teams from this division are scheduled (match team names that appear in this division's arena assignments).
       - Sorts by time slot.
       - **Filters to "from now" by default**: use the browser clock to determine the current time. Only show slots whose end time is >= now (i.e. currently running or upcoming). Past slots are hidden. On days that are entirely in the past or future, use a simple heuristic: if today matches a day label show from-now; otherwise show all slots for future days and skip past days entirely.
     - Renders a large, full-width layout:
       - **Header bar**: division name (with its `divColor`), a progress indicator showing "Division X of Y", and the cycle interval.
       - **Day sections**: for each day, a clear sub-header, then a table showing time slot, arena/resource (short name), and teams — similar to the existing day view but filtered to one division.
       - **Interview section per day**: below each day's arena schedule, show that division's interview slots (time + teams) if any exist.
  2. **Viewport-fit / no-cutoff logic**: the rendered content must not be cut off at the bottom of the screen.
     - After rendering, measure the content height vs the viewport height.
     - If content fits in one screen: display it as-is (no scroll).
     - If content overflows: enable a slow **auto-scroll** that scrolls the content from top to bottom over the cycle interval, pausing briefly at top and bottom. Use `scrollTo` with smooth behavior or a `requestAnimationFrame` loop. This ensures all rows are visible before the next division cycles in.
     - As a fallback, dynamically reduce font size (step down in increments, e.g. 1.2rem → 1.1rem → 1.0rem) if the overflow is small, before resorting to auto-scroll.
  3. Use large, readable font sizes suitable for projectors (1.1–1.3rem for body, 1.5rem+ for headers).
  4. Verify rendering is correct with sample data, then commit.

- [x] **Task 3: Implement auto-cycling timer**

  1. In `render()`, when `state.view === 'wallboard'`:
     - Clear any existing `state.wallboardTimer` and cancel any running auto-scroll animation.
     - After render, check if auto-scroll is needed (content overflows viewport). If so, start the scroll animation first — the cycle timer only starts **after** the scroll completes (or immediately if no scroll is needed).
     - Total dwell time per division = `state.wallboardInterval * 1000` (scroll time is part of this, not added on top).
     - When the dwell time elapses, increment `state.wallboardDivIdx` (wrapping) and call `render()`.
  2. When switching away from wallboard view, clear the timer and cancel any scroll animation in `render()`.
  3. Add a visual countdown/progress bar at the top or bottom of the wallboard view:
     - A thin horizontal bar that animates from 0% to 100% width over the total dwell duration using a CSS animation (`@keyframes`) keyed to `state.wallboardInterval`.
  4. Verify cycling works correctly, then commit.

- [x] **Task 4: Add wallboard controls (pause, interval, manual nav)**

  1. Add a slim control bar at the top of the wallboard view with:
     - **Pause/Resume button**: toggles `state.wallboardPaused`. When paused, clear the timer and show a "Paused" indicator; when resumed, restart it.
     - **Previous / Next buttons**: manually go to prev/next division (wrapping). Resets the timer countdown.
     - **Interval selector**: a small input or dropdown to change seconds (5, 10, 15, 20, 30, 60). Updates `state.wallboardInterval` and restarts the timer.
  2. Add keyboard shortcuts within wallboard view:
     - `Space` → pause/resume
     - `ArrowLeft` → previous division
     - `ArrowRight` → next division
  3. Wire up event listeners in `render()` for these controls.
  4. Verify controls work, then commit.

- [x] **Task 5: Wallboard CSS and polish**

  1. Add CSS for the wallboard view:
     - Dark background (e.g. `#1e1b4b` or similar) with white/light text for projector readability.
     - Full-viewport-height layout (no scroll ideally, or minimal scroll for very long schedules).
     - Division color used as accent (header bar background, progress bar color).
     - Large table cells with generous padding.
     - Smooth fade or slide transition between divisions (CSS transition on opacity or transform).
  2. Hide the main header and view selector when in wallboard "fullscreen" mode — or provide a small "Exit Wallboard" button in a corner.
  3. Add `@media print` rule to hide wallboard controls.
  4. Consider adding a `?wallboard=15` URL parameter that auto-enters wallboard mode on load (useful for setting up a kiosk browser).
  5. Verify visual appearance, then commit.

- [ ] **Task 6: URL parameter for auto-start wallboard**

  1. In the `applyHash()` function (or a new URL-params handler), check for `#wallboard` or `#wallboard=<seconds>` in the URL.
  2. If present, automatically switch to wallboard view with the specified interval (or default 15s).
  3. Update `updateHash()` to persist wallboard state in the URL when active.
  4. Verify auto-start works, then commit.
