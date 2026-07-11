# Earth Game Roadmap

## Goal

Build a private, offline command-line companion that turns the ideas in
`PLAN.md` into a small repeatable loop:

```text
know your character -> choose a quest -> take the next action
        ^                                      |
        +----------- review and adapt <--------+
```

The program should help one person choose deliberately, close distracting open
loops, and notice drift. It is a reflection tool, not a literal measure of a
person's worth.

## Product translation

| Idea in `PLAN.md` | Program behavior |
| --- | --- |
| Hidden character traits | A private profile of values, strengths, frictions, purpose, and anti-vision |
| Connections, production, mindset, health, awareness | Optional pillar tags on quests and reviews |
| Curiosity, passion, purpose, autonomy, mastery | Optional driver tags explaining why a quest matters |
| Custom quests and checkpoints | User-created quests with one concrete next action |
| Background programs | A short list of open loops that can be closed or discarded |
| Entropy | A weekly review that checks alignment and stale commitments |
| The NPC trap | `earth today`, which shows the one quest the user chose to focus on |
| Love, connection, adaptability, authenticity, contribution | Reflection prompts, never a calculated score or public leaderboard |

## Smallest useful implementation

Use one executable Python 3 script backed by SQLite from the Python standard
library.

- Source: `earth`
- Check: `test_earth.py`
- Runtime dependencies: none beyond Python 3
- Data: `${XDG_DATA_HOME:-$HOME/.local/share}/earth-game/earth.db`
- Test override: `EARTH_GAME_DB=/tmp/test-earth.db`

Python is the default because its standard library already provides the CLI
parser, SQLite, JSON, dates, and tests. Do not rewrite it in Rust, C, Bash, or
Odin unless deployment later requires a standalone binary or measurements show
a real limitation.

## Scope

### In the first release

- One local user and one character profile
- One current quest at a time
- A backlog of planned, completed, and dropped quests
- One next action per quest
- Open-loop capture and closure
- A short weekly review
- Human-readable terminal output and JSON export
- Local, user-owned storage with no network access

### Deliberately out of scope

- Accounts, cloud sync, social features, or a public leaderboard
- XP, coins, streaks, rankings, or an algorithmic life score
- AI-generated goals, coaching, or automated judgments
- Calendars, notifications, timers, habit tracking, or a full task manager
- A GUI, TUI framework, plug-in system, or configuration framework
- Medical, mental-health, or substance-use recommendations

The health pillar is only a user-defined reflection label. The program must not
diagnose, prescribe, or suggest that professional support can be replaced by
the tool.

## Command contract

```text
earth init
earth character show
earth character edit

earth quest add
earth quest list [--all]
earth quest start ID
earth quest done ID
earth quest drop ID

earth loop add
earth loop list [--all]
earth loop close ID

earth today
earth review
earth export [PATH]
```

Commands that create or edit content prompt for missing values. Flags may
supply those values for scripts and tests. `--help` documents every command.

Key behavior:

- `earth init` creates missing storage but never overwrites existing data.
- `earth quest add` requires a title and a concrete next action. Everything
  else is optional.
- `earth quest start ID` makes that quest current. If another quest is current,
  it returns the old one to the backlog after confirmation.
- `earth today` shows the current quest, its next action, unresolved-loop count,
  and whether a review is due. Empty states explain the next valid command.
- `earth review` first lists open loops, then records five short reflections:
  love and connection, adaptation to change, authenticity and alignment,
  contribution, and the next action or pillar needing attention. It changes a
  quest only with confirmation.
- `earth export` writes all user content as stable, readable JSON. With no path,
  it writes to standard output.
- Unknown IDs, invalid tags, missing required text, and unwritable storage
  produce a clear error on standard error and a non-zero exit status.

## Data model

Keep four tables:

```text
profile
  id = 1
  values, strengths, frictions, purpose, anti_vision, updated_at

quests
  id, title, why, next_action, pillar, driver, horizon,
  status, created_at, completed_at

open_loops
  id, description, status, created_at, closed_at

reviews
  id, answers_json, created_at
```

Rules:

- Quest status is `planned`, `current`, `completed`, or `dropped`.
- Open-loop status is `open` or `closed`.
- Pillar, when present, is `connection`, `production`, `mindset`, `health`, or
  `awareness`.
- Driver, when present, is `curiosity`, `passion`, `purpose`, `autonomy`, or
  `mastery`.
- There can be at most one current quest; changing it happens in one database
  transaction.
- All SQL uses parameters. Text is stored verbatim, including spaces and
  newlines.
- Timestamps are stored as UTC ISO 8601 and displayed in local time.
- The data directory and database are private to the current user where the
  operating system supports Unix permissions.
- Track the schema with SQLite's `user_version`; add a direct migration only
  when a schema change actually exists.

## Milestones

### 0. Walking skeleton

- Add the executable, argument parser, database connection, and schema creation.
- Implement `init`, global `--help`, and the empty `today` state.
- Add one standard-library integration test using a temporary database.

Checkpoint: running `earth init` twice is safe, and `earth today` tells a new
user how to create a quest.

### 1. The useful quest loop

- Implement quest add, list, start, done, and drop.
- Enforce one current quest in a transaction.
- Make `today` show the current title and next action.
- Test the complete add -> start -> today -> done path and invalid IDs.

Checkpoint: a user can complete the core loop without editing a file or opening
the database.

### 2. Character and alignment

- Implement character show and edit.
- Add the optional pillar, driver, horizon, and “why” fields to quests.
- Show purpose beside the current quest when one has been recorded.
- Validate tags while leaving free-form profile text unrestricted.

Checkpoint: a user can explain both what they are doing and why it fits the
character they are trying to build.

### 3. Open loops and review

- Implement open-loop add, list, and close.
- Implement the five-question review and persist its answers.
- Mark a review due when no review has been recorded in the previous seven days.
- Test that a review records answers without silently changing quest state.

Checkpoint: `earth today` exposes drift without becoming another task manager.

### 4. Data ownership and release

- Implement deterministic JSON export.
- Make interrupted writes safe by relying on SQLite transactions.
- Document the data location, manual backup, restore, and uninstall steps in
  `--help` or a short `README.md`.
- Run the automated check on a fresh temporary database and manually exercise
  the first-run flow.

Checkpoint: tag `v0.1.0` only when the definition of done below is satisfied.

## Definition of done for v0.1.0

- A new user can initialize the app and start a first quest in under a minute.
- The core quest loop survives process restarts and invalid input.
- Exactly one quest can be current.
- Reviews and open loops persist and appear correctly in `today`.
- Exported JSON contains the profile, quests, open loops, and reviews.
- The program makes no network requests and creates files only in its data path.
- `python3 -m unittest -v` passes using only the standard library.
- `python3 -m py_compile earth` succeeds.
- Help output is enough to discover every command without reading source code.

## After v0.1.0

Observe real use before adding anything. The first candidates are a compact
history view and import from the exported JSON. Add reminders, richer analytics,
encryption, sync, or a different implementation language only after a concrete
need appears; do not build them from the metaphor alone.

## Assumptions

- `PLAN.md` supplies themes and vocabulary, not literal claims the software must
  enforce.
- The first user is comfortable in a Unix-like terminal with Python 3 installed.
- All content is entered and interpreted by the user; the program organizes it
  but does not decide what a good life or winning score means.
