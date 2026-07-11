# Earth Game

![Earth Game: a connected planet with a glowing quest path](assets/earth-game-banner.png)

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
![Dependencies: standard library](https://img.shields.io/badge/dependencies-standard_library_only-2ea44f)
![Storage: local SQLite](https://img.shields.io/badge/storage-local_SQLite-0f80cc?logo=sqlite&logoColor=white)
![Network: no external requests](https://img.shields.io/badge/network-no_external_requests-6f42c1)

A private, offline companion for choosing quests, taking the next action,
closing open loops, and reviewing your direction before drift sets in.

Earth Game uses Python's standard library and SQLite. It has no third-party
dependencies, accounts, outbound requests, scoring, or AI-generated advice.

## Requirements

- Python 3.8 or newer
- A Unix-like terminal

## Install on Arch Linux

Earth Game is available from the [AUR](https://aur.archlinux.org/packages/earth-game):

```sh
yay -S earth-game
```

After installation, run `earth` or `earth-game` from anywhere.

## Quick start

```sh
./earth init
./earth character edit
./earth quest add
./earth quest list
./earth quest start 1
./earth today
```

Prefer a browser? Start the same app as a local-only web UI:

```sh
./earth web
```

It opens a private session URL on `http://127.0.0.1:8765/` and uses the same
database as the CLI. Stop it with Ctrl-C. It never binds to your LAN or makes
external requests.

Commands prompt for missing text. Options also support non-interactive use:

```sh
./earth quest add \
  --title "Reconnect with an old friend" \
  --next "Send Sam a message" \
  --pillar connection \
  --driver purpose

./earth quest start 1
./earth today
```

Run `./earth --help` or `./earth COMMAND --help` for the complete interface.
See [USAGE.md](USAGE.md) for complete real-world walkthroughs.

## Commands

- `earth init` creates local storage without overwriting an existing database.
- `earth character show|edit` manages values, strengths, frictions, purpose,
  and anti-vision.
- `earth quest add|list|start|done|drop` manages quests. Only one quest can be
  current.
- `earth loop add|list|close` captures and closes unresolved tasks or concerns.
- `earth today` shows the current quest, next action, open-loop count, and
  review status.
- `earth review` records five short reflections. Pass `--update-quest` to use
  the `--next` answer as the current quest's next action.
- `earth export [PATH]` exports all data as readable JSON. Existing files are
  never overwritten.
- `earth web` starts the local browser UI. Use `--no-open` or choose a port with
  `--port PORT`.

## Typical loop

```sh
./earth loop add --text "Book the dentist"
./earth today
./earth quest done 1
./earth review
./earth export earth-export.json
```

## Data and privacy

The default database is:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/earth-game/earth.db
```

Set `EARTH_GAME_DB` to use another path:

```sh
EARTH_GAME_DB=/path/to/earth.db ./earth init
```

The database and JSON exports are created with private permissions on Unix.
Earth Game makes no external network requests; the web command listens only on
the local loopback address and requires the private session URL printed at
startup.

To back up or restore, copy the SQLite database while no Earth Game command is
running. `./earth --help` prints the exact active data path.

## Tests

```sh
python3 -m unittest -v
python3 -m py_compile earth earth_core.py earth_web.py
```

## Structure

- `earth` contains CLI parsing and terminal interaction.
- `earth_core.py` contains SQLite and shared domain operations.
- `earth_web.py` contains the local HTTP server and HTML interface.

See [ROADMAP.md](ROADMAP.md) for the product decisions and future-change rules.
