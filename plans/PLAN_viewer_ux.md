# UX Improvement Plan: schedule_viewer.html

## Context

The viewer serves two main audiences:
1. **Organizers** who need the full-day overview (which arenas are busy when, are there conflicts)
2. **Team mentors/participants** who need to quickly find "when and where does my team go next"

---

## A. Schedule Overview (Day View) Improvements

### A1. Sticky time column + frozen headers
**Problem:** The grid scrolls horizontally for many arenas — once you scroll right, you lose the time column. On tall schedules you also lose the header rows.
**Fix:** Make the time column `position: sticky; left: 0` and the `<thead>` `position: sticky; top: 0` (within the `.grid-wrapper`). Give both a solid background so content doesn't bleed through.

### A2. Visual break rows
**Problem:** Breaks (lunch, division-specific pauses) are defined in the JSON metadata but invisible in the grid. Users see empty cells with no explanation.
**Fix:** Detect break periods from `meta.breaks` (or infer from gaps). Insert a spanning row with a muted label like "Lunch Break 12:30–13:30" across the full table width. Use a light grey/hatched background to distinguish it from empty slots.

### A3. "Now" indicator (optional, low priority)
**Problem:** During the event, organizers need to quickly locate the current timeslot.
**Fix:** If the browser clock falls within any timeslot range, highlight that row with a subtle left-border accent and scroll it into view on load.

### A4. Compact/comfortable density toggle
**Problem:** The grid has generous padding which works well on large screens but forces excessive scrolling on laptops.
**Fix:** Add a small density toggle (compact / default) in the header bar. Compact mode reduces cell padding, font-size, and `min-width` on `.slot-cell`.

### A5. Clickable team tags in overview
**Problem:** Seeing a team name in the grid gives no easy path to viewing that team's full schedule.
**Fix:** Make `.team-tag` elements in the Day view clickable. Clicking switches to the Team view with that team name pre-filled in the search box.

---

## B. Team View Improvements

### B1. Show all teams by default (grouped by division)
**Problem:** The current team view shows nothing until you search — users who don't know exact team names are stuck. There's no browsable list.
**Fix:** When search is empty, show a grouped listing: one collapsible section per division, listing team names alphabetically. Each team name is a clickable link that opens/expands their full schedule card. This lets mentors browse to find their team.

### B2. Improve search: instant results + fuzzy matching
**Problem:** Search is exact substring match. "b.robots" won't match "B.Robots Seniors". Users may not type the exact casing.
**Fix:** Search is already case-insensitive (good), but add:
- Show result count ("3 teams found")
- Highlight the matching substring within team names
- Consider a lightweight fuzzy match (e.g., splitting on spaces and matching each token independently) so "robots senior" matches "B.Robots Seniors"

### B3. Direct-link / shareable URL per team
**Problem:** Mentors can't bookmark or share a link to their team's schedule.
**Fix:** Update the URL hash when viewing a team (e.g., `#team=Eurobot`). On page load, if a hash is present, auto-load the schedule and jump to that team's card. This also enables QR codes on printed schedules.

### B4. Visual timeline for a team's day
**Problem:** The team card shows a table of assignments, but it's hard to visually grasp gaps, back-to-back runs, or how spread out assignments are.
**Fix:** Add a simple horizontal or vertical timeline bar above/beside the table showing the team's slots as colored blocks against the full day range. Gaps are visible as whitespace. Color-code by division (arena runs vs interview).

### B5. Conflict / tight-turnaround warnings
**Problem:** If a team has two assignments with < buffer_minutes between them (or overlapping), this is invisible.
**Fix:** Compare consecutive assignments for a team. If the gap is less than the configured `buffer_minutes`, show a small warning icon/badge on the team card. Helps organizers catch scheduling problems.

---

## C. Cross-cutting Improvements

### C1. Print / export-friendly mode
**Problem:** Organizers often print schedules to post on walls at the venue.
**Fix:** Add a print stylesheet (`@media print`) that removes the header chrome, maximizes table width, forces page-break-inside: avoid on cards, and uses black-and-white-friendly styling. Add a "Print" button in the header.

