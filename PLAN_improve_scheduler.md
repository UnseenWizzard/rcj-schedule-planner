# Plan: Improve Scheduler

## Goal

Modify the scheduler so that teams have **most of their runs on earlier days**. For a 2-day event where each team has 3 runs, as many teams as possible should have 2 runs on Day 1 and 1 run on Day 2.

## Current Behavior

The scheduler iterates through all timeslots across all days chronologically (`generate_slots` produces Day1 slots then Day2 slots). It greedily assigns teams to slots using a round-robin over `required_pairs`. Because it fills slots top-down without any day-awareness, runs naturally spread across days roughly evenly (or based on available capacity).

**Key constraints** — the algorithm must continue to:
1. Never overlap slots for a team
2. Fill timeslots fully on each arena, packing from earliest time downward
3. Respect `buffer_minutes` between a team's assignments
4. Respect arena reset gaps, breaks, resource conflicts
5. Give each team exactly `num_arenas * runs_per_arena` total runs

## Design Approach

Change the **team selection priority** inside the greedy slot-filling loop so that teams with fewer runs on the current day are preferred. Within the inner loop that searches `required_pairs` for a candidate:

- Collect **all valid candidates** for the `(slot, arena)` pair
- Score each: prefer fewest runs on this slot's day → fewest total runs → original order (stability)
- Remove the `pair_idx` round-robin; selection is now score-based

This ensures Day 1 slots are front-loaded: all teams start at 0 day-runs so they fill evenly. When Day 2 begins, teams with fewer total runs are preferred — their remaining runs concentrate there.

---

## Task List

> Each task is self-contained and can be picked up independently. Read the **Files** and **Context** sections before starting a task.

### Task 1 — Add day-run tracking
- [x] In `rcj_planner/scheduler.py`, inside `build_schedule()` Phase 1 loop, add alongside `team_runs`:
  ```python
  team_day_runs = defaultdict(lambda: defaultdict(int))  # team -> day -> count
  ```
- [x] Update it when an assignment is made (next to `team_runs[team] += 1`):
  ```python
  team_day_runs[team][slot.day] += 1
  ```
- [x] Run `pytest` — all existing tests must pass (this change is additive, no behavior change yet)
- [x] Commit: `scheduler: track per-day run counts per team`

### Task 2 — Replace round-robin with scored candidate selection
- [x] In `rcj_planner/scheduler.py`, inside the `for arena in arenas:` loop, replace the round-robin scan with:
  1. Collect **all valid candidates** from `required_pairs` for this `(slot, arena)` (same filters: arena match, not in `used_teams`, run limits, resource/team conflicts)
  2. Pick candidate with lowest `team_day_runs[team][slot.day]`
  3. Tie-break: lowest `team_runs[team]`
  4. Tie-break: original position in `required_pairs` (stability)
- [x] Remove the `pair_idx` round-robin variable (no longer needed)
- [x] Run `pytest` — all existing tests must still pass
- [x] Commit: `scheduler: score-based candidate selection for early-day loading`

