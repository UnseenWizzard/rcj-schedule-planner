# Plan: Schedule Editor UI

## Overview

A browser-based schedule editor (`ui/schedule_editor.html`) that loads a `schedule.json`, lets users move runs/interviews to different time slots (with swap logic and validation), shows a diff of changes, and exports the edited schedule with a change summary.

Single self-contained HTML file (same pattern as `schedule_viewer.html`).

---

## Data Model (in-memory)

- `originalSchedule` — parsed from loaded JSON, never mutated (used for diff)
- `editedSchedule` — deep clone of original, all edits apply here
- `changeLog` — array of `{ team, from: {day, start, end, resource}, to: {day, start, end, resource} }` entries

---

## Checklist

- [x] Task 1: Scaffold the editor HTML with file loading
- [x] Task 2: Render the editable schedule grid
- [x] Task 3: Implement slot selection and move UI
- [ ] Task 4: Implement the Changes & Diff tab
- [ ] Task 5: Download edited schedule with info field
- [ ] Task 6: Polish and edge cases

---

## Tasks

### Task 1: Scaffold the editor HTML with file loading

Create `ui/schedule_editor.html` with:
- Header bar ("RCJ Schedule Editor")
- File drop zone / file picker to load `schedule.json` (reuse pattern from viewer)
- Two tabs: **Editor** | **Changes & Diff**
- On load: parse JSON into `originalSchedule` and deep-clone into `editedSchedule`
- Render a basic table of all assignments grouped by day (read-only for now)

**Acceptance:**
- Can open the file in browser, drop a `schedule.json`, see assignments listed
- Tab switching works (Changes tab can be empty placeholder)

**After task:** make a git commit. Update the checklist above.

---

### Task 2: Render the editable schedule grid

Render `editedSchedule` as an interactive schedule view:
- Group assignments by day (day tabs like the viewer)
- For each day, show a table: rows = time slots, columns = resources (arenas + interview)
- Each cell shows the team name(s) assigned to that resource at that time
- Empty cells represent available slots
- Team cells are styled as draggable-looking tags (but drag comes later)

**Key details:**
- Time slots should be derived from the assignments themselves (collect all unique start times)
- Resources derived from assignments (collect all unique resource kind+name)
- A cell is identified by `(day, timeSlot, resource)`

**Acceptance:**
- Schedule renders correctly matching the data in the JSON
- Day tabs switch between days
- Empty slots are clearly visible

**After task:** make a git commit. Update the checklist above.

---

### Task 3: Implement slot selection and move UI

Add click-to-select-then-click-to-move interaction:

1. Clicking a team cell **selects** it (highlight with border/color). Store `selectedAssignment` in state (the assignment index + team).
2. Once selected, all **valid target cells** for that team are highlighted in a different color (e.g., light green). Invalid targets are not highlighted. Only cells on the **same resource** column are valid targets (you move within the same arena/interview resource).
3. Clicking a valid target cell performs the move:
   - If target is **empty**: move the team's assignment to that time slot
   - If target is **occupied by another team**: **swap** the two teams' time slots
4. Clicking elsewhere or pressing Escape deselects.

**Validation rules** (checked before highlighting valid targets):
- The team must not already have another assignment (run or interview) that overlaps with the target time slot
- Buffer time (`meta.buffer_minutes`) must be respected: no other assignment for the team within buffer_minutes of the target slot
- Check both directions: the moved team's other assignments, AND if swapping, the other team's other assignments against the swapped-to slot

Use `TimeSlot.overlaps` and `TimeSlot.buffer_conflict` logic from `models.py`, reimplemented in JS.

**State changes on move:**
- Update the assignment's `slot` (day/start/end) in `editedSchedule`
- If swap: update both assignments
- Append entry to `changeLog`

**Acceptance:**
- Selecting a team cell highlights it
- Valid target slots are visually indicated
- Moving to empty slot works
- Swapping two teams works
- Invalid moves (overlap/buffer conflict) are not offered as targets
- Multiple sequential edits work correctly

**After task:** make a git commit. Update the checklist above.

---

### Task 4: Implement the Changes & Diff tab

The second tab shows two sections:

#### 4a: Change summary list
- List each change from `changeLog` in human-readable form:
  `"Team X: Maze – Arena 1 Day1 11:00-11:10 -> Day1 11:20-11:30"`
- If a swap occurred, show both teams' changes
- An "Undo last change" button that reverts the most recent change (pop from `changeLog`, restore previous slot values)

#### 4b: JSON diff view
- Show a side-by-side or unified text diff between `JSON.stringify(originalSchedule, null, 2)` and `JSON.stringify(editedSchedule, null, 2)`
- Implement a simple line-by-line diff: for each line, mark as added (green), removed (red), or unchanged
- No external libraries — a basic longest-common-subsequence or line-comparison is sufficient
- Style like a typical diff viewer (monospace font, colored backgrounds)

**Acceptance:**
- After making edits, switching to Changes tab shows the change list
- Diff correctly highlights changed lines in the JSON
- Undo reverts the last change and updates both the summary and diff

**After task:** make a git commit. Update the checklist above.

---

### Task 5: Download edited schedule with info field

Add a "Download" button (visible when there are changes) that:

1. Builds the output JSON from `editedSchedule`
2. Adds an `"info"` field at the top level containing a text summary of all changes:
   ```json
   {
     "info": "Schedule edited on 2026-04-04\nChanges:\n- Team Alpha: Maze – Arena 1 Day1 11:00-11:10 -> 11:20-11:30\n- Team Beta: Maze – Arena 1 Day1 11:20-11:30 -> 11:00-11:10",
     "meta": { ... },
     "assignments": [ ... ]
   }
   ```
3. Triggers a browser file download as `schedule_edited.json`

**Info field format:**
```
Schedule edited on YYYY-MM-DD
Changes:
- {team}: {resource} {day} {old_start}-{old_end} -> {day} {new_start}-{new_end}
```
(One line per team move. Swaps produce two lines.)

**Acceptance:**
- Download button appears only when changes exist
- Downloaded JSON is valid, parseable by `persistence.py`'s `load()` function (the `info` field is ignored by load since it only reads `meta` and `assignments`)
- Info field contains accurate change descriptions
- Downloaded file can be loaded back into the editor

**After task:** make a git commit. Update the checklist above.

---

### Task 6: Polish and edge cases

- Visual feedback: show a brief toast/flash when a move is made ("Swapped Team A and Team B")
- Show validation warnings if the schedule has any existing violations on load (reimplement `validate_schedule` logic in JS, show as a banner)
- Handle interview group assignments correctly: when an interview slot has multiple teams, the entire group moves together (not individual teams)
- Ensure the editor works with the existing `schedule.json` test files in the repo
- Test with the viewer: load an edited schedule in `schedule_viewer.html` to verify it renders correctly

**After task:** make a git commit. Update the checklist above.

---

## Non-goals
- No drag-and-drop (click-to-select is simpler and more accessible)
- No cross-resource moves (a team can't be moved from Arena 1 to Arena 2 — that changes the arena assignment)
- No adding/removing assignments, only moving existing ones
- No server component — everything runs client-side

## Technical notes
- Buffer conflict and overlap logic from `models.py` must be faithfully reimplemented in JS
- The `schedule.json` format is defined in `persistence.py` — the editor must read and write this exact format
- Interview assignments can have multiple teams (group interviews) — moves apply to the whole group
