import csv, os
from click.testing import CliRunner
from rcj_planner.cli import cli

SOCCER_CSV = "team_name\nAlpha\nBeta\n"
RESCUE_CSV = "team_name\nGamma\nDelta\n"


def test_generate_validate_csv(tmp_path):
    soccer_file = tmp_path / "soccer.csv"
    soccer_file.write_text(SOCCER_CSV)
    rescue_file = tmp_path / "rescue.csv"
    rescue_file.write_text(RESCUE_CSV)
    schedule_file = tmp_path / "schedule.json"
    output_dir = tmp_path / "out"

    runner = CliRunner()

    result = runner.invoke(cli, [
        "generate",
        "--division", f"Soccer:{soccer_file}:arenas=2",
        "--division", f"Rescue:{rescue_file}:arenas=1",
        "--run-time", "10",
        "--interview-time", "20",
        "--interview-group-size", "2",
        "--day", "Day1:09:00-17:00",
        "--save", str(schedule_file),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["validate", str(schedule_file)])
    assert result.exit_code == 0, result.output
    assert "valid" in result.output

    day1_csv = output_dir / "Day1.csv"
    assert day1_csv.exists()
    with open(day1_csv) as f:
        rows = list(csv.DictReader(f))

    arena_rows = [r for r in rows if "Arena" in r["resource"]]
    interview_rows = [r for r in rows if r["resource"] == "Interview"]

    # Soccer: 2 teams × 2 arenas = 4 runs; Rescue: 2 teams × 1 arena = 2 runs
    assert len(arena_rows) == 6
    # 2 divisions × 1 group each = 2 interview slots
    assert len(interview_rows) == 2


def test_division_arenas_isolated(tmp_path):
    soccer_file = tmp_path / "soccer.csv"
    soccer_file.write_text(SOCCER_CSV)
    rescue_file = tmp_path / "rescue.csv"
    rescue_file.write_text(RESCUE_CSV)
    schedule_file = tmp_path / "schedule.json"
    output_dir = tmp_path / "out"

    runner = CliRunner()
    runner.invoke(cli, [
        "generate",
        "--division", f"Soccer:{soccer_file}:arenas=1",
        "--division", f"Rescue:{rescue_file}:arenas=1",
        "--run-time", "10",
        "--interview-time", "20",
        "--interview-group-size", "2",
        "--day", "Day1:09:00-17:00",
        "--save", str(schedule_file),
        "--output-dir", str(output_dir),
    ])

    with open(output_dir / "Day1.csv") as f:
        rows = list(csv.DictReader(f))

    arena_names = {r["resource"] for r in rows if "Arena" in r["resource"]}
    assert any("Soccer" in n for n in arena_names)
    assert any("Rescue" in n for n in arena_names)
    # No arena serves both divisions
    soccer_teams = {"Alpha", "Beta"}
    rescue_teams = {"Gamma", "Delta"}
    for r in rows:
        if "Arena" not in r["resource"]:
            continue
        if "Soccer" in r["resource"]:
            assert r["teams"] in soccer_teams
        if "Rescue" in r["resource"]:
            assert r["teams"] in rescue_teams


def test_generate_no_interviews_flag(tmp_path):
    soccer_file = tmp_path / "soccer.csv"
    soccer_file.write_text(SOCCER_CSV)
    rescue_file = tmp_path / "rescue.csv"
    rescue_file.write_text(RESCUE_CSV)
    schedule_file = tmp_path / "schedule.json"
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "generate",
        "--division", f"Soccer:{soccer_file}:arenas=1:no_interviews",
        "--division", f"Rescue:{rescue_file}:arenas=1",
        "--run-time", "10",
        "--interview-time", "20",
        "--interview-group-size", "2",
        "--day", "Day1:09:00-17:00",
        "--save", str(schedule_file),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output

    day1_csv = output_dir / "Day1.csv"
    assert day1_csv.exists()
    with open(day1_csv) as f:
        rows = list(csv.DictReader(f))

    soccer_team_names = {"Alpha", "Beta"}
    interview_rows = [r for r in rows if r["resource"] == "Interview"]

    # No Soccer team should appear in any interview row
    for r in interview_rows:
        teams_in_row = {t.strip() for t in r["teams"].split(",")}
        assert teams_in_row.isdisjoint(soccer_team_names), (
            f"Soccer team found in interview row: {r}"
        )

    # Rescue division should still have interviews (1 group of 2)
    rescue_team_names = {"Gamma", "Delta"}
    rescue_interview_rows = [
        r for r in interview_rows
        if any(t.strip() in rescue_team_names for t in r["teams"].split(","))
    ]
    assert len(rescue_interview_rows) == 1


def test_generate_division_day_override(tmp_path):
    """--division-day restricts Maze to 09:00-10:00; Line uses full global window 09:00-17:00."""
    maze_csv = tmp_path / "maze.csv"
    maze_csv.write_text("team_name\nTeam A\nTeam B\nTeam C\nTeam D\n")
    line_csv = tmp_path / "line.csv"
    line_csv.write_text("team_name\nTeam E\nTeam F\nTeam G\nTeam H\n")
    schedule_file = tmp_path / "schedule.json"
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "generate",
        "--division", f"Maze:{maze_csv}:arenas=1",
        "--division", f"Line:{line_csv}:arenas=1",
        "--division-day", "Maze:Day1:09:00-10:00",
        "--run-time", "10",
        "--interview-time", "20",
        "--interview-group-size", "2",
        "--day", "Day1:09:00-17:00",
        "--save", str(schedule_file),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output

    from datetime import time as dtime
    day1_csv = output_dir / "Day1.csv"
    assert day1_csv.exists()
    with open(day1_csv) as f:
        rows = list(csv.DictReader(f))

    maze_arena_rows = [r for r in rows if "Maze" in r["resource"] and "Arena" in r["resource"]]
    line_arena_rows = [r for r in rows if "Line" in r["resource"] and "Arena" in r["resource"]]

    # All Maze arena runs must end at or before 10:00
    for r in maze_arena_rows:
        end_str = r["time_slot"].split("-")[1].strip()
        end_h, end_m = map(int, end_str.split(":"))
        assert dtime(end_h, end_m) <= dtime(10, 0), (
            f"Maze arena row ends at {end_str}, expected <= 10:00"
        )

    # Line division is scheduled successfully (global 09:00-17:00 window)
    assert len(line_arena_rows) == 4, f"Expected 4 Line arena rows (1 per team), got {len(line_arena_rows)}"


def test_generate_division_day_runs(tmp_path):
    """--division-day-runs Maze:Day1:2 with runs=3 and 2-day schedule gives 2 Day1 runs, 1 Day2 run."""
    maze_csv = tmp_path / "maze.csv"
    maze_csv.write_text("team_name\nTeam A\nTeam B\nTeam C\nTeam D\n")
    schedule_file = tmp_path / "schedule.json"
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "generate",
        "--division", f"Maze:{maze_csv}:arenas=1:runs=3",
        "--division-day-runs", "Maze:Day1:2",
        "--run-time", "10",
        "--interview-time", "15",
        "--interview-group-size", "2",
        "--day", "Day1:09:00-17:00",
        "--day", "Day2:09:00-17:00",
        "--save", str(schedule_file),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output

    maze_teams = {"Team A", "Team B", "Team C", "Team D"}

    for day_name, expected_runs in [("Day1", 2), ("Day2", 1)]:
        day_csv = output_dir / f"{day_name}.csv"
        assert day_csv.exists(), f"{day_name}.csv not found"
        with open(day_csv) as f:
            rows = list(csv.DictReader(f))
        maze_arena_rows = [r for r in rows if "Maze" in r["resource"] and "Arena" in r["resource"]]
        for team_name in maze_teams:
            team_rows = [r for r in maze_arena_rows if r["teams"].strip() == team_name]
            assert len(team_rows) == expected_runs, (
                f"{team_name} on {day_name}: expected {expected_runs} runs, got {len(team_rows)}"
            )
