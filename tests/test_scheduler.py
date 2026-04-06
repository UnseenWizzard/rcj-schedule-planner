import pytest
from datetime import datetime, date, time
from rcj_planner.models import Team, Break, Division
from rcj_planner.scheduler import build_schedule, validate_schedule, SchedulingError

DAYS = ["Day1:09:00-17:00"]


def make_divisions(num_teams=4, num_arenas=2, division="DivA", runs_per_arena=1, arena_reset=0, no_interviews=False):
    teams = [Team(f"Team{i}", division) for i in range(num_teams)]
    return [Division(label=division, teams=teams, num_arenas=num_arenas,
                     runs_per_arena=runs_per_arena, arena_reset_minutes=arena_reset,
                     no_interviews=no_interviews)]


def test_basic_schedule():
    divisions = make_divisions()
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    teams = divisions[0].teams
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
    teams = divisions[0].teams
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


def test_interview_day_specs_restricts_window():
    """Interviews should only be scheduled within the interview_day_specs window."""
    from datetime import time as dtime
    divisions = make_divisions(num_teams=4, num_arenas=2)
    interview_day_specs = ["Day1:14:00-17:00"]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10,
                       interview_day_specs=interview_day_specs)
    assert validate_schedule(s) == []
    for a in s.assignments:
        if a.resource.kind == "interview":
            assert a.slot.start >= dtime(14, 0), (
                f"Interview at {a.slot.start} is outside the interview window 14:00-17:00"
            )


def test_interview_day_specs_none_uses_day_specs():
    """Omitting interview_day_specs should preserve current behavior (interviews use run day specs)."""
    divisions = make_divisions(num_teams=4, num_arenas=2)
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10,
                       interview_day_specs=None)
    assert validate_schedule(s) == []
    assert s.meta["interview_days"] == DAYS
    interviews = [a for a in s.assignments if a.resource.kind == "interview"]
    assert len(interviews) == 2  # 4 teams / group_size 2


def test_num_interview_rooms_1_single_resource():
    """With num_interview_rooms=1, only one 'Interview' resource should exist."""
    divisions = make_divisions(num_teams=4, num_arenas=2)
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10,
                       num_interview_rooms=1)
    interview_resources = {a.resource.name for a in s.assignments if a.resource.kind == "interview"}
    assert interview_resources == {"Interview"}


def test_num_interview_rooms_2_parallel_groups():
    """With num_interview_rooms=2, two groups can be interviewed at the same time."""
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    divisions = [Division(label="DivA", teams=teams, num_arenas=2, runs_per_arena=1, arena_reset_minutes=0)]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=1, buffer_minutes=10,
                       num_interview_rooms=2)
    assert validate_schedule(s) == []
    interview_resources = {a.resource.name for a in s.assignments if a.resource.kind == "interview"}
    assert "Interview 1" in interview_resources
    assert "Interview 2" in interview_resources
    # Verify that two interviews are scheduled at the same time (parallelism)
    interview_assignments = [a for a in s.assignments if a.resource.kind == "interview"]
    start_times = [a.slot.start for a in interview_assignments]
    assert len(start_times) > len(set(start_times)), "Expected parallel interviews at same time slot"


def test_no_interviews_division_gets_no_interviews():
    """A division with no_interviews=True should have zero interview assignments."""
    divisions = make_divisions(num_teams=4, num_arenas=2, division="Soccer", no_interviews=True)
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    teams = divisions[0].teams
    for team in teams:
        interviews = [a for a in s.assignments_for_team(team) if a.resource.kind == "interview"]
        assert len(interviews) == 0, f"Expected no interviews for {team.name}, got {len(interviews)}"


def test_no_interviews_does_not_affect_other_divisions():
    """no_interviews only skips that division; other divisions still get interviews."""
    soccer_teams = [Team(f"S{i}", "Soccer") for i in range(4)]
    rescue_teams = [Team(f"R{i}", "Rescue") for i in range(4)]
    divisions = [
        Division(label="Soccer", teams=soccer_teams, num_arenas=2, no_interviews=True),
        Division(label="Rescue", teams=rescue_teams, num_arenas=2),
    ]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for team in soccer_teams:
        interviews = [a for a in s.assignments_for_team(team) if a.resource.kind == "interview"]
        assert len(interviews) == 0, f"Soccer team {team.name} should have no interviews"
    for team in rescue_teams:
        interviews = [a for a in s.assignments_for_team(team) if a.resource.kind == "interview"]
        assert len(interviews) == 1, f"Rescue team {team.name} should have 1 interview"


def test_no_interviews_with_arena_reset_gap_path():
    """Single arena, runs_per_arena=2, arena_reset=30, no_interviews=True: no interview assignments."""
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    divisions = [Division(label="DivA", teams=teams, num_arenas=1, runs_per_arena=2,
                          arena_reset_minutes=30, no_interviews=True)]
    s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    interview_assignments = [a for a in s.assignments if a.resource.kind == "interview"]
    assert len(interview_assignments) == 0, "Expected no interviews when no_interviews=True"


