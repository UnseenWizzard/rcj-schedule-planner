# Plan: Fix arena_reset scheduling (v2)

## Problem summary

The current general-purpose scheduler treats arena_reset as a gap enforced after
every Nth assignment on an arena (where N = number of teams). This works for the
simple case but is fragile — breaks can split a "round" across long gaps, and the
slot-by-slot iteration makes it hard to guarantee predictable round structure.

For single-arena divisions with `arena_reset`, the expected schedule is
straightforward:

```
Round 1: Team0 → Team1 → … → TeamN (back-to-back, respecting breaks)
[arena_reset gap — interviews may be scheduled here]
Round 2: Team0 → Team1 → … → TeamN
[arena_reset gap]
…
Round R: Team0 → Team1 → … → TeamN
```

The general-purpose slot iterator is overkill for this pattern and introduces
subtle ordering bugs. A dedicated scheduling path for this case is simpler and
more correct.

## Tasks

- [x] ~~Task 1 — Fix Bug 1: apply reset only after a complete round~~
- [x] ~~Task 2 — Fix Bug 2: use day-aware datetimes in the reset comparison~~
- [x] ~~Task 3 — Update the existing arena-reset test to match correct round semantics~~
- [x] ~~Task 4 — Add an integration test that uses should_work.sh~~

---

### New tasks (v2)

- [x] **Task 5 — Add a pytest test validating reset gaps between all consecutive rounds**

  This test mirrors the `should_work.sh` scenario (4 teams, 1 arena, 4 runs,
  `arena_reset=60`, 2 days with a lunch break) and checks the schedule structure.

  In `tests/test_scheduler.py`:

  1. Create a test `test_arena_reset_all_rounds_should_work_scenario` with:
     - 4 teams, 1 arena, `runs_per_arena=4`, `arena_reset=60`
     - `day_specs = ["Day1:10:30-18:00", "Day2:09:00-13:00"]`
     - `breaks = [Break(day="Day1", start=time(12,30), end=time(13,30))]`
     - `run_time=10, interview_time=15, interview_group_size=2, buffer_minutes=10`
  2. Assert the schedule is valid (`validate_schedule` returns no violations).
  3. Extract arena runs, sorted by `(day, start)`.
  4. Assert there are exactly 16 arena runs (4 teams × 4 rounds).
  5. Group runs into consecutive rounds of 4. For each pair of consecutive rounds,
     compute the gap between the last slot's end of one round and the first slot's
     start of the next round (using the `day_index` trick for cross-day comparison).
     Assert the gap is ≥ 60 minutes.
  6. Within each round, assert consecutive runs have **no** reset-sized gap
     (gap < 60 min — they should be back-to-back or only separated by a break).
  7. Run all tests (`python -m pytest tests/`) and fix any failures, then commit.

- [x] **Task 6 — Implement simplified single-arena scheduling with arena_reset**

  When a division has exactly 1 arena and `arena_reset > 0`, use a dedicated
  scheduling path instead of the general slot iterator. This path schedules runs
  deterministically round-by-round.

  In `rcj_planner/scheduler.py`, inside `build_schedule`, before the existing
  arena scheduling loop for a division:

  1. Detect the simplified case: `num_arenas == 1 and div_arena_reset > 0`.
  2. When detected, use this algorithm instead of the general slot loop:
     ```
     arena = arenas[0]
     slot_cursor = 0   # index into run_slots

     for round_num in range(runs_per_arena):
         # If not the first round, advance cursor past the arena_reset gap
         if round_num > 0:
             last_end = _slot_end_dt(last_assigned_slot)
             required_start = last_end + timedelta(minutes=div_arena_reset)
             while slot_cursor < len(run_slots):
                 if _slot_start_dt(run_slots[slot_cursor]) >= required_start:
                     break
                 slot_cursor += 1

         # Schedule each team in order, back-to-back
         for team in teams:
             while slot_cursor < len(run_slots):
                 slot = run_slots[slot_cursor]
                 slot_cursor += 1
                 if _resource_conflicts(slot, arena, assignments):
                     continue
                 if _team_conflicts(slot, team, assignments, buffer_minutes):
                     continue
                 assignments.append(Assignment(slot, arena, [team]))
                 team_runs[team] += 1
                 team_day_runs[team][slot.day] += 1
                 last_assigned_slot = slot
                 break
             else:
                 raise SchedulingError(...)
     ```
  3. After scheduling all rounds, verify each team has `runs_per_arena` runs
     (same check as the general path).
  4. Skip the general slot-iterator path for this division (use `continue` or
     an `else` branch).
  5. Run all tests (`python -m pytest tests/`) and fix any failures, then commit.

- [x] **Task 7 — Schedule interviews in arena_reset gaps (simplified mode)**

  For divisions using the simplified single-arena path, interviews can be
  scheduled during the reset breaks between rounds.

  In `rcj_planner/scheduler.py`:

  1. Move interview scheduling for simplified-mode divisions into Phase 1,
     right after all arena rounds are placed. After each round (except the last),
     there is a known reset gap. Try to schedule interview groups for this
     division's teams into interview slots that fall within these gaps.
  2. The interview scheduling should still use the shared `interview_resource`
     and respect `_team_conflicts` and `_resource_conflicts`.
  3. Fall back to the existing Phase 2 interview scheduling for any groups that
     couldn't be placed in gaps (e.g., if the gap is too short or all interview
     slots are taken).
  4. Ensure the existing Phase 2 loop skips divisions whose interviews were
     already fully scheduled in Phase 1.
  5. Run all tests (`python -m pytest tests/`) and fix any failures, then commit.

- [x] **Task 8 — Update should_work integration test and verify end-to-end**

  1. The `should_work.sh` script references `input/Online_Simulation.csv` which
     is gitignored. Update `tests/integration/should_work.sh` (and the pytest
     wrapper `tests/test_integration_should_work.py`) to create a temporary
     team CSV inline so the test is self-contained and doesn't depend on
     gitignored input files.
  2. Run the integration test and verify it passes.
  3. Run the full test suite (`python -m pytest tests/`) and fix any failures,
     then commit.
