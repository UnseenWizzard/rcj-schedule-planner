from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, timedelta
from rcj_planner.models import Team, TimeSlot, Resource, Assignment, Schedule, Break
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


def build_schedule(
    divisions: list[tuple[str, list[Team], int, int]],
    day_specs: list[str],
    run_time: int,
    interview_time: int,
    interview_group_size: int,
    buffer_minutes: int,
    breaks: list[Break] | None = None,
    arena_reset_minutes: int = 0,
) -> Schedule:
    """
    divisions: list of (division_label, teams, num_arenas, runs_per_arena)
    Each division gets its own namespaced arena resources and independent run schedule.
    All divisions share a single Interview resource.
    """
    breaks = breaks or []
    global_breaks = [b for b in breaks if b.division is None]

    all_run_slots = generate_slots(day_specs, run_time)
    all_interview_slots = generate_slots(day_specs, interview_time)

    # Filter interview slots against global breaks only
    interview_slots = [
        s for s in all_interview_slots
        if not any(b.blocks_slot(s) for b in global_breaks)
    ]

    interview_resource = Resource("interview", "Interview")

    assignments: list[Assignment] = []

    # Phase 1 — Arena runs per division (greedy round-robin, namespaced arenas)
    for div_label, teams, num_arenas, runs_per_arena in divisions:
        div_breaks = global_breaks + [b for b in breaks if b.division == div_label]
        run_slots = [
            s for s in all_run_slots
            if not any(b.blocks_slot(s) for b in div_breaks)
        ]
        arenas = [Resource("arena", f"{div_label} – Arena {i+1}") for i in range(num_arenas)]
        for arena in arenas:
            cursor = 0
            for _ in range(runs_per_arena):
                assignments_before = len(assignments)
                for team in teams:
                    found = False
                    for i in range(cursor, len(run_slots)):
                        slot = run_slots[i]
                        if _resource_conflicts(slot, arena, assignments):
                            continue
                        if _team_conflicts(slot, team, assignments, buffer_minutes):
                            continue
                        assignments.append(Assignment(slot, arena, [team]))
                        cursor = i + 1
                        found = True
                        break
                    if not found:
                        raise SchedulingError(
                            f"No valid run slot found for team '{team.name}' on arena '{arena.name}'. "
                            "Try extending the day or reducing teams/arenas."
                        )

                # Advance cursor past the post-round reset window
                if arena_reset_minutes > 0:
                    round_slots = [a.slot for a in assignments[assignments_before:] if a.resource == arena]
                    last_slot = max(round_slots, key=lambda s: s.end)
                    cutoff = (
                        datetime.combine(date.today(), last_slot.end)
                        + timedelta(minutes=arena_reset_minutes)
                    ).time()
                    while cursor < len(run_slots) and (
                        run_slots[cursor].day == last_slot.day
                        and run_slots[cursor].start < cutoff
                    ):
                        cursor += 1

    # Phase 2 — Interviews grouped by division (shared interview resource)
    for div_label, teams, _, _runs in divisions:
        chunks = [
            teams[i:i + interview_group_size]
            for i in range(0, len(teams), interview_group_size)
        ]
        cursor = 0
        for chunk in chunks:
            found = False
            for i in range(cursor, len(interview_slots)):
                slot = interview_slots[i]
                if _resource_conflicts(slot, interview_resource, assignments):
                    continue
                if any(_team_conflicts(slot, t, assignments, buffer_minutes) for t in chunk):
                    continue
                assignments.append(Assignment(slot, interview_resource, list(chunk)))
                cursor = i + 1
                found = True
                break
            if not found:
                raise SchedulingError(
                    f"No valid interview slot found for division '{div_label}' group {[t.name for t in chunk]}. "
                    "Try extending the day or adjusting parameters."
                )

    meta = {
        "divisions": {label: {"arenas": num_arenas, "runs_per_arena": runs} for label, _, num_arenas, runs in divisions},
        "run_time_minutes": run_time,
        "interview_time_minutes": interview_time,
        "interview_group_size": interview_group_size,
        "buffer_minutes": buffer_minutes,
        "arena_reset_minutes": arena_reset_minutes,
        "days": day_specs,
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
