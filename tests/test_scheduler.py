import pytest
from datetime import datetime, date, time
from rcj_planner.models import Team, Break
from rcj_planner.scheduler import build_schedule, validate_schedule, SchedulingError

DAYS = ["Day1:09:00-17:00"]


def make_divisions(num_teams=4, num_arenas=2, division="DivA", runs_per_arena=1):
    teams = [Team(f"Team{i}", division) for i in range(num_teams)]
    return [(division, teams, num_arenas, runs_per_arena)]


def test_basic_schedule():
    divisions = make_divisions()
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    teams = divisions[0][1]
    for team in teams:
        arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
        assert len(arena_runs) == 2

    for team in teams:
        interviews = [a for a in s.assignments_for_team(team) if a.resource.kind == "interview"]
        assert len(interviews) == 1


def test_no_violations():
    s = build_schedule(make_divisions(), DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []


def test_scheduling_error_too_tight():
    many_teams = [Team(f"T{i}", "X") for i in range(50)]
    with pytest.raises(SchedulingError):
        build_schedule([("X", many_teams, 1, 1)], ["Day1:09:00-09:30"],
                       run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)


def test_runs_per_arena():
    divisions = make_divisions(num_teams=3, num_arenas=2, runs_per_arena=2)
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    teams = divisions[0][1]
    for team in teams:
        arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
        assert len(arena_runs) == 4  # 2 arenas × 2 runs


def test_multi_division():
    divisions = [
        ("Soccer", [Team("A", "Soccer"), Team("B", "Soccer")], 2, 1),
        ("Rescue", [Team("C", "Rescue"), Team("D", "Rescue")], 1, 1),
    ]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []


def test_arena_resources_namespaced():
    divisions = [
        ("Soccer", [Team("A", "Soccer"), Team("B", "Soccer")], 2, 1),
        ("Rescue", [Team("C", "Rescue"), Team("D", "Rescue")], 2, 1),
    ]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    arena_names = {a.resource.name for a in s.assignments if a.resource.kind == "arena"}
    soccer_arenas = {n for n in arena_names if "Soccer" in n}
    rescue_arenas = {n for n in arena_names if "Rescue" in n}
    # No overlap between division arena names
    assert soccer_arenas.isdisjoint(rescue_arenas)
    assert len(soccer_arenas) == 2
    assert len(rescue_arenas) == 2


def test_arena_reset_between_rounds():
    """After each round (all 3 teams run once on the arena), a 30-min gap must follow."""
    divisions = make_divisions(num_teams=3, num_arenas=1, runs_per_arena=3)
    s = build_schedule(
        divisions, ["Day1:09:00-17:00"],
        run_time=10, interview_time=20, interview_group_size=3,
        buffer_minutes=10, arena_reset_minutes=30,
    )
    assert validate_schedule(s) == []
    arena_runs = sorted(
        [a for a in s.assignments if a.resource.kind == "arena"],
        key=lambda a: a.slot.start,
    )
    assert len(arena_runs) == 9  # 3 teams × 3 rounds

    round_size = 3
    for r in range(2):  # gap after round 0 and round 1 (round 2 has no round after it)
        end_of_round = arena_runs[(r + 1) * round_size - 1].slot.end
        start_of_next = arena_runs[(r + 1) * round_size].slot.start
        gap = (datetime.combine(date.today(), start_of_next)
               - datetime.combine(date.today(), end_of_round)).seconds // 60
        assert gap >= 30, f"Round {r} reset gap is only {gap} min"


def test_global_break_blocks_all():
    """No assignment should fall within a global break window."""
    breaks = [Break(day="Day1", start=time(9, 30), end=time(10, 0))]
    divisions = make_divisions(num_teams=4, num_arenas=2)
    s = build_schedule(divisions, ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10, breaks=breaks)
    assert validate_schedule(s) == []
    for a in s.assignments:
        # No assignment should overlap the break window
        assert not (a.slot.start < time(10, 0) and a.slot.end > time(9, 30)), \
            f"Assignment at {a.slot.start}-{a.slot.end} overlaps break"


def test_division_break_blocks_only_that_division():
    """A division-specific break blocks runs for that division but not others."""
    divisions = [
        ("Soccer", [Team("A", "Soccer"), Team("B", "Soccer")], 1, 1),
        ("Rescue", [Team("C", "Rescue"), Team("D", "Rescue")], 1, 1),
    ]
    breaks = [Break(day="Day1", start=time(9, 0), end=time(9, 30), division="Soccer")]
    s = build_schedule(divisions, ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10, breaks=breaks)
    assert validate_schedule(s) == []
    for a in s.assignments:
        if a.resource.kind == "arena" and "Soccer" in a.resource.name:
            assert not (a.slot.start < time(9, 30) and a.slot.end > time(9, 0)), \
                f"Soccer arena assignment at {a.slot.start}-{a.slot.end} overlaps Soccer-only break"


def test_interview_resource_shared():
    divisions = [
        ("Soccer", [Team("A", "Soccer"), Team("B", "Soccer")], 1, 1),
        ("Rescue", [Team("C", "Rescue"), Team("D", "Rescue")], 1, 1),
    ]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    interview_resources = {a.resource.name for a in s.assignments if a.resource.kind == "interview"}
    assert interview_resources == {"Interview"}
