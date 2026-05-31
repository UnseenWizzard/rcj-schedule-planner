import csv
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from utils.create_superteam.create_super_teams import Team, SuperTeam, load_teams, create_super_teams, write_csv


def make_team(name, discipline, level, city, points=0, language=""):
    return Team(name=name, discipline=discipline, level=level, city=city, institution="Test", language=language, points=points)


# ── load_teams ────────────────────────────────────────────────────────────────


class TestLoadTeams:
    def _write(self, tmp_path, content):
        p = tmp_path / "teams.csv"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_loads_valid_row(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Language;Points\nAlpha;Maze;Entry;Berlin;School;DE;10\n")
        teams = load_teams(path)
        assert len(teams) == 1
        t = teams[0]
        assert t.name == "Alpha"
        assert t.discipline == "Maze"
        assert t.level == "Entry"
        assert t.city == "Berlin"
        assert t.institution == "School"
        assert t.language == "DE"
        assert t.points == 10

    def test_loads_language_field(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Language;Points\nA;Maze;Entry;Berlin;S;FR;5\n")
        assert load_teams(path)[0].language == "FR"

    def test_loads_missing_language_as_empty(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Points\nA;Maze;Entry;Berlin;S;5\n")
        assert load_teams(path)[0].language == ""

    def test_loads_line_regular(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Language;Points\nBeta;Line;Regular;Munich;Gym;EN;5\n")
        teams = load_teams(path)
        assert len(teams) == 1
        assert teams[0].discipline == "Line"
        assert teams[0].level == "Regular"

    def test_skips_invalid_discipline(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Points\nA;Soccer;Entry;Berlin;S;0\n")
        assert load_teams(path) == []

    def test_skips_invalid_level(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Points\nA;Maze;Pro;Berlin;S;0\n")
        assert load_teams(path) == []

    def test_skips_non_numeric_points(self, tmp_path):
        # Matches malformed rows in real data that overflow into Points column
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Points\nA;Maze;Entry;Berlin;S;notanumber\n")
        assert load_teams(path) == []

    def test_skips_extra_columns_row(self, tmp_path):
        # Real data has rows like: Name;Regular;Line;Regular;City;Institution;0 (7 fields, wrong order)
        path = self._write(
            tmp_path,
            "TeamName;Discipline;Level;City;Institution;Points\n"
            "Iron Line;Regular;Line;Regular;Barcelos;Agrupamento;0\n"
            "Good;Maze;Entry;Berlin;School;5\n",
        )
        teams = load_teams(path)
        assert len(teams) == 1
        assert teams[0].name == "Good"

    def test_strips_whitespace(self, tmp_path):
        path = self._write(tmp_path, "TeamName;Discipline;Level;City;Institution;Points\n Alpha ;Maze;Entry; Berlin ;School; 7 \n")
        teams = load_teams(path)
        assert teams[0].name == "Alpha"
        assert teams[0].city == "Berlin"
        assert teams[0].points == 7


# ── create_super_teams ────────────────────────────────────────────────────────


class TestCreateSuperTeams:
    def test_pairs_maze_and_line_different_city(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin"), make_team("L1", "Line", "Entry", "Munich")]
        result = create_super_teams(teams, points_range=20)
        assert len(result) == 1
        assert result[0].maze_team.name == "M1"
        assert result[0].line_team.name == "L1"

    def test_no_match_same_city(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin"), make_team("L1", "Line", "Entry", "Berlin")]
        assert create_super_teams(teams) == []

    def test_city_case_insensitive(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin"), make_team("L1", "Line", "Entry", "berlin")]
        assert create_super_teams(teams) == []

    def test_no_match_points_too_far(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin", 0), make_team("L1", "Line", "Entry", "Munich", 50)]
        assert create_super_teams(teams, points_range=20) == []

    def test_match_at_exact_boundary(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin", 0), make_team("L1", "Line", "Entry", "Munich", 20)]
        assert len(create_super_teams(teams, points_range=20)) == 1

    def test_no_match_just_outside_boundary(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin", 0), make_team("L1", "Line", "Entry", "Munich", 21)]
        assert create_super_teams(teams, points_range=20) == []

    def test_no_cross_level_matching(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin"), make_team("L1", "Line", "Regular", "Munich")]
        assert create_super_teams(teams) == []

    def test_each_team_used_at_most_once(self):
        teams = [
            make_team("M1", "Maze", "Entry", "Berlin"),
            make_team("M2", "Maze", "Entry", "Hamburg"),
            make_team("L1", "Line", "Entry", "Munich"),
        ]
        result = create_super_teams(teams)
        assert len(result) == 1
        line_names = [st.line_team.name for st in result]
        assert line_names.count("L1") == 1

    def test_picks_closest_points(self):
        teams = [
            make_team("M1", "Maze", "Entry", "Berlin", 10),
            make_team("L1", "Line", "Entry", "Munich", 12),   # diff=2
            make_team("L2", "Line", "Entry", "Hamburg", 25),  # diff=15
        ]
        result = create_super_teams(teams, points_range=20)
        assert len(result) == 1
        assert result[0].line_team.name == "L1"

    def test_super_team_level_property(self):
        teams = [make_team("M1", "Maze", "Regular", "Berlin"), make_team("L1", "Line", "Regular", "Munich")]
        result = create_super_teams(teams)
        assert result[0].level == "Regular"

    def test_points_diff_property(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin", 5), make_team("L1", "Line", "Entry", "Munich", 15)]
        result = create_super_teams(teams, points_range=20)
        assert result[0].points_diff == 10

    def test_multiple_levels_matched_independently(self):
        teams = [
            make_team("ME", "Maze", "Entry", "Berlin"),
            make_team("LE", "Line", "Entry", "Munich"),
            make_team("MR", "Maze", "Regular", "Hamburg"),
            make_team("LR", "Line", "Regular", "Cologne"),
        ]
        result = create_super_teams(teams)
        assert len(result) == 2
        levels = {st.level for st in result}
        assert levels == {"Entry", "Regular"}

    def test_custom_points_range(self):
        teams = [make_team("M1", "Maze", "Entry", "Berlin", 0), make_team("L1", "Line", "Entry", "Munich", 5)]
        assert len(create_super_teams(teams, points_range=3)) == 0
        assert len(create_super_teams(teams, points_range=5)) == 1

    def test_prefers_different_language(self):
        teams = [
            make_team("M1", "Maze", "Entry", "Berlin", 10, language="EN"),
            make_team("L1", "Line", "Entry", "Munich", 10, language="EN"),   # same language
            make_team("L2", "Line", "Entry", "Hamburg", 10, language="FR"),  # different language
        ]
        result = create_super_teams(teams, points_range=20)
        assert len(result) == 1
        assert result[0].line_team.name == "L2"

    def test_fallback_allows_same_language_different_city(self):
        teams = [
            make_team("M1", "Maze", "Entry", "Berlin", 10, language="EN"),
            make_team("L1", "Line", "Entry", "Munich", 10, language="EN"),
        ]
        result = create_super_teams(teams, points_range=20)
        assert len(result) == 1
        assert result[0].line_team.name == "L1"

    def test_no_match_same_language_same_city(self):
        teams = [
            make_team("M1", "Maze", "Entry", "Berlin", 10, language="EN"),
            make_team("L1", "Line", "Entry", "Berlin", 10, language="EN"),
        ]
        assert create_super_teams(teams, points_range=20) == []


# ── write_csv ─────────────────────────────────────────────────────────────────


class TestWriteCsv:
    def test_writes_header_and_row(self):
        st = SuperTeam(
            maze_team=make_team("MazeA", "Maze", "Entry", "Berlin", 10),
            line_team=make_team("LineB", "Line", "Entry", "Munich", 15),
        )
        import io
        buf = io.StringIO()
        write_csv([st], buf)
        buf.seek(0)
        rows = list(csv.reader(buf))
        assert rows[0] == ["Level", "MazeTeam", "MazeCity", "MazeLanguage", "MazePoints", "LineTeam", "LineCity", "LineLanguage", "LinePoints", "PointsDiff"]
        assert rows[1] == ["Entry", "MazeA", "Berlin", "", "10", "LineB", "Munich", "", "15", "5"]

    def test_empty_list_writes_only_header(self):
        import io
        buf = io.StringIO()
        write_csv([], buf)
        buf.seek(0)
        rows = list(csv.reader(buf))
        assert len(rows) == 1

    def test_unmatched_maze_row_has_empty_line_columns(self):
        import io
        buf = io.StringIO()
        unmatched = [make_team("MazeX", "Maze", "Entry", "Vienna", 8, "DE")]
        write_csv([], buf, unmatched_maze=unmatched)
        buf.seek(0)
        rows = list(csv.reader(buf))
        assert rows[1] == ["Entry", "MazeX", "Vienna", "DE", "8", "", "", "", "", ""]

    def test_unmatched_line_row_has_empty_maze_columns(self):
        import io
        buf = io.StringIO()
        unmatched = [make_team("LineX", "Line", "Regular", "Prague", 12, "CZ")]
        write_csv([], buf, unmatched_line=unmatched)
        buf.seek(0)
        rows = list(csv.reader(buf))
        assert rows[1] == ["Regular", "", "", "", "", "LineX", "Prague", "CZ", "12", ""]


# ── main / per-level output ───────────────────────────────────────────────────


class TestMainOutputFiles:
    def _make_csv(self, tmp_path, rows):
        p = tmp_path / "teams.csv"
        lines = ["TeamName;Discipline;Level;City;Institution;Points"] + rows
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(p)

    def test_writes_one_file_per_level(self, tmp_path):
        from utils.create_superteam.create_super_teams import main
        csv_path = self._make_csv(tmp_path, [
            "ME;Maze;Entry;Berlin;S;0",
            "LE;Line;Entry;Munich;S;0",
            "MR;Maze;Regular;Hamburg;S;0",
            "LR;Line;Regular;Cologne;S;0",
        ])
        sys.argv = ["create_super_teams.py", csv_path, "--output-dir", str(tmp_path)]
        main()
        assert (tmp_path / "superteams_entry.csv").exists()
        assert (tmp_path / "superteams_regular.csv").exists()

    def test_entry_details_contains_only_entry_teams(self, tmp_path):
        from utils.create_superteam.create_super_teams import main
        csv_path = self._make_csv(tmp_path, [
            "ME;Maze;Entry;Berlin;S;0",
            "LE;Line;Entry;Munich;S;0",
            "MR;Maze;Regular;Hamburg;S;0",
            "LR;Line;Regular;Cologne;S;0",
        ])
        sys.argv = ["create_super_teams.py", csv_path, "--output-dir", str(tmp_path)]
        main()
        rows = list(csv.reader((tmp_path / "superteams_entry_details.csv").open()))
        data_rows = rows[1:]
        assert all(r[0] == "Entry" for r in data_rows)

    def test_regular_details_contains_only_regular_teams(self, tmp_path):
        from utils.create_superteam.create_super_teams import main
        csv_path = self._make_csv(tmp_path, [
            "ME;Maze;Entry;Berlin;S;0",
            "LE;Line;Entry;Munich;S;0",
            "MR;Maze;Regular;Hamburg;S;0",
            "LR;Line;Regular;Cologne;S;0",
        ])
        sys.argv = ["create_super_teams.py", csv_path, "--output-dir", str(tmp_path)]
        main()
        rows = list(csv.reader((tmp_path / "superteams_regular_details.csv").open()))
        data_rows = rows[1:]
        assert all(r[0] == "Regular" for r in data_rows)

    def test_details_includes_unmatched_teams(self, tmp_path):
        from utils.create_superteam.create_super_teams import main
        # M1 pairs with L1 (within range); M2 has no matching line team (points too far)
        csv_path = self._make_csv(tmp_path, [
            "M1;Maze;Entry;Berlin;S;10",
            "M2;Maze;Entry;Vienna;S;100",
            "L1;Line;Entry;Munich;S;10",
        ])
        sys.argv = ["create_super_teams.py", csv_path, "--output-dir", str(tmp_path)]
        main()
        rows = list(csv.reader((tmp_path / "superteams_entry_details.csv").open()))
        names_in_file = {r[1] for r in rows[1:]} | {r[5] for r in rows[1:]}
        assert "M1" in names_in_file
        assert "L1" in names_in_file
        assert "M2" in names_in_file  # unmatched, but still listed