### C2. Keyboard navigation
**Problem:** Everything is mouse-only. Power users (organizers switching between views quickly) would benefit from keyboard shortcuts.
**Fix:** 
- `1`/`2`/`3`/`4` to switch views (Day / Division / Interview / Team)
- Left/Right arrow to switch day tabs in Day view
- `/` to focus the team search box

### C3. Responsive / mobile layout
**Problem:** The grid view is essentially unusable on phones. Even the team view has no mobile-specific layout.
**Fix:** On narrow viewports (`<768px`):
- Day view: collapse the grid into a vertical list grouped by timeslot, showing resource + team as stacked cards
- Team view: make cards full-width, increase tap targets
- Hide division view on mobile (it's an organizer tool)

### C4. Loading state for URL fetch
**Problem:** When loading from URL, the only feedback is the button changing to "Loading..." — no spinner or progress indication.
**Fix:** Add a simple CSS spinner animation next to the button text. Show elapsed time if > 2s.

---

## D. Combine Day & Division Views — Division Filter on Day View

### Context
The "By Division" view exists as a separate organizer tool, but its primary use case (focusing on specific divisions) can be folded into the Day view as a filter. This simplifies the UI to fewer views while making the Day view more powerful.

### D1. Add division filter toggles to Day view
**What:** Add a row of pill/chip-style toggle buttons between the day tabs and the schedule table. Each button shows a division name with its assigned color. By default all divisions are visible (all toggles "on"). Clicking a toggle hides/shows that division's columns in the table. An "All" button resets to show everything.

**State change:** Add `hiddenDivisions: new Set()` to the `state` object.

**Rendering changes in `renderDayView()`:**
- After computing `resources = resourcesForDay(day)`, filter out resources whose `divisionOf(r)` is in `state.hiddenDivisions`
- This naturally removes hidden divisions from header rows, data cells, and mobile cards
- Generate the filter toggle HTML using `allDivisions()` and `divColor()`

**Event wiring in `render()`:**
- Division filter button click: toggle division in/out of `state.hiddenDivisions`, re-render
- "All" button click: clear `state.hiddenDivisions`, re-render

### D2. Remove the standalone "By Division" view
- Remove `<button class="view-btn" data-view="division">` from HTML
- Remove `renderDivisionView()` function
- Remove the `state.view === 'division'` branch in `render()`
- Remove `.div-cards`, `.div-card`, `.div-card-header` CSS rules
- Update keyboard shortcuts: `1` = Day, `2` = Interviews, `3` = By Team

### D3. Add CSS for filter toggles
- Pill-style buttons in a flex-wrap container
- Active (visible): filled with division color, white text
- Inactive (hidden): outlined border with division color, faded text
- Responsive: wraps naturally on narrow screens

### Verification
- Load a schedule with multiple divisions → all shown by default (same as current)
- Toggle a division off → its columns disappear from table and mobile view
- Toggle back on → columns reappear
- Click "All" → resets to showing everything
- Keyboard shortcuts `1`/`2`/`3` work correctly for the three remaining views
- Mobile layout handles filtered divisions correctly

---

## Suggested Implementation Order

| Priority | Item | Effort | Impact | Status |
|----------|------|--------|--------|--------|
| 1 | A1 - Sticky headers/time column | Small | High | Done |
| 2 | B1 - Show all teams by default | Medium | High | Done |
| 3 | A5 - Clickable team tags | Small | High | Done |
| 4 | B3 - Shareable URL per team | Small | High | Done |
| 5 | A2 - Visual break rows | Medium | Medium | Done |
| 6 | B2 - Better search | Small | Medium | Done |
| 7 | B4 - Visual timeline | Medium | Medium | Done |
| 8 | C1 - Print mode | Medium | Medium | Done |
| 9 | A4 - Density toggle | Small | Low | Done |
| 10 | B5 - Conflict warnings | Medium | Medium | Done |
| 11 | C2 - Keyboard nav | Small | Low | Done |
| 12 | C3 - Mobile layout | Large | Medium | Done |
| 13 | A3 - Now indicator | Small | Low | Done |
| 14 | C4 - URL loading spinner | Small | Low | Done |
| 15 | D1 - Division filter on Day view | Medium | High | Done |
| 16 | D2 - Remove standalone Division view | Small | Medium | Done |
| 17 | D3 - Filter toggle CSS | Small | Medium | Done |
