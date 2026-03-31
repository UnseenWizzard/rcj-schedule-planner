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
