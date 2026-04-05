# Plan: Per-Location View (replacing Interview view)

## Goal

Replace the current "Interviews" view in `schedule_viewer.html` with a general-purpose "By Location" view that can show the schedule filtered to any single location (division arena or interview location).

## Context

Currently:
- The viewer has views: **By Day**, **Interviews**, **By Team**, **Wallboard**
- The "Interviews" view (`renderInterviewView()`) is hardcoded to filter rows where `resource === 'Interview'` and shows a day-grouped table of interview time slots and teams
- Each schedule row has a `resource` field like `"Line – Arena 1"`, `"Maze – Arena 1"`, or `"Interview"`
- Helper `divisionOf(resource)` extracts the division name; `shortName(resource)` extracts the arena part
- The `resourcesForDay(day)` function returns all unique resource names for a given day, sorted by division

## Design

The new "By Location" view will:
1. Show a **location picker** (dropdown or button group) listing all unique `resource` values across all days (e.g. "Line – Arena 1", "Maze – Arena 1", "Interview")
2. When a location is selected, display a **day-grouped table** (similar to current interview view) showing all time slots at that location with their teams
3. Default to the first location alphabetically, or "Interview" if present (to preserve existing quick-access to interviews)

---

## Tasks

- [x] **Task 1: Add state and collect locations**

  1. In `schedule_viewer.html`, add a `selectedLocation: null` field to the `state` object (around line 788).
  2. Create a helper function `allLocations()` that collects all unique `resource` values from `state.days` across all days and returns them sorted (divisions first, then "Interview" last — reuse the existing sort logic from `resourcesForDay`).
  3. No tests needed (HTML-only change). Make a git commit.

- [x] **Task 2: Rename view button and update view routing**

  1. Change the view button from `<button class="view-btn" data-view="interview">Interviews</button>` (line 776) to `<button class="view-btn" data-view="location">By Location</button>`.
  2. In the `render()` function (around line 1646), change the `state.view === 'interview'` branch to `state.view === 'location'` and call `renderLocationView()` instead of `renderInterviewView()`.
  3. Update the keyboard shortcut (line 1857) from `switchView('interview')` to `switchView('location')` for the `2` key.
  4. Update the mobile CSS that currently hides `data-view="division"` — check if `data-view="location"` also needs hiding on mobile (probably not, as it's useful for volunteers at a specific location).
  5. No tests needed (HTML-only change). Make a git commit.

- [x] **Task 3: Implement `renderLocationView()`**

  1. Replace the `renderInterviewView()` function (lines 1111–1156) with a new `renderLocationView()` function.
  2. The function should:
     - Call `allLocations()` to get available locations.
     - If `state.selectedLocation` is null or not in the list, default to the first location (or "Interview" if present).
     - Render a **location picker** at the top — a row of pill/tag buttons (styled like the existing view-selector buttons), one per location. Highlight the active one.
     - Attach click handlers (via `onclick` or event delegation) that set `state.selectedLocation` and re-render.
     - Filter all rows across all days where `row.resource === state.selectedLocation`.
     - Group filtered rows by day, sort by time slot within each day.
     - Render a day-grouped card layout (reuse the `div-card` / `div-card-header` styling from the existing interview view) with columns: **Time**, **#** (slot number within that day), **Teams** (as team-tag chips).
     - Use the division color (`divColor(divisionOf(selectedLocation))`) for the card header background.
     - Show an empty state message if no slots found for the selected location.
  3. No tests needed (HTML-only change). Make a git commit.

- [x] **Task 4: Clean up old interview-specific code**

  1. Remove the now-unused `renderInterviewView()` function if not already replaced in Task 3.
  2. Search for any remaining references to `'interview'` as a view name (e.g. in URL hash handling around lines 1780–1805, any `data-view="interview"` checks) and update them to `'location'`.
  3. Verify the wallboard view's interview section still works correctly — it uses its own filtering logic (`r.resource === 'Interview'`) independent of the view, so it should be unaffected. Just confirm.
  4. No tests needed (HTML-only change). Make a git commit.

- [ ] **Task 5: Manual verification**

  1. Open `schedule_viewer.html` in a browser with `ui/schedule.json` loaded.
  2. Verify the "By Location" button appears where "Interviews" used to be.
  3. Verify the location picker shows all arenas and "Interview".
  4. Click through several locations and confirm correct rows display.
  5. Verify keyboard shortcut `2` switches to the location view.
  6. Verify the wallboard and other views still work.
  7. Make a final commit if any tweaks are needed.