def test_per_division_day_restricts_run_slots():
    """Division with day_specs=["Day1:09:00-10:00"] should have all arena runs end by 10:00."""
    from datetime import time as dtime
    teams = [Team(f"Team{i}", "Maze") for i in range(4)]
    div = Division(label="Maze", teams=teams, num_arenas=2,
                   day_specs=["Day1:09:00-10:00"])
    s = build_schedule([div], ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for a in s.assignments:
        if a.resource.kind == "arena" and "Maze" in a.resource.name:
            assert a.slot.end <= dtime(10, 0), (
                f"Maze arena slot ends at {a.slot.end}, expected <= 10:00"
            )


def test_per_division_day_other_division_uses_global():
    """Division with day_specs=None uses global day_specs and gets slots throughout full window."""
    from datetime import time as dtime
    maze_teams = [Team(f"M{i}", "Maze") for i in range(4)]
    line_teams = [Team(f"L{i}", "Line") for i in range(4)]
    maze_div = Division(label="Maze", teams=maze_teams, num_arenas=2,
                        day_specs=["Day1:09:00-10:00"])
    line_div = Division(label="Line", teams=line_teams, num_arenas=2,
                        day_specs=None)
    s = build_schedule([maze_div, line_div], ["Day1:09:00-17:00"],
                       run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    # Line has 4 teams × 2 arenas × 1 run = 8 arena assignments
    line_arena_assignments = [a for a in s.assignments
                              if a.resource.kind == "arena" and "Line" in a.resource.name]
    assert len(line_arena_assignments) == 8, (
        f"Expected 8 Line arena assignments (4 teams × 2 arenas), got {len(line_arena_assignments)}"
    )


def test_per_division_day_none_uses_global():
    """Division with day_specs=None behaves same as providing the global day specs explicitly."""
    teams = [Team(f"Team{i}", "DivA") for i in range(4)]
    div_none = Division(label="DivA", teams=teams, num_arenas=2, day_specs=None)
    div_explicit = Division(label="DivA", teams=teams, num_arenas=2, day_specs=["Day1:09:00-17:00"])
    global_days = ["Day1:09:00-17:00"]
    s_none = build_schedule([div_none], global_days, run_time=10, interview_time=20,
                            interview_group_size=2, buffer_minutes=10)
    s_explicit = build_schedule([div_explicit], global_days, run_time=10, interview_time=20,
                                interview_group_size=2, buffer_minutes=10)
    slots_none = sorted({(a.slot.start, a.slot.end) for a in s_none.assignments if a.resource.kind == "arena"})
    slots_explicit = sorted({(a.slot.start, a.slot.end) for a in s_explicit.assignments if a.resource.kind == "arena"})
    assert slots_none == slots_explicit


DAYS_2 = ["Day1:09:00-17:00", "Day2:09:00-17:00"]


def test_day_run_limits_two_day_schedule():
    """day_run_limits={"Day1": 2} with runs_per_arena=3 should give 2 runs on Day1 and 1 on Day2."""
    teams = [Team(f"Team{i}", "Maze") for i in range(4)]
    divisions = [Division(label="Maze", teams=teams, num_arenas=1, runs_per_arena=3,
                          day_run_limits={"Day1": 2})]
    s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for team in teams:
        day1_runs = [a for a in s.assignments_for_team(team)
                     if a.resource.kind == "arena" and a.slot.day == "Day1"]
        day2_runs = [a for a in s.assignments_for_team(team)
                     if a.resource.kind == "arena" and a.slot.day == "Day2"]
        assert len(day1_runs) == 2, f"{team.name}: expected 2 Day1 runs, got {len(day1_runs)}"
        assert len(day2_runs) == 1, f"{team.name}: expected 1 Day2 run, got {len(day2_runs)}"


def test_day_run_limits_zero_on_day():
    """day_run_limits={"Day1": 0} forces all runs to Day2."""
    teams = [Team(f"Team{i}", "Maze") for i in range(4)]
    divisions = [Division(label="Maze", teams=teams, num_arenas=1, runs_per_arena=2,
                          day_run_limits={"Day1": 0})]
    s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for team in teams:
        day1_runs = [a for a in s.assignments_for_team(team)
                     if a.resource.kind == "arena" and a.slot.day == "Day1"]
        assert len(day1_runs) == 0, f"{team.name}: expected 0 Day1 runs, got {len(day1_runs)}"


def test_day_run_limits_multi_division_independent():
    """Two divisions with different day_run_limits are each enforced independently."""
    maze_teams = [Team(f"M{i}", "Maze") for i in range(4)]
    rescue_teams = [Team(f"R{i}", "Rescue") for i in range(4)]
    divisions = [
        Division(label="Maze", teams=maze_teams, num_arenas=1, runs_per_arena=3,
                 day_run_limits={"Day1": 2}),
        Division(label="Rescue", teams=rescue_teams, num_arenas=1, runs_per_arena=3,
                 day_run_limits={"Day1": 1}),
    ]
    s = build_schedule(divisions, DAYS_2, run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
    assert validate_schedule(s) == []
    for team in maze_teams:
        day1 = [a for a in s.assignments_for_team(team)
                if a.resource.kind == "arena" and a.slot.day == "Day1"]
        assert len(day1) == 2, f"Maze {team.name}: expected 2 Day1 runs, got {len(day1)}"
    for team in rescue_teams:
        day1 = [a for a in s.assignments_for_team(team)
                if a.resource.kind == "arena" and a.slot.day == "Day1"]
        assert len(day1) == 1, f"Rescue {team.name}: expected 1 Day1 run, got {len(day1)}"


def test_day_run_limits_impossible_raises():
    """day_run_limits={"Day1": 0} with single-day schedule and runs_per_arena=2 should raise."""
    teams = [Team(f"Team{i}", "Maze") for i in range(4)]
    divisions = [Division(label="Maze", teams=teams, num_arenas=1, runs_per_arena=2,
                          day_run_limits={"Day1": 0})]
    with pytest.raises(SchedulingError):
        build_schedule(divisions, ["Day1:09:00-17:00"], run_time=10, interview_time=20,
                       interview_group_size=2, buffer_minutes=10)
