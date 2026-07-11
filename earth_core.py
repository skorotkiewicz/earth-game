"""Shared SQLite storage and domain operations for Earth Game."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
PILLARS = ("connection", "production", "mindset", "health", "awareness")
DRIVERS = ("curiosity", "passion", "purpose", "autonomy", "mastery")
SCHEMA = """
CREATE TABLE profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    values_text TEXT NOT NULL DEFAULT '',
    strengths TEXT NOT NULL DEFAULT '',
    frictions TEXT NOT NULL DEFAULT '',
    purpose TEXT NOT NULL DEFAULT '',
    anti_vision TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE quests (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    why TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL,
    pillar TEXT CHECK (
        pillar IS NULL OR pillar IN
        ('connection', 'production', 'mindset', 'health', 'awareness')
    ),
    driver TEXT CHECK (
        driver IS NULL OR driver IN
        ('curiosity', 'passion', 'purpose', 'autonomy', 'mastery')
    ),
    horizon TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN ('planned', 'current', 'completed', 'dropped')
    ),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX one_current_quest
ON quests(status) WHERE status = 'current';

CREATE TABLE open_loops (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY,
    answers_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class EarthError(Exception):
    pass


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp():
    return now_utc().isoformat().replace("+00:00", "Z")


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def data_path():
    override = os.environ.get("EARTH_GAME_DB")
    if override:
        return Path(override).expanduser()
    root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return root / "earth-game/earth.db"


def secure(path, parent_created=False):
    if os.name != "posix":
        return
    if parent_created or path.parent.name == "earth-game":
        os.chmod(path.parent, 0o700)
    if path.exists():
        os.chmod(path, 0o600)


def checked_connection(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        db.close()
        raise EarthError(
            f"unsupported database schema {version}; expected {SCHEMA_VERSION}"
        )
    return db


@contextmanager
def database():
    path = data_path()
    if not path.is_file():
        raise EarthError("not initialized; run 'earth init'")
    db = checked_connection(path)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database():
    path = data_path()
    if path.exists():
        db = checked_connection(path)
        db.close()
        secure(path)
        return path, False

    parent_created = not path.parent.exists()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    db = sqlite3.connect(path)
    secure(path, parent_created)
    try:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO profile (id, updated_at) VALUES (1, ?)", (timestamp(),))
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        db.commit()
    finally:
        db.close()
    secure(path, parent_created)
    return path, True


def nonempty(value, label):
    if value is None or not value.strip():
        raise EarthError(f"{label} must not be empty")
    return value


def update_character(db, values):
    allowed = {"values_text", "strengths", "frictions", "purpose", "anti_vision"}
    if not values or not set(values) <= allowed:
        raise EarthError("invalid character fields")
    assignments = ", ".join(f"{field} = ?" for field in values)
    db.execute(
        f"UPDATE profile SET {assignments}, updated_at = ? WHERE id = 1",
        (*values.values(), timestamp()),
    )


def create_quest(db, title, next_action, why="", pillar=None, driver=None, horizon=""):
    title = nonempty(title, "title")
    next_action = nonempty(next_action, "next action")
    if pillar and pillar not in PILLARS:
        raise EarthError("invalid pillar")
    if driver and driver not in DRIVERS:
        raise EarthError("invalid driver")
    cursor = db.execute(
        """INSERT INTO quests
           (title, why, next_action, pillar, driver, horizon, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, why or "", next_action, pillar, driver, horizon or "", timestamp()),
    )
    return cursor.lastrowid


def get_quest(db, quest_id):
    quest = db.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    if not quest:
        raise EarthError(f"quest {quest_id} not found")
    return quest


def start_quest(db, quest_id):
    quest = get_quest(db, quest_id)
    if quest["status"] not in ("planned", "current"):
        raise EarthError(f"quest {quest_id} is {quest['status']}")
    if quest["status"] == "current":
        return False
    db.execute("UPDATE quests SET status = 'planned' WHERE status = 'current'")
    db.execute(
        "UPDATE quests SET status = 'current', completed_at = NULL WHERE id = ?",
        (quest_id,),
    )
    return True


def complete_quest(db, quest_id):
    quest = get_quest(db, quest_id)
    if quest["status"] == "completed":
        return False
    if quest["status"] == "dropped":
        raise EarthError(f"quest {quest_id} is dropped")
    db.execute(
        "UPDATE quests SET status = 'completed', completed_at = ? WHERE id = ?",
        (timestamp(), quest_id),
    )
    return True


def drop_quest(db, quest_id):
    quest = get_quest(db, quest_id)
    if quest["status"] == "dropped":
        return False
    if quest["status"] == "completed":
        raise EarthError(f"quest {quest_id} is completed")
    db.execute(
        "UPDATE quests SET status = 'dropped', completed_at = NULL WHERE id = ?",
        (quest_id,),
    )
    return True


def create_loop(db, description):
    cursor = db.execute(
        "INSERT INTO open_loops (description, created_at) VALUES (?, ?)",
        (nonempty(description, "open loop"), timestamp()),
    )
    return cursor.lastrowid


def close_loop(db, loop_id):
    loop = db.execute(
        "SELECT status FROM open_loops WHERE id = ?", (loop_id,)
    ).fetchone()
    if not loop:
        raise EarthError(f"open loop {loop_id} not found")
    if loop["status"] == "closed":
        return False
    db.execute(
        "UPDATE open_loops SET status = 'closed', closed_at = ? WHERE id = ?",
        (timestamp(), loop_id),
    )
    return True


def save_review(db, answers, update_quest=False):
    current = db.execute("SELECT id FROM quests WHERE status = 'current'").fetchone()
    if update_quest and not current:
        raise EarthError("no current quest to update")
    if update_quest:
        db.execute(
            "UPDATE quests SET next_action = ? WHERE id = ?",
            (nonempty(answers.get("next_action"), "next action"), current["id"]),
        )
    db.execute(
        "INSERT INTO reviews (answers_json, created_at) VALUES (?, ?)",
        (json.dumps(answers, ensure_ascii=False, sort_keys=True), timestamp()),
    )


def exported_json(db):
    profile = dict(db.execute("SELECT * FROM profile WHERE id = 1").fetchone())
    profile["values"] = profile.pop("values_text")
    quests = [dict(row) for row in db.execute("SELECT * FROM quests ORDER BY id")]
    loops = [dict(row) for row in db.execute("SELECT * FROM open_loops ORDER BY id")]
    reviews = []
    for row in db.execute("SELECT * FROM reviews ORDER BY id"):
        review = dict(row)
        review["answers"] = json.loads(review.pop("answers_json"))
        reviews.append(review)
    return (
        json.dumps(
            {
                "open_loops": loops,
                "profile": profile,
                "quests": quests,
                "reviews": reviews,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
