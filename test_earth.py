import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


EARTH = Path(__file__).with_name("earth")


class EarthCLITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "earth.db"

    def tearDown(self):
        self.temp.cleanup()

    def run_earth(self, *args, input_text=None, check=True, extra_env=None):
        env = os.environ.copy()
        env["EARTH_GAME_DB"] = str(self.db)
        env.update(extra_env or {})
        result = subprocess.run(
            [sys.executable, str(EARTH), *map(str, args)],
            input=input_text,
            text=True,
            capture_output=True,
            env=env,
        )
        if check and result.returncode:
            self.fail(f"earth {' '.join(map(str, args))}: {result.stderr}")
        return result

    def test_init_is_safe_and_today_guides_a_new_user(self):
        first = self.run_earth("init")
        second = self.run_earth("init")
        today = self.run_earth("today")

        self.assertIn("initialized", first.stdout)
        self.assertIn("already initialized", second.stdout)
        self.assertIn("earth quest add", today.stdout)
        self.assertIn("Open loops: 0", today.stdout)
        self.assertIn("Review: due", today.stdout)

    def test_character_and_quest_lifecycle(self):
        self.run_earth("init")
        self.run_earth(
            "character",
            "edit",
            "--values",
            "kindness",
            "--purpose",
            "leave things better",
        )
        character = self.run_earth("character", "show")
        self.assertIn("Values: kindness", character.stdout)
        self.assertIn("Purpose: leave things better", character.stdout)

        self.run_earth(
            "quest",
            "add",
            "--title",
            "Ship a tiny tool",
            "--next",
            "write the first check",
            "--pillar",
            "production",
            "--driver",
            "purpose",
        )
        self.run_earth(
            "quest", "add", "--title", "Take a walk", "--next", "put on shoes"
        )
        self.run_earth("quest", "start", "1")

        cancelled = self.run_earth(
            "quest", "start", "2", input_text="n\n", check=False
        )
        self.assertNotEqual(0, cancelled.returncode)
        self.assertIn("cancelled", cancelled.stderr)

        self.run_earth("quest", "start", "2", "--yes")
        today = self.run_earth("today")
        self.assertIn("Purpose: leave things better", today.stdout)
        self.assertIn("Current quest: Take a walk", today.stdout)
        self.assertIn("Next action: put on shoes", today.stdout)

        with sqlite3.connect(self.db) as db:
            current_count = db.execute(
                "SELECT count(*) FROM quests WHERE status = 'current'"
            ).fetchone()[0]
        self.assertEqual(1, current_count)

        self.run_earth("quest", "done", "2")
        quests = self.run_earth("quest", "list", "--all")
        self.assertIn("COMPLETED Take a walk", quests.stdout)
        missing = self.run_earth("quest", "done", "999", check=False)
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("not found", missing.stderr)

    def test_open_loops_review_and_export(self):
        self.run_earth("init")
        self.run_earth(
            "quest", "add", "--title", "Reconnect", "--next", "message Sam"
        )
        self.run_earth("quest", "start", "1")
        self.run_earth("loop", "add", "--text", "book dentist")
        self.assertIn("[1] OPEN book dentist", self.run_earth("loop", "list").stdout)
        self.assertIn("Open loops: 1", self.run_earth("today").stdout)

        self.run_earth(
            "review",
            "--love",
            "listened carefully",
            "--adaptation",
            "changed the schedule",
            "--alignment",
            "yes",
            "--contribution",
            "helped a neighbor",
            "--next",
            "call Sam",
            "--update-quest",
        )
        today = self.run_earth("today")
        self.assertIn("Next action: call Sam", today.stdout)
        self.assertIn("Review: last completed", today.stdout)

        self.run_earth(
            "review",
            "--love",
            "kept listening",
            "--adaptation",
            "stayed flexible",
            "--alignment",
            "still yes",
            "--contribution",
            "shared notes",
            "--next",
            "do not replace the quest action",
        )
        self.assertIn("Next action: call Sam", self.run_earth("today").stdout)

        with sqlite3.connect(self.db) as db:
            stored = db.execute(
                "SELECT created_at FROM reviews ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        expected_local_date = (
            datetime.fromisoformat(stored.replace("Z", "+00:00")) + timedelta(hours=14)
        ).date().isoformat()
        local_today = self.run_earth("today", extra_env={"TZ": "Etc/GMT-14"})
        self.assertIn(f"Review: last completed {expected_local_date}", local_today.stdout)

        exported = self.run_earth("export").stdout
        data = json.loads(exported)
        self.assertEqual("book dentist", data["open_loops"][0]["description"])
        self.assertEqual("", data["profile"]["values"])
        self.assertEqual("call Sam", data["quests"][0]["next_action"])
        self.assertEqual("helped a neighbor", data["reviews"][0]["answers"]["contribution"])
        self.assertEqual(exported, self.run_earth("export").stdout)

        export_path = Path(self.temp.name) / "export.json"
        self.run_earth("export", export_path)
        self.assertEqual(data, json.loads(export_path.read_text(encoding="utf-8")))
        overwrite = self.run_earth("export", export_path, check=False)
        self.assertNotEqual(0, overwrite.returncode)
        self.assertIn("File exists", overwrite.stderr)
        self.assertEqual([], list(export_path.parent.glob(".export.json.*")))

        self.run_earth("loop", "close", "1")
        self.assertIn("Open loops: 0", self.run_earth("today").stdout)


if __name__ == "__main__":
    unittest.main()
