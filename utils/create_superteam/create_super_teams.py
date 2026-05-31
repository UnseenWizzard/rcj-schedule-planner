#!/usr/bin/env python3
"""Create SuperTeams by pairing Maze+Line teams of same level, similar points, different language (city as fallback)."""

import csv
import argparse
import os
import sys
from dataclasses import dataclass


@dataclass
class Team:
    name: str
    discipline: str
    level: str
    city: str
    institution: str
    language: str
    points: int


@dataclass
class SuperTeam:
    maze_team: Team
    line_team: Team

    @property
    def level(self) -> str:
        return self.maze_team.level

    @property
    def points_diff(self) -> int:
        return abs(self.maze_team.points - self.line_team.points)


def load_teams(csv_path: str) -> list[Team]:
    teams = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                discipline = row.get("Discipline", "").strip()
                level = row.get("Level", "").strip()
                if discipline not in ("Maze", "Line") or level not in ("Entry", "Regular"):
                    continue
                teams.append(
                    Team(
                        name=row["TeamName"].strip(),
                        discipline=discipline,
                        level=level,
                        city=row["City"].strip(),
                        institution=row["Institution"].strip(),
                        language=row.get("Language", "").strip(),
                        points=int(row["Points"].strip()),
                    )
                )
            except (KeyError, ValueError):
                continue
    return teams


def _find_best_line_match(
    maze_team: Team,
    line: list[Team],
    used_line: set[int],
    points_range: int,
    require_diff_language: bool,
) -> tuple[int, Team, int] | None:
    best: tuple[int, Team, int] | None = None
    for i, line_team in enumerate(line):
        if i in used_line:
            continue
        if line_team.city.lower() == maze_team.city.lower():
            continue
        if require_diff_language and line_team.language.lower() == maze_team.language.lower():
            continue
        diff = abs(maze_team.points - line_team.points)
        if diff <= points_range and (best is None or diff < best[0]):
            best = (diff, line_team, i)
    return best


def create_super_teams(teams: list[Team], points_range: int = 20) -> list[SuperTeam]:
    result = []
    for level in ("Entry", "Regular"):
        maze = sorted(
            [t for t in teams if t.discipline == "Maze" and t.level == level],
            key=lambda t: t.points,
        )
        line = sorted(
            [t for t in teams if t.discipline == "Line" and t.level == level],
            key=lambda t: t.points,
        )
        used_line: set[int] = set()
        for maze_team in maze:
            best = _find_best_line_match(maze_team, line, used_line, points_range, require_diff_language=True)
            if not best:
                # No different-language match found; fall back to same language, city constraint still applies.
                best = _find_best_line_match(maze_team, line, used_line, points_range, require_diff_language=False)
            if best:
                _, matched, idx = best
                used_line.add(idx)
                result.append(SuperTeam(maze_team=maze_team, line_team=matched))
    return result


def write_short_csv(super_teams: list[SuperTeam], out) -> None:
    writer = csv.writer(out)
    writer.writerow(["team_name"])
    for st in super_teams:
        writer.writerow([f"{st.maze_team.name},{st.line_team.name}"])


def write_csv(super_teams: list[SuperTeam], out) -> None:
    writer = csv.writer(out)
    writer.writerow(
        ["Level", "MazeTeam", "MazeCity", "MazeLanguage", "MazePoints", "LineTeam", "LineCity", "LineLanguage", "LinePoints", "PointsDiff"]
    )
    for st in super_teams:
        writer.writerow(
            [
                st.level,
                st.maze_team.name,
                st.maze_team.city,
                st.maze_team.language,
                st.maze_team.points,
                st.line_team.name,
                st.line_team.city,
                st.line_team.language,
                st.line_team.points,
                st.points_diff,
            ]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create SuperTeams from Maze and Line rescue teams.")
    parser.add_argument("csv_file", help="Input CSV (TeamName;Discipline;Level;City;Institution;Language;Points)")
    parser.add_argument("--points-range", type=int, default=20, help="Max points difference (default: 20)")
    parser.add_argument("--output-dir", "-o", default=".", help="Directory for output CSV files (default: current directory)")
    args = parser.parse_args()

    teams = load_teams(args.csv_file)
    super_teams = create_super_teams(teams, args.points_range)

    for level in ("Entry", "Regular"):
        level_teams = [st for st in super_teams if st.level == level]
        details_path = os.path.join(args.output_dir, f"superteams_{level.lower()}_details.csv")
        with open(details_path, "w", newline="", encoding="utf-8") as f:
            write_csv(level_teams, f)
        short_path = os.path.join(args.output_dir, f"superteams_{level.lower()}.csv")
        with open(short_path, "w", newline="", encoding="utf-8") as f:
            write_short_csv(level_teams, f)
        print(f"Wrote {len(level_teams)} {level} super teams to {details_path} and {short_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
