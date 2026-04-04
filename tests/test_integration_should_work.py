import os
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOULD_WORK_SCRIPT = os.path.join(REPO_ROOT, "tests", "integration", "should_work.sh")


def test_should_work_generates_valid_schedule(tmp_path):
    result = subprocess.run(
        ["bash", SHOULD_WORK_SCRIPT],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"should_work.sh failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )

    schedule_path = os.path.join(REPO_ROOT, "output", "schedule.json")
    assert os.path.exists(schedule_path), f"schedule.json not found at {schedule_path}"

    validate = subprocess.run(
        ["rcj-planner", "validate", schedule_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, (
        f"rcj-planner validate failed (exit {validate.returncode}):\n"
        f"{validate.stdout}\n{validate.stderr}"
    )
    assert "valid" in validate.stdout.lower()