### Task 3 — Add tests for early-day loading
- [ ] In `tests/test_scheduler.py`, add the following test cases (all must pass after Task 2):

  **3a** `test_early_day_loading_2day_3runs` — 2 days, 3 runs/team, at least 5/6 teams have ≥2 runs on Day 1
  ```python
  def test_early_day_loading_2day_3runs():
      DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
      teams = [Team(f"Team{i}", "DivA") for i in range(6)]
      divisions = [("DivA", teams, 1, 3)]  # 1 arena, 3 runs per arena
      s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                         interview_group_size=3, buffer_minutes=10)
      assert validate_schedule(s) == []
      teams_with_2_on_day1 = 0
      for team in teams:
          arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
          day1_runs = [a for a in arena_runs if a.slot.day == "Day1"]
          assert len(arena_runs) == 3
          if len(day1_runs) >= 2:
              teams_with_2_on_day1 += 1
      assert teams_with_2_on_day1 >= 5, f"Only {teams_with_2_on_day1}/6 teams have 2+ runs on Day 1"
  ```

  **3b** `test_early_day_loading_no_violations` — 2 days, 4 runs/team, all constraints hold
  ```python
  def test_early_day_loading_no_violations():
      DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
      teams = [Team(f"Team{i}", "DivA") for i in range(8)]
      divisions = [("DivA", teams, 2, 2)]  # 2 arenas, 2 runs each = 4 runs per team
      s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                         interview_group_size=2, buffer_minutes=10)
      assert validate_schedule(s) == []
      for team in teams:
          arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
          assert len(arena_runs) == 4
  ```

  **3c** `test_single_day_unaffected` — single-day scheduling unchanged
  ```python
  def test_single_day_unaffected():
      teams = [Team(f"Team{i}", "DivA") for i in range(4)]
      divisions = [("DivA", teams, 2, 1)]
      s = build_schedule(divisions, ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                         interview_group_size=2, buffer_minutes=10)
      assert validate_schedule(s) == []
      for team in teams:
          arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
          assert len(arena_runs) == 2
  ```

  **3d** `test_early_day_loading_tight_day1` — short Day 1 overflows gracefully to Day 2
  ```python
  def test_early_day_loading_tight_day1():
      DAYS_TIGHT = ["Day1:09:00-10:00", "Day2:09:00-17:00"]
      teams = [Team(f"Team{i}", "DivA") for i in range(4)]
      divisions = [("DivA", teams, 1, 3)]
      s = build_schedule(divisions, DAYS_TIGHT, run_time=10, interview_time=20,
                         interview_group_size=2, buffer_minutes=10)
      assert validate_schedule(s) == []
      for team in teams:
          arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
          assert len(arena_runs) == 3
  ```

  **3e** `test_early_day_loading_multi_division` — front-loading works per division
  ```python
  def test_early_day_loading_multi_division():
      DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
      divisions = [
          ("Soccer", [Team(f"S{i}", "Soccer") for i in range(4)], 1, 3),
          ("Rescue", [Team(f"R{i}", "Rescue") for i in range(4)], 1, 3),
      ]
      s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                         interview_group_size=2, buffer_minutes=10)
      assert validate_schedule(s) == []
      for div_label, teams, _, _ in divisions:
          for team in teams:
              arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
              day1_runs = [a for a in arena_runs if a.slot.day == "Day1"]
              assert len(arena_runs) == 3
              assert len(day1_runs) >= 2, f"{team.name} has only {len(day1_runs)} runs on Day 1"
  ```

  **3f** `test_early_day_loading_buffer_respected` — buffer minutes respected while front-loading
  ```python
  def test_early_day_loading_buffer_respected():
      DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
      teams = [Team(f"Team{i}", "DivA") for i in range(4)]
      divisions = [("DivA", teams, 1, 3)]
      s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                         interview_group_size=2, buffer_minutes=15)
      assert validate_schedule(s) == []
  ```

- [x] Run `pytest` — all 6 new tests must pass alongside all existing tests
- [x] Commit: `tests: early-day loading test cases`

### Task 4 — Verify and finalise
- [ ] Run `pytest` — full suite green
- [ ] Run the CLI with a 2-day config and confirm Day 1 is visibly heavier than Day 2
- [ ] If the verification shows the changes do not have the desired effect, tell the user and add further Tasks to this plan file. 

---

## Files

| File | Change |
|------|--------|
| `rcj_planner/scheduler.py` | Add `team_day_runs` tracking; replace round-robin with scored selection |
| `tests/test_scheduler.py` | Add 6 new test cases (3a–3f) |

## Risks

- **Slower selection**: scanning all candidates per slot vs. rotating index. Bounded by team count (<100 in practice) — negligible.
- **Round-robin ordering effects**: existing tests that passed only because of a specific round-robin order may surface. The scored approach is strictly more flexible; all existing tests act as regression guards.
- **Day 1 too small**: if Day 1 cannot hold most runs the algorithm still falls through to any valid candidate (scoring is preference, not hard constraint). Test 3d validates this.
