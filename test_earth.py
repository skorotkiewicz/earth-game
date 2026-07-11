import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


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

    def test_help_is_discoverable_at_every_command_level(self):
        version = self.run_earth("--version")
        self.assertRegex(version.stdout, r"\Aearth \d+\.\d+\.\d+\n\Z")

        for args, expected in (
            ((), "earth init"),
            (("character",), "edit      edit the profile"),
            (("quest",), "start     make a quest current"),
            (("loop",), "close     close an open loop"),
        ):
            with self.subTest(args=args):
                result = self.run_earth(*args)
                self.assertIn("usage:", result.stdout)
                self.assertIn(expected, result.stdout)

        add_help = self.run_earth("quest", "add", "--help")
        self.assertIn("concrete next action; prompted if omitted", add_help.stdout)
        start_help = self.run_earth("quest", "start", "--help")
        self.assertIn("-y", start_help.stdout)
        loop_help = self.run_earth("loop", "list", "--help")
        self.assertIn("-a", loop_help.stdout)
        web_help = self.run_earth("web", "--help")
        self.assertIn("bound only to 127.0.0.1", web_help.stdout)
        bad_port = self.run_earth("web", "--port", "70000", check=False)
        self.assertEqual(2, bad_port.returncode)
        self.assertIn("port must be between 0 and 65535", bad_port.stderr)

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

        cancelled = self.run_earth("quest", "start", "2", input_text="n\n", check=False)
        self.assertNotEqual(0, cancelled.returncode)
        self.assertIn("cancelled", cancelled.stderr)

        self.run_earth("quest", "start", "2", "--yes")
        today = self.run_earth("today")
        self.assertIn("Purpose: leave things better", today.stdout)
        self.assertIn("Current quest: [2] Take a walk", today.stdout)
        self.assertIn("Next action: put on shoes", today.stdout)

        with sqlite3.connect(self.db) as db:
            current_count = db.execute(
                "SELECT count(*) FROM quests WHERE status = 'current'"
            ).fetchone()[0]
        self.assertEqual(1, current_count)

        self.run_earth("quest", "done", "2")
        quests = self.run_earth("quest", "list", "--all")
        self.assertIn("pillar=production, driver=purpose", quests.stdout)
        self.assertIn("COMPLETED Take a walk", quests.stdout)
        missing = self.run_earth("quest", "done", "999", check=False)
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("not found", missing.stderr)

    def test_noninteractive_errors_name_the_missing_option(self):
        self.run_earth("init")
        missing_next = self.run_earth(
            "quest", "add", "--title", "Incomplete", input_text="", check=False
        )
        self.assertNotEqual(0, missing_next.returncode)
        self.assertIn("pass --next", missing_next.stderr)

        missing_values = self.run_earth("character", "edit", input_text="", check=False)
        self.assertNotEqual(0, missing_values.returncode)
        self.assertIn("pass --values", missing_values.stderr)

    def test_open_loops_review_and_export(self):
        self.run_earth("init")
        self.run_earth("quest", "add", "--title", "Reconnect", "--next", "message Sam")
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
            (
                datetime.fromisoformat(stored.replace("Z", "+00:00"))
                + timedelta(hours=14)
            )
            .date()
            .isoformat()
        )
        local_today = self.run_earth("today", extra_env={"TZ": "Etc/GMT-14"})
        self.assertIn(
            f"Review: last completed {expected_local_date}", local_today.stdout
        )

        exported = self.run_earth("export").stdout
        data = json.loads(exported)
        self.assertEqual("book dentist", data["open_loops"][0]["description"])
        self.assertEqual("", data["profile"]["values"])
        self.assertEqual("call Sam", data["quests"][0]["next_action"])
        self.assertEqual(
            "helped a neighbor", data["reviews"][0]["answers"]["contribution"]
        )
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

    def test_local_web_ui_core_flow_and_security(self):
        self.run_earth("init")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = os.environ.copy()
        env["EARTH_GAME_DB"] = str(self.db)
        process = subprocess.Popen(
            [sys.executable, str(EARTH), "web", "--port", str(port), "--no-open"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        startup = process.stdout.readline().strip()
        if not startup.startswith("Earth Game web UI: "):
            stdout, stderr = process.communicate(timeout=5)
            self.fail(f"web server did not start:\n{startup}\n{stdout}\n{stderr}")
        private_url = startup.removeprefix("Earth Game web UI: ")
        parts = urlsplit(private_url)
        base = f"{parts.scheme}://{parts.netloc}"
        opener = build_opener(HTTPCookieProcessor(CookieJar()))

        def get(path="/"):
            with opener.open(base + path, timeout=2) as response:
                return response, response.read().decode("utf-8")

        # def post(path, fields):
        #     request = Request(base + path, data=urlencode(fields).encode("utf-8"))
        def post(path, fields, origin=None):
            headers = {"Origin": origin} if origin else {}
            request = Request(
                base + path,
                data=urlencode(fields).encode("utf-8"),
                headers=headers,
            )
            with opener.open(request, timeout=2) as response:
                return response.read().decode("utf-8")

        try:
            with self.assertRaises(HTTPError) as unauthorized:
                urlopen(base + "/", timeout=2)
            self.assertEqual(401, unauthorized.exception.code)
            unauthorized.exception.close()

            with opener.open(private_url, timeout=2) as response:
                page = response.read().decode("utf-8")

            self.assertEqual("no-store", response.headers["Cache-Control"])
            self.assertIn(
                "frame-ancestors 'none'", response.headers["Content-Security-Policy"]
            )
            self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
            token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

            page = post(
                "/character",
                {
                    "csrf": token,
                    "values_text": "kindness",
                    "strengths": "listening",
                    "frictions": "overcommitting",
                    "purpose": "Make useful things",
                    "anti_vision": "Busy without meaning",
                },
                origin="null",
            )
            self.assertIn("Make useful things", page)
            page = post(
                "/quest/add",
                {
                    "csrf": token,
                    "title": "Practice <b>kindness</b>",
                    "next_action": "call Sam",
                    "pillar": "connection",
                    "driver": "purpose",
                    "horizon": "today",
                },
            )
            self.assertIn("Practice &lt;b&gt;kindness&lt;/b&gt;", page)
            self.assertNotIn("Practice <b>kindness</b>", page)
            page = post("/quest/start", {"csrf": token, "id": "1"})
            self.assertIn("Current quest · #1", page)
            self.assertIn("call Sam", page)
            self.assertIn(
                'aria-label="Complete quest #1: Practice &lt;b&gt;kindness&lt;/b&gt;"',
                page,
            )

            page = post("/loop/add", {"csrf": token, "description": "book the dentist"})
            self.assertIn("book the dentist", page)
            page = post("/loop/close", {"csrf": token, "id": "1"})
            self.assertNotIn("book the dentist", page)
            page = post(
                "/review",
                {
                    "csrf": token,
                    "love_connection": "listened",
                    "adaptation": "adjusted",
                    "alignment": "yes",
                    "contribution": "helped",
                    "next_action": "call tomorrow",
                    "update_quest": "1",
                },
            )
            self.assertIn("call tomorrow", page)

            post(
                "/quest/add",
                {
                    "csrf": token,
                    "title": "A quest to drop",
                    "next_action": "nothing",
                },
            )
            page = post("/quest/drop", {"csrf": token, "id": "2"})
            self.assertIn("A quest to drop", page)
            page = post("/quest/done", {"csrf": token, "id": "1"})
            self.assertIn("Choose what moves next", page)

            _, exported = get("/export")
            quests = json.loads(exported)["quests"]
            self.assertEqual("call tomorrow", quests[0]["next_action"])
            self.assertEqual("completed", quests[0]["status"])
            self.assertEqual("dropped", quests[1]["status"])

            with self.assertRaises(HTTPError) as csrf_error:
                post("/loop/add", {"csrf": "wrong", "description": "must not save"})
            self.assertEqual(403, csrf_error.exception.code)
            csrf_error.exception.close()

            # origin_request = Request(
            #     base + "/loop/add",
            #     data=urlencode({"csrf": token, "description": "must not save"}).encode(
            #         "utf-8"
            #     ),
            #     headers={"Origin": "https://example.com"},
            # )
            # with self.assertRaises(HTTPError) as origin_error:
            #     opener.open(origin_request, timeout=2)
            # self.assertEqual(403, origin_error.exception.code)
            # origin_error.exception.close()

            untrusted = Request(base + "/")
            untrusted.add_unredirected_header("Host", "example.com")
            with self.assertRaises(HTTPError) as host_error:
                opener.open(untrusted, timeout=2)
            self.assertEqual(400, host_error.exception.code)
            host_error.exception.close()
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
