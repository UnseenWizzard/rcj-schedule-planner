import pytest
from datetime import datetime, date, time
from rcj_planner.models import Team, Break
from rcj_planner.scheduler import build_schedule, validate_schedule, SchedulingError

DAYS = ["Day1:09:00-17:00"]


def make_divisions(num_teams=4, num_arenas=2, division="DivA", runs_per_arena=1, arena_reset=0):
    teams = [Team(f"Team{i}", division) for i in range(num_teams)]
    return [(division, teams, num_arenas, runs_per_arena, arena_reset)]


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
    """After each complete round (all 3 teams run once on the arena), a 30-min gap must
    follow. Within a round, consecutive runs are separated only by run_time — no reset gap."""
    divisions = make_divisions(num_teams=3, num_arenas=1, runs_per_arena=3, arena_reset=30)
    s = build_schedule(
        divisions, ["Day1:09:00-17:00"],
        run_time=10, interview_time=20, interview_group_size=3,
        buffer_minutes=10,
    )
    assert validate_schedule(s) == []
    arena_runs = sorted(
        [a for a in s.assignments if a.resource.kind == "arena"],
        key=lambda a: a.slot.start,
    )
    assert len(arena_runs) == 9  # 3 teams × 3 rounds

    round_size = 3
    # Within each round: consecutive runs must NOT have a reset gap (gap == run_time == 10)
    for r in range(3):
        for i in range(round_size - 1):
            idx = r * round_size + i
            end_of_run = arena_runs[idx].slot.end
            start_of_next_run = arena_runs[idx + 1].slot.start
            intra_gap = (datetime.combine(date.today(), start_of_next_run)
                         - datetime.combine(date.today(), end_of_run)).seconds // 60
            assert intra_gap < 30, (
                f"Round {r}, run {i}: unexpected reset gap of {intra_gap} min within a round"
            )

    # Between rounds: gap after the last slot of a round must be >= arena_reset (30 min)
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


def test_single_day_unaffected():
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    divisions = [("DivA", teams, 2, 1)]
    s = build_schedule(divisions, ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for team in teams:
        arena_runs = [a for a in s.assignments_for_team(team) if a.resource.kind == "arena"]
        assert len(arena_runs) == 2


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


def test_arena_reset_all_rounds_should_work_scenario():
    """Mirrors the should_work.sh scenario: 4 teams, 1 arena, 4 runs, arena_reset=60,
    2 days with a lunch break. Verifies reset gap between every pair of consecutive
    rounds and no reset gap within rounds."""
    from datetime import timedelta
    day_specs = ["Day1:10:30-18:00", "Day2:09:00-13:00"]
    breaks = [Break(day="Day1", start=time(12, 30), end=time(13, 30))]
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    divisions = [("DivA", teams, 1, 4, 60)]
    s = build_schedule(
        divisions, day_specs,
        run_time=10, interview_time=15, interview_group_size=2,
        buffer_minutes=10, breaks=breaks,
    )
    assert validate_schedule(s) == []

    arena_runs = sorted(
        [a for a in s.assignments if a.resource.kind == "arena"],
        key=lambda a: (day_specs.index(next(d for d in day_specs if d.startswith(a.slot.day))), a.slot.start),
    )
    assert len(arena_runs) == 16  # 4 teams × 4 rounds

    _reset_base = date(2000, 1, 1)
    day_index = {spec.split(":")[0]: i for i, spec in enumerate(day_specs)}

    def slot_start_dt(a):
        return datetime.combine(_reset_base + timedelta(days=day_index[a.slot.day]), a.slot.start)

    def slot_end_dt(a):
        return datetime.combine(_reset_base + timedelta(days=day_index[a.slot.day]), a.slot.end)

    round_size = 4
    num_rounds = 4

    def break_gap_between(end_dt, start_dt):
        """Minutes of break time that fall between two datetime instants."""
        total = 0.0
        for b in breaks:
            b_day_idx = day_index.get(b.day, -1)
            b_start = datetime.combine(_reset_base + timedelta(days=b_day_idx), b.start)
            b_end = datetime.combine(_reset_base + timedelta(days=b_day_idx), b.end)
            overlap = min(start_dt, b_end) - max(end_dt, b_start)
            if overlap.total_seconds() > 0:
                total += overlap.total_seconds() / 60
        return total

    # Within each round: gap should only come from break time, not a reset gap
    for r in range(num_rounds):
        for i in range(round_size - 1):
            idx = r * round_size + i
            end_dt = slot_end_dt(arena_runs[idx])
            start_dt = slot_start_dt(arena_runs[idx + 1])
            gap = (start_dt - end_dt).total_seconds() / 60
            max_expected = break_gap_between(end_dt, start_dt)
            assert gap <= max_expected, (
                f"Round {r}, run {i}: gap of {gap:.0f} min exceeds break time "
                f"({max_expected:.0f} min) — unexpected reset gap within a round"
            )

    # Between rounds: gap >= arena_reset (60 min)
    for r in range(num_rounds - 1):
        end_of_round = slot_end_dt(arena_runs[(r + 1) * round_size - 1])
        start_of_next = slot_start_dt(arena_runs[(r + 1) * round_size])
        gap = (start_of_next - end_of_round).total_seconds() / 60
        assert gap >= 60, f"Inter-round gap after round {r} is only {gap:.0f} min (expected >= 60)"


def test_early_day_loading_buffer_respected():
    DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    divisions = [("DivA", teams, 1, 3)]
    s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=15)
    assert validate_schedule(s) == []
