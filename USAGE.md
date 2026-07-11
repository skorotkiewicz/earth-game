# Using Earth Game

Earth Game keeps one question visible: **what did you choose to move forward
next?**

The basic loop is:

```text
describe your character -> create a quest -> make it current
-> take the next action -> review -> complete, drop, or adjust
```

Run these examples from the project directory. Use `./earth COMMAND --help`
whenever you need the exact options.

## 1. Initialize your local game

```sh
./earth init
```

This creates a private SQLite database. Running `init` again is safe and does
not overwrite it.

## Optional: use the local web UI

```sh
./earth web
```

Your browser opens `http://127.0.0.1:8765/`. The dashboard exposes the same
character, quests, open loops, weekly review, and JSON export as the CLI, using
the same database. Changes made in one interface immediately appear in the
other.

The server listens only on this computer. Stop it with Ctrl-C. To keep the
browser closed or choose another local port:

```sh
./earth web --no-open
./earth web --port 9000
```

There is intentionally no option to expose the server to your LAN or the
internet.

## 2. Describe the character you are playing

Imagine Maya wants to move into more meaningful work without sacrificing the
relationships and stability she already values:

```sh
./earth character edit \
  --values "curiosity, reliability, kindness" \
  --strengths "explaining complex ideas, patient research" \
  --frictions "overcommitting, waiting for perfect plans" \
  --purpose "make useful knowledge easier to understand" \
  --anti-vision "busy all day while neglecting people and health"
```

Check the result:

```sh
./earth character show
```

Running `./earth character edit` without options starts an interactive edit.
Press Enter to keep an existing value. Supplying options changes only the named
fields.

## 3. Turn a real goal into a quest

“Get a better job” is too vague to act on. Maya makes it a quest with a next
action that can be completed today:

```sh
./earth quest add \
  --title "Move into a data analyst role" \
  --why "Use research and explanation skills on useful problems" \
  --next "List three analyst roles whose work looks meaningful" \
  --pillar production \
  --driver mastery \
  --horizon "six months"
```

Earth Game prints the new quest ID. List the backlog and make that quest
current:

```sh
./earth quest list
./earth quest start 1
./earth today
```

Example `today` output:

```text
Purpose: make useful knowledge easier to understand
Current quest: [1] Move into a data analyst role
Next action: List three analyst roles whose work looks meaningful
Open loops: 0
Review: due
```

Quest IDs may differ in your database; always use the ID from `quest list`.

## 4. Capture distractions without changing quests

While working, Maya remembers unrelated obligations. They are important enough
not to forget, but they do not need to replace the current quest:

```sh
./earth loop add --text "Renew library card"
./earth loop add --text "Reply to landlord about the inspection"
./earth loop list
```

After handling one:

```sh
./earth loop close 1
./earth today
```

Closed loops disappear from the default list. Include history with:

```sh
./earth loop list --all
```

## 5. Review the week

The easiest review is interactive:

```sh
./earth review
```

It first shows unresolved loops, then asks about:

1. love and connection;
2. adaptation to change;
3. authenticity and alignment;
4. contribution; and
5. the next action or pillar needing attention.

For a scripted or copy-paste review, provide all five answers:

```sh
./earth review \
  --love "Made time to listen to my partner instead of multitasking" \
  --adaptation "Reduced the weekly target after a demanding work deadline" \
  --alignment "The analyst quest still fits my purpose and values" \
  --contribution "Helped a coworker understand a confusing report" \
  --next "Ask one analyst for a 20-minute informational interview" \
  --update-quest
```

`--update-quest` explicitly replaces the current quest's next action with the
`--next` answer. Without it, the review is saved but the quest is unchanged.
`today` marks another review due after seven days.

## 6. Switch focus when life changes

Suppose an apartment inspection becomes the real priority:

```sh
./earth quest add \
  --title "Prepare for apartment inspection" \
  --next "Photograph the maintenance issue" \
  --pillar awareness \
  --driver autonomy \
  --horizon "this week"

./earth quest start 2
```

