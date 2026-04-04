import os, tempfile
from datetime import time
from rcj_planner.loader import load_teams, parse_day_spec, generate_slots, parse_division_spec, parse_break_spec


def test_parse_day_spec():
    label, start, end = parse_day_spec("Day1:09:00-17:00")
    assert label == "Day1"
    assert start == time(9, 0)
    assert end == time(17, 0)


def test_generate_slots_count():
    slots = generate_slots(["Day1:09:00-09:30"], 10)
    assert len(slots) == 3
    assert slots[0].start == time(9, 0)
    assert slots[0].end == time(9, 10)
    assert slots[2].end == time(9, 30)


def test_generate_slots_multi_day():
    slots = generate_slots(["Day1:09:00-09:20", "Day2:10:00-10:20"], 10)
    assert len(slots) == 4
    assert slots[0].day == "Day1"
    assert slots[2].day == "Day2"


def test_load_teams(tmp_path):
    csv_file = tmp_path / "teams.csv"
    csv_file.write_text("team_name,division\nAlpha,Soccer\nBeta,Rescue\n")
    teams = load_teams(str(csv_file))
    assert len(teams) == 2
    assert teams[0].name == "Alpha"
    assert teams[0].division == "Soccer"
    assert teams[1].name == "Beta"


def test_load_teams_division_override(tmp_path):
    csv_file = tmp_path / "teams.csv"
    csv_file.write_text("team_name\nAlpha\nBeta\n")
    teams = load_teams(str(csv_file), division="Soccer Open")
    assert all(t.division == "Soccer Open" for t in teams)


def test_parse_division_spec():
    label, path, num_arenas, runs_per_arena, arena_reset = parse_division_spec("Soccer Open:soccer.csv:arenas=3")
    assert label == "Soccer Open"
    assert path == "soccer.csv"
    assert num_arenas == 3
    assert runs_per_arena == 1
    assert arena_reset == 0


def test_parse_division_spec_with_runs():
    label, path, num_arenas, runs_per_arena, arena_reset = parse_division_spec("Line:Line.csv:arenas=2:runs=3")
    assert label == "Line"
    assert num_arenas == 2
    assert runs_per_arena == 3
    assert arena_reset == 0


def test_parse_division_spec_with_arena_reset():
    label, path, num_arenas, runs_per_arena, arena_reset = parse_division_spec("Maze:maze.csv:arenas=2:runs=3:arena_reset=15")
    assert label == "Maze"
    assert num_arenas == 2
    assert runs_per_arena == 3
    assert arena_reset == 15


def test_parse_division_spec_invalid():
    import pytest
    with pytest.raises(ValueError):
        parse_division_spec("Soccer Open:soccer.csv")
    with pytest.raises(ValueError):
        parse_division_spec("Soccer Open:soccer.csv:3")
    with pytest.raises(ValueError):
        parse_division_spec("Soccer Open:soccer.csv:arenas=2:badpart")


def test_parse_break_spec_global():
    from datetime import time
    b = parse_break_spec("Day1:12:00-13:00")
    assert b.day == "Day1"
    assert b.start == time(12, 0)
    assert b.end == time(13, 0)
    assert b.division is None


def test_parse_break_spec_division():
    from datetime import time
    b = parse_break_spec("Day1:Line:12:00-13:00")
    assert b.day == "Day1"
    assert b.division == "Line"
    assert b.start == time(12, 0)
    assert b.end == time(13, 0)


def test_parse_break_spec_invalid():
    import pytest
    with pytest.raises((ValueError, Exception)):
        parse_break_spec("Day1:badtime")
