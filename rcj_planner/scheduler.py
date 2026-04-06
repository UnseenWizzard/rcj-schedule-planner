from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, timedelta
from rcj_planner.models import Team, TimeSlot, Resource, Assignment, Schedule, Break, Division
from rcj_planner.loader import generate_slots


class SchedulingError(Exception):
    pass


def _team_conflicts(slot: TimeSlot, team: Team, assignments: list[Assignment], buffer_minutes: int) -> bool:
    for a in assignments:
        if team not in a.teams:
            continue
        if slot.overlaps(a.slot):
            return True
        if slot.buffer_conflict(a.slot, buffer_minutes):
            return True
    return False


def _resource_conflicts(slot: TimeSlot, resource: Resource, assignments: list[Assignment]) -> bool:
    for a in assignments:
        if a.resource == resource and slot.overlaps(a.slot):
            return True
    return False


def _to_division(entry) -> Division:
    """Convert a legacy tuple entry to a Division object if needed."""
    if isinstance(entry, Division):
        return entry
    label, teams, num_arenas = entry[0], entry[1], entry[2]
    runs_per_arena = entry[3] if len(entry) > 3 else 1
    arena_reset_minutes = entry[4] if len(entry) > 4 else 0
    return Division(label=label, teams=teams, num_arenas=num_arenas,
                    runs_per_arena=runs_per_arena, arena_reset_minutes=arena_reset_minutes)