Earth Game asks before replacing the current quest. If confirmed, the previous
quest returns to the backlog; it is not deleted. Scripts can confirm explicitly:

```sh
./earth quest start 2 --yes
```

There is still only one current quest.

## 7. Finish or deliberately stop a quest

Complete work that reached its intended outcome:

```sh
./earth quest done 2
```

Drop work that no longer deserves attention:

```sh
./earth quest drop 1
```

The default list shows current and planned quests. Include completed and dropped
history with:

```sh
./earth quest list --all
```

Dropping a quest is not failure; it is an explicit decision to stop spending
attention on it.

## More real-world quest examples

### Rebuild a relationship

```sh
./earth quest add \
  --title "Reconnect with my brother" \
  --why "I want a relationship based on regular, honest contact" \
  --next "Send a message asking when he is free to talk" \
  --pillar connection \
  --driver purpose \
  --horizon "three months"
```

### Finish a household project

```sh
./earth quest add \
  --title "Make the spare room usable" \
  --next "Fill one donation box from the closet" \
  --pillar awareness \
  --driver autonomy \
  --horizon "this month"
```

### Learn a skill for connection

```sh
./earth quest add \
  --title "Learn conversational Spanish" \
  --why "Speak comfortably with extended family" \
  --next "Schedule one 30-minute conversation practice" \
  --pillar connection \
  --driver mastery \
  --horizon "one year"
```

Good next actions start with a concrete verb: call, write, schedule, list, ask,
read, repair, or deliver. “Work on it” usually hides the real first step.

## Choosing pillar and driver tags

Tags are optional. Use them only when they make a quest easier to understand.

| Situation | Likely pillar | Likely driver |
| --- | --- | --- |
| Repair a friendship | `connection` | `purpose` |
| Ship a useful work project | `production` | `mastery` |
| Change an unhelpful assumption | `mindset` | `curiosity` |
| Create a sustainable movement routine | `health` | `autonomy` |
| Review commitments and direction | `awareness` | `purpose` |

The tags organize reflection; they do not score or judge you. The health pillar
is not medical guidance.

## Export your data

Print JSON to the terminal:

```sh
./earth export
```

Write a private JSON file:

```sh
./earth export earth-export-2026-07-11.json
```

Earth Game refuses to overwrite an existing export. Choose a new filename if
the target already exists. JSON export is currently for reading and portability;
there is no import command yet.

For a full backup, copy the SQLite database while no Earth Game command is
running. `./earth --help` prints its exact location.

## Use a separate database

`EARTH_GAME_DB` can isolate a trial run, another profile, or a test script:

```sh
EARTH_GAME_DB="$HOME/.local/share/earth-game-sandbox/earth.db" ./earth init
EARTH_GAME_DB="$HOME/.local/share/earth-game-sandbox/earth.db" ./earth today
```

Every command in that shell must use the same variable to reach the same data.
The normal app intentionally stays single-user and local.

## A lightweight cadence

Daily, or whenever attention feels scattered:

```sh
./earth today
```

Capture an unrelated obligation with `loop add`; do not create a quest for every
task. When the displayed next action is done, either complete the quest or use a
review to choose the next action.

Weekly:

```sh
./earth loop list
./earth quest list
./earth review
```

That is enough. Earth Game is not intended to replace a calendar or task
manager.

## Common errors

### “not initialized”

Run:

```sh
./earth init
```

### “quest ID not found” or “open loop ID not found”

List the records and use the displayed ID:

```sh
./earth quest list --all
./earth loop list --all
```

### Starting a quest waits for confirmation

Another quest is already current. Answer `y` to return it to the backlog, or
use `--yes` in a non-interactive command.

### An export says the file already exists

Exports never overwrite files. Pick another filename.

### A pillar or driver is rejected

Show the accepted values:

```sh
./earth quest add --help
```
