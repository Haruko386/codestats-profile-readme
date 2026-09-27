import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_history_graph.py"
SPEC = importlib.util.spec_from_file_location("generate_history_graph", SCRIPT)
graph = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(graph)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "username": "tester",
            "timezone": "Asia/Shanghai",
            "history_days": 3,
            "max_languages": 1,
            "width": 600,
            "height": 240,
            "show_legend": True,
            "output": "out.svg",
            "history_file": "history.json",
            "colors_file": "colors.json",
            "color_overrides": {"Others": "#ededed"},
            "language_aliases": {"C/C++": "C++"},
            "unknown_color": "#d0d7de",
        }

    def test_target_day_uses_shanghai_calendar(self):
        instant = datetime(2026, 9, 26, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(graph.target_day("Asia/Shanghai", instant), date(2026, 9, 26))

    def test_update_history_replaces_day_and_prunes_old_entries(self):
        history = {
            "days": {
                "2026-09-22": {"Go": 1},
                "2026-09-25": {"Go": 2},
                "2026-09-26": {"Go": 999},
            }
        }
        updated = graph.update_history(history, "Tester", date(2026, 9, 26), {"Go": 3}, 3)
        self.assertEqual(updated["days"], {"2026-09-25": {"Go": 2}, "2026-09-26": {"Go": 3}})

    def test_changing_username_clears_previous_users_history(self):
        history = {"username": "SomeoneElse", "days": {"2026-09-25": {"Go": 99}}}
        updated = graph.update_history(history, "Tester", date(2026, 9, 26), {"Python": 3}, 30)
        self.assertEqual(updated["days"], {"2026-09-26": {"Python": 3}})

    def test_series_groups_languages_after_limit(self):
        days = {"2026-09-26": {"Go": 50, "Python": 30, "HTML": 20}}
        series = graph.graph_series(days, [date(2026, 9, 26)], 1)
        self.assertEqual(series, [("Go", [50]), ("Others", [50])])

    def test_alias_uses_official_colour(self):
        colour = graph.colour_for("C/C++", self.config, {"C++": "#f34b7d"})
        self.assertEqual(colour, "#f34b7d")

    @patch.object(graph, "http_text")
    def test_fetch_range_drops_partial_next_day(self, http_text):
        http_text.return_value = (
            '{"data":{"profile":{"day_language_xps":['
            '{"date":"2026-09-25","language":"Markdown","xp":10},'
            '{"date":"2026-09-26","language":"Go","xp":40},'
            '{"date":"2026-09-26","language":"Go","xp":2},'
            '{"date":"2026-09-27","language":"Python","xp":999}'
            "]}}}"
        )
        self.assertEqual(
            graph.fetch_range("Tester", date(2026, 9, 24), date(2026, 9, 26)),
            {
                "2026-09-24": {},
                "2026-09-25": {"Markdown": 10},
                "2026-09-26": {"Go": 42},
            },
        )

    def test_render_is_valid_svg_and_escapes_language(self):
        history = {"username": "Tester", "days": {"2026-09-26": {"A&B": 10}}}
        svg = graph.render_svg(history, date(2026, 9, 26), self.config, {})
        ET.fromstring(svg)
        self.assertIn("A&amp;B", svg)
        self.assertIn("Sep 26", svg)

    def test_json_output_ends_with_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "value.json"
            graph.write_json(output, {"b": 1, "a": 2})
            self.assertEqual(output.read_bytes()[-1:], b"\n")

    def test_relative_output_can_target_caller_workspace(self):
        workspace = Path("caller-repository")
        self.assertEqual(
            graph.relative_path("assets/history.svg", workspace),
            workspace / "assets" / "history.svg",
        )


if __name__ == "__main__":
    unittest.main()