def build_schedule(
    divisions: list,
    day_specs: list[str],
    run_time: int,
    interview_time: int,
    interview_group_size: int,
    buffer_minutes: int,
    breaks: list[Break] | None = None,
    arena_reset_minutes: int = 0,
    interview_day_specs: list[str] | None = None,
    num_interview_rooms: int = 1,
) -> Schedule:
    """
    divisions: list of Division objects (or legacy tuples for backward compat).
    Each division gets its own namespaced arena resources and independent run schedule.
    All divisions share interview resources (one or more, per num_interview_rooms).
    arena_reset_minutes (kwarg) is a global fallback used only if legacy tuple has 4 elements.
    """
    divisions = [_to_division(e) for e in divisions]
    breaks = breaks or []
    global_breaks = [b for b in breaks if b.division is None]

    global_run_slots = generate_slots(day_specs, run_time)
    interview_specs = interview_day_specs if interview_day_specs is not None else day_specs
    all_interview_slots = generate_slots(interview_specs, interview_time)

    # Filter interview slots against global breaks only
    interview_slots = [
        s for s in all_interview_slots
        if not any(b.blocks_slot(s) for b in global_breaks)
    ]

    if num_interview_rooms == 1:
        interview_resources = [Resource("interview", "Interview")]
    else:
        interview_resources = [Resource("interview", f"Interview {i+1}") for i in range(num_interview_rooms)]

    assignments: list[Assignment] = []

    # Map day label → 0-based index so cross-day reset comparisons are monotonic
    day_index: dict[str, int] = {}
    for i, spec in enumerate(day_specs):
        label = spec.split(":")[0]
        day_index[label] = i

    _reset_base = date(2000, 1, 1)

    def _slot_end_dt(slot: TimeSlot) -> datetime:
        return datetime.combine(_reset_base + timedelta(days=day_index[slot.day]), slot.end)

    def _slot_start_dt(slot: TimeSlot) -> datetime:
        return datetime.combine(_reset_base + timedelta(days=day_index[slot.day]), slot.start)

    # Track interview chunk indices already placed in Phase 1 (simplified mode)
    # div_label -> set of chunk indices placed
    div_phase1_placed: dict[str, set[int]] = {}

    # Phase 1 — Arena runs per division (prioritize filling each timeslot across all arenas)
    for div in divisions:
        div_label, teams, num_arenas, runs_per_arena = div.label, div.teams, div.num_arenas, div.runs_per_arena
        div_arena_reset = div.arena_reset_minutes
        div_breaks = global_breaks + [b for b in breaks if b.division == div_label]
        div_run_slots_all = generate_slots(div.day_specs, run_time) if div.day_specs is not None else global_run_slots
        run_slots = [
            s for s in div_run_slots_all
            if not any(b.blocks_slot(s) for b in div_breaks)
        ]
        arenas = [Resource("arena", f"{div_label} – Arena {i+1}") for i in range(num_arenas)]
        num_teams = len(teams)
        team_runs = {team: 0 for team in teams}
        total_runs_per_team = num_arenas * runs_per_arena

        if num_arenas == 1 and div_arena_reset > 0:
            # Simplified path: schedule round-by-round, back-to-back within each round
            arena = arenas[0]
            slot_cursor = 0
            last_assigned_slot = None
            round_first_slots: list = []
            round_last_slots: list = []
            team_day_runs_s: dict = defaultdict(lambda: defaultdict(int))

            for round_num in range(runs_per_arena):
                if round_num > 0:
                    last_end = _slot_end_dt(last_assigned_slot)
                    required_start = last_end + timedelta(minutes=div_arena_reset)
                    while slot_cursor < len(run_slots) and _slot_start_dt(run_slots[slot_cursor]) < required_start:
                        slot_cursor += 1

                round_first_slot = None
                for team in teams:
                    scheduled = False
                    while slot_cursor < len(run_slots):
                        slot = run_slots[slot_cursor]
                        slot_cursor += 1
                        if _resource_conflicts(slot, arena, assignments):
                            continue
                        if _team_conflicts(slot, team, assignments, buffer_minutes):
                            continue
                        if div.day_run_limits:
                            day_limit = div.day_run_limits.get(slot.day)
                            if day_limit is not None and team_day_runs_s[team][slot.day] >= day_limit:
                                continue
                        assignments.append(Assignment(slot, arena, [team]))
                        team_day_runs_s[team][slot.day] += 1
                        team_runs[team] += 1
                        last_assigned_slot = slot
                        if round_first_slot is None:
                            round_first_slot = slot
                        scheduled = True
                        break
                    if not scheduled:
                        raise SchedulingError(
                            f"No valid run slot found for team '{team.name}' in division '{div_label}' round {round_num + 1}. "
                            "Try extending the day or reducing teams/arenas."
                        )
                round_first_slots.append(round_first_slot)
                round_last_slots.append(last_assigned_slot)

            # Try to schedule interviews in the reset gaps between rounds
            if not div.no_interviews:
                chunks = [
                    teams[i:i + interview_group_size]
                    for i in range(0, len(teams), interview_group_size)
                ]
                placed_chunks: set[int] = set()
                div_phase1_placed[div_label] = placed_chunks

                for gap_idx in range(runs_per_arena - 1):
                    gap_start = _slot_end_dt(round_last_slots[gap_idx])
                    gap_end = _slot_start_dt(round_first_slots[gap_idx + 1])
                    gap_slots = [
                        s for s in interview_slots
                        if _slot_start_dt(s) >= gap_start and _slot_end_dt(s) <= gap_end
                    ]
                    for chunk_idx, chunk in enumerate(chunks):
                        if chunk_idx in placed_chunks:
                            continue
                        for slot in gap_slots:
                            if any(_team_conflicts(slot, t, assignments, buffer_minutes) for t in chunk):
                                continue
                            for ir in interview_resources:
                                if _resource_conflicts(slot, ir, assignments):
                                    continue
                                assignments.append(Assignment(slot, ir, list(chunk)))
                                placed_chunks.add(chunk_idx)
                                break
                            if chunk_idx in placed_chunks:
                                break
        else:
            # General path: fill each timeslot across all arenas
            team_day_runs = defaultdict(lambda: defaultdict(int))  # team -> day -> count
            team_arena_runs = {(team, arena): 0 for team in teams for arena in arenas}
            last_slot_for_arena = {arena: None for arena in arenas}
            arena_run_count = {arena: 0 for arena in arenas}
            # Build a list of all (team, arena) pairs that need to be scheduled, each repeated runs_per_arena times
            required_pairs = []
            for team in teams:
                for arena in arenas:
                    required_pairs.extend([(team, arena)] * runs_per_arena)
            # Assign by timeslot: for each slot, try to fill all arenas with a team that still needs a run on that arena
            for slot in run_slots:
                used_teams = set()
                for arena in arenas:
                    # Arena reset: skip if not enough time since last run on this arena
                    if last_slot_for_arena[arena] is not None and div_arena_reset > 0:
                        prev_slot = last_slot_for_arena[arena]
                        prev_end = _slot_end_dt(prev_slot)
                        curr_start = _slot_start_dt(slot)
                        if curr_start < prev_end + timedelta(minutes=div_arena_reset):
                            continue
                    if _resource_conflicts(slot, arena, assignments):
                        continue
                    # Collect all valid candidates for this (slot, arena)
                    candidates = []
                    for i, (team, candidate_arena) in enumerate(required_pairs):
                        if candidate_arena != arena:
                            continue
                        if team in used_teams:
                            continue
                        if team_arena_runs[(team, arena)] >= runs_per_arena:
                            continue
                        if team_runs[team] >= total_runs_per_team:
                            continue
                        if div.day_run_limits:
                            day_limit = div.day_run_limits.get(slot.day)
                            if day_limit is not None and team_day_runs[team][slot.day] >= day_limit:
                                continue
                        if _team_conflicts(slot, team, assignments, buffer_minutes):
                            continue
                        candidates.append((i, team))
                    if not candidates:
                        continue
                    # Pick best candidate: fewest runs on this day → fewest total runs → original order
                    best_idx, best_team = min(
                        candidates,
                        key=lambda x: (team_day_runs[x[1]][slot.day], team_runs[x[1]], x[0])
                    )
                    assignments.append(Assignment(slot, arena, [best_team]))
                    team_arena_runs[(best_team, arena)] += 1
                    team_runs[best_team] += 1
                    team_day_runs[best_team][slot.day] += 1
                    arena_run_count[arena] += 1
                    if arena_run_count[arena] % num_teams == 0:
                        last_slot_for_arena[arena] = slot
                    used_teams.add(best_team)
                    required_pairs.pop(best_idx)
                if not required_pairs:
                    break

        # After scheduling, check if all teams have the required number of runs
        for team in teams:
            if team_runs[team] != total_runs_per_team:
                raise SchedulingError(
                    f"Team '{team.name}' in division '{div_label}' was assigned {team_runs[team]} runs, expected {total_runs_per_team}. "
                    "Try extending the day or reducing teams/arenas."
                )

        if div.day_run_limits:
            for day_lbl, limit in div.day_run_limits.items():
                for team in teams:
                    actual = sum(
                        1 for a in assignments
                        if a.slot.day == day_lbl
                        and a.resource.kind == "arena"
                        and a.resource.name.startswith(div_label)
                        and team in a.teams
                    )
                    if actual != limit:
                        raise SchedulingError(
                            f"Team '{team.name}' in '{div_label}' has {actual} runs on {day_lbl}, "
                            f"expected {limit}. Try adjusting day timeframes or constraints."
                        )

    # Phase 2 — Interviews grouped by division (shared interview resources)
    # Chunks already placed in Phase 1 (simplified mode) are skipped here.
    for div in divisions:
        if div.no_interviews:
            continue
        div_label, teams = div.label, div.teams
        chunks = [
            teams[i:i + interview_group_size]
            for i in range(0, len(teams), interview_group_size)
        ]
        phase1_placed = div_phase1_placed.get(div_label, set())
        cursor = 0
        for chunk_idx, chunk in enumerate(chunks):
            if chunk_idx in phase1_placed:
                continue
            found = False
            for i in range(cursor, len(interview_slots)):
                slot = interview_slots[i]
                if any(_team_conflicts(slot, t, assignments, buffer_minutes) for t in chunk):
                    continue
                for ir in interview_resources:
                    if _resource_conflicts(slot, ir, assignments):
                        continue
                    assignments.append(Assignment(slot, ir, list(chunk)))
                    if all(_resource_conflicts(slot, r, assignments) for r in interview_resources):
                        cursor = i + 1
                    found = True
                    break
                if found:
                    break
            if not found:
                raise SchedulingError(
                    f"No valid interview slot found for division '{div_label}' group {[t.name for t in chunk]}. "
                    "Try extending the day or adjusting parameters."
                )

    meta = {
        "divisions": {
            div.label: {
                "arenas": div.num_arenas,
                "runs_per_arena": div.runs_per_arena,
                "arena_reset_minutes": div.arena_reset_minutes,
            }
            for div in divisions
        },
        "run_time_minutes": run_time,
        "interview_time_minutes": interview_time,
        "interview_group_size": interview_group_size,
        "buffer_minutes": buffer_minutes,
        "days": day_specs,
        "interview_days": interview_specs,
        "interview_rooms": num_interview_rooms,
        "breaks": [
            {"day": b.day, "start": b.start.strftime("%H:%M"), "end": b.end.strftime("%H:%M"),
             "division": b.division}
            for b in breaks
        ],
    }
    return Schedule(assignments=assignments, meta=meta)


def validate_schedule(schedule: Schedule) -> list[str]:
    """Return list of violation messages (empty = valid)."""
    violations = []
    assignments = schedule.assignments
    meta = schedule.meta
    buffer = meta.get("buffer_minutes", 0)

    # Check resource double-booking
    for i, a in enumerate(assignments):
        for b in assignments[i+1:]:
            if a.resource == b.resource and a.slot.overlaps(b.slot):
                violations.append(
                    f"Resource '{a.resource.name}' double-booked at {a.slot} and {b.slot}"
                )

    # Check team overlap/buffer
    all_teams = {t for a in assignments for t in a.teams}
    for team in all_teams:
        team_assignments = [a for a in assignments if team in a.teams]
        for i, a in enumerate(team_assignments):
            for b in team_assignments[i+1:]:
                if a.slot.overlaps(b.slot):
                    violations.append(f"Team '{team.name}' has overlapping slots: {a.slot} and {b.slot}")
                elif a.slot.buffer_conflict(b.slot, buffer):
                    violations.append(
                        f"Team '{team.name}' has insufficient buffer between {a.slot} and {b.slot}"
                    )

    return violations
