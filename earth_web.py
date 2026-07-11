"""Local-only HTTP and HTML interface for Earth Game."""

import secrets
import sqlite3
import webbrowser
from datetime import timedelta
from html import escape
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from earth_core import (
    DRIVERS,
    PILLARS,
    EarthError,
    close_loop,
    complete_quest,
    create_loop,
    create_quest,
    database,
    drop_quest,
    exported_json,
    now_utc,
    parse_timestamp,
    save_review,
    start_quest,
    update_character,
)


def html_text(value):
    return escape(str(value or ""), quote=True)


def csrf_field(token):
    return f'<input type="hidden" name="csrf" value="{html_text(token)}">'


def web_tags(quest):
    tags = [
        f"{label}: {value}"
        for label, value in (
            ("pillar", quest["pillar"]),
            ("driver", quest["driver"]),
            ("horizon", quest["horizon"]),
        )
        if value
    ]
    return f'<p class="tags">{html_text(" · ".join(tags))}</p>' if tags else ""


def action_form(path, token, record_id, label, accessible_label, kind=""):
    css = f' class="{kind}"' if kind else ""
    return (
        f'<form method="post" action="{path}">{csrf_field(token)}'
        f'<input type="hidden" name="id" value="{int(record_id)}">'
        f'<button{css} aria-label="{html_text(accessible_label)}" type="submit">'
        f"{html_text(label)}</button></form>"
    )


def render_web(db, token, error=""):
    profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    current = db.execute("SELECT * FROM quests WHERE status = 'current'").fetchone()
    planned = db.execute(
        "SELECT * FROM quests WHERE status = 'planned' ORDER BY id"
    ).fetchall()
    history = db.execute(
        "SELECT * FROM quests WHERE status IN ('completed', 'dropped') ORDER BY id DESC"
    ).fetchall()
    loops = db.execute(
        "SELECT * FROM open_loops WHERE status = 'open' ORDER BY id"
    ).fetchall()
    last_review = db.execute(
        "SELECT created_at FROM reviews ORDER BY id DESC LIMIT 1"
    ).fetchone()

    last_review_at = parse_timestamp(last_review[0]) if last_review else None
    review_due = not last_review_at or now_utc() - last_review_at >= timedelta(days=7)
    review_label = (
        "Review due"
        if review_due
        else f"Reviewed {last_review_at.astimezone().date().isoformat()}"
    )
    error_html = (
        f'<div class="error" role="alert">{html_text(error)}</div>' if error else ""
    )

    if current:
        current_html = f"""
        <article class="current">
          <p class="eyebrow">Current quest · #{current["id"]}</p>
          <h2>{html_text(current["title"])}</h2>
          <p class="next"><strong>Next:</strong> {html_text(current["next_action"])}</p>
          {web_tags(current)}
          <div class="actions">
            {action_form("/quest/done", token, current["id"], "Complete", f"Complete quest #{current['id']}: {current['title']}")}
            {action_form("/quest/drop", token, current["id"], "Drop", f"Drop quest #{current['id']}: {current['title']}", "quiet")}
          </div>
        </article>"""
    else:
        current_html = """
        <article class="current empty">
          <p class="eyebrow">Current quest</p>
          <h2>Choose what moves next.</h2>
          <p>Start a planned quest or create one below.</p>
        </article>"""

    planned_html = (
        "".join(
            f"""
        <li>
          <div><strong>#{quest["id"]} · {html_text(quest["title"])}</strong>
          <p>{html_text(quest["next_action"])}</p>{web_tags(quest)}</div>
          <div class="actions">
            {action_form("/quest/start", token, quest["id"], "Replace current" if current else "Make current", f"Make quest #{quest['id']} current: {quest['title']}")}
            {action_form("/quest/drop", token, quest["id"], "Drop", f"Drop quest #{quest['id']}: {quest['title']}", "quiet")}
          </div>
        </li>"""
            for quest in planned
        )
        or '<li class="empty-row">No planned quests.</li>'
    )

    loops_html = (
        "".join(
            f"""
        <li><span>#{loop["id"]} · {html_text(loop["description"])}</span>
        {action_form("/loop/close", token, loop["id"], "Close", f"Close open loop #{loop['id']}: {loop['description']}", "quiet")}</li>"""
            for loop in loops
        )
        or '<li class="empty-row">No open loops.</li>'
    )

    history_html = (
        "".join(
            f'<li><span class="status {quest["status"]}">{html_text(quest["status"])}</span> '
            f"#{quest['id']} · {html_text(quest['title'])}</li>"
            for quest in history
        )
        or '<li class="empty-row">No quest history yet.</li>'
    )

    pillar_options = '<option value="">No pillar</option>' + "".join(
        f'<option value="{value}">{value.title()}</option>' for value in PILLARS
    )
    driver_options = '<option value="">No driver</option>' + "".join(
        f'<option value="{value}">{value.title()}</option>' for value in DRIVERS
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Earth Game</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --card:#101d2e; --line:#263850;
      --text:#eef6ff; --muted:#9fb0c5; --gold:#f3c96b; --blue:#72b7ff; --bad:#ff9b9b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 50% -20%,#183556,var(--bg) 45%);
      color:var(--text); font:16px/1.5 system-ui,sans-serif; }}
    header,main,footer {{ width:min(1100px,calc(100% - 2rem)); margin:auto; }}
    header {{ display:flex; justify-content:space-between; gap:1rem; align-items:end;
      padding:3rem 0 1.5rem; }}
    h1,h2,h3,p {{ margin-top:0; }} h1 {{ margin-bottom:.25rem; font-size:clamp(2rem,7vw,4rem); }}
    h2 {{ margin-bottom:.5rem; }} h3 {{ margin-bottom:1rem; }}
    a {{ color:var(--blue); }} .eyebrow,.kicker,.tags {{ color:var(--muted); font-size:.82rem;
      letter-spacing:.06em; text-transform:uppercase; }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }}
    section,article {{ background:var(--card); background:color-mix(in srgb,var(--card) 94%,transparent);
      border:1px solid var(--line); border-radius:16px; padding:1.25rem; margin-bottom:1rem; }}
    .current {{ border-color:#826f3d; box-shadow:0 12px 50px #0005; }}
    .current h2 {{ font-size:clamp(1.5rem,4vw,2.4rem); }} .next {{ font-size:1.15rem; }}
    ul {{ list-style:none; padding:0; margin:0; }} li {{ display:flex; justify-content:space-between;
      align-items:start; gap:1rem; padding:.85rem 0; border-top:1px solid var(--line); }}
    li:first-child {{ border-top:0; }} li p {{ margin:.25rem 0; color:var(--muted); }}
    form {{ margin:0; }} .stack {{ display:grid; gap:.8rem; }} .two {{ display:grid;
      grid-template-columns:1fr 1fr; gap:.8rem; }} label {{ display:grid; gap:.3rem; color:var(--muted); }}
    input,textarea,select,button {{ width:100%; border:1px solid var(--line); border-radius:9px;
      padding:.68rem .75rem; background:#091525; color:var(--text); font:inherit; }}
    textarea {{ min-height:5rem; resize:vertical; }} button {{ width:auto; cursor:pointer;
      border-color:#ad8d42; background:var(--gold); color:#18202b; font-weight:700; }}
    button.quiet {{ background:transparent; color:var(--muted); border-color:var(--line); }}
    button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,a:focus-visible {{
      outline:3px solid var(--blue); outline-offset:2px; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }}
    .error {{ margin-bottom:1rem; padding:1rem; border:1px solid var(--bad); border-radius:10px;
      color:#ffe2e2; background:#4b1d28; }} .status {{ text-transform:uppercase; font-size:.75rem; }}
    .completed {{ color:#8ee6ac; }} .dropped {{ color:var(--muted); }} .empty-row,.empty {{ color:var(--muted); }}
    details {{ margin-bottom:2rem; }} summary {{ cursor:pointer; color:var(--muted); }}
    footer {{ color:var(--muted); padding:0 0 3rem; font-size:.9rem; }}
    @media (max-width:760px) {{ .grid,.two {{ grid-template-columns:1fr; }} header {{ align-items:start;
      flex-direction:column; }} li {{ flex-direction:column; }} }}
  </style>
</head>
<body>
  <header>
    <div><p class="kicker">Private · local · deliberate</p><h1>Earth Game</h1>
      <p>{html_text(profile["purpose"]) or "Choose a quest. Take the next action. Review and adapt."}</p></div>
    <div><span class="eyebrow">{review_label}</span> · <a href="/export">Export JSON</a></div>
  </header>
  <main>
    {error_html}
    {current_html}
    <div class="grid">
      <section><h3>Planned quests</h3><ul>{planned_html}</ul></section>
      <section><h3>Open loops</h3><ul>{loops_html}</ul>
        <form class="stack" method="post" action="/loop/add">{csrf_field(token)}
          <label>Capture an open loop<input name="description" required maxlength="1000"></label>
          <button type="submit">Capture</button>
        </form>
      </section>
    </div>

    <section><h3>Create a quest</h3>
      <form class="stack" method="post" action="/quest/add">{csrf_field(token)}
        <div class="two">
          <label>Title<input name="title" required maxlength="300"></label>
          <label>Next action<input name="next_action" required maxlength="1000"></label>
        </div>
        <label>Why<textarea name="why" maxlength="4000"></textarea></label>
        <div class="two">
          <label>Pillar<select name="pillar">{pillar_options}</select></label>
          <label>Driver<select name="driver">{driver_options}</select></label>
        </div>
        <label>Horizon<input name="horizon" maxlength="200" placeholder="this month"></label>
        <button type="submit">Add to planned quests</button>
      </form>
    </section>

    <section><h3>Character</h3>
      <form class="stack" method="post" action="/character">{csrf_field(token)}
        <div class="two">
          <label>Values<textarea name="values_text">{html_text(profile["values_text"])}</textarea></label>
          <label>Strengths<textarea name="strengths">{html_text(profile["strengths"])}</textarea></label>
          <label>Frictions<textarea name="frictions">{html_text(profile["frictions"])}</textarea></label>
          <label>Purpose<textarea name="purpose">{html_text(profile["purpose"])}</textarea></label>
        </div>
        <label>Anti-vision<textarea name="anti_vision">{html_text(profile["anti_vision"])}</textarea></label>
        <button type="submit">Save character</button>
      </form>
    </section>

    <section><h3>Weekly review</h3>
      <form class="stack" method="post" action="/review">{csrf_field(token)}
        <label>Where did love or connection guide you?<textarea name="love_connection"></textarea></label>
        <label>What changed, and how did you adapt?<textarea name="adaptation"></textarea></label>
        <label>Is the current quest authentic and aligned?<textarea name="alignment"></textarea></label>
        <label>What did you contribute?<textarea name="contribution"></textarea></label>
        <label>What next action or pillar now matters?<textarea name="next_action"></textarea></label>
        <label><span><input type="checkbox" name="update_quest" value="1" style="width:auto">
          Use that answer as the current quest's next action</span></label>
        <button type="submit">Save review</button>
      </form>
    </section>

    <details><summary>Completed and dropped quests ({len(history)})</summary><ul>{history_html}</ul></details>
  </main>
  <footer>Served only to this browser session on this computer. Stop with Ctrl-C.</footer>
</body>
</html>"""


def web_form_id(form):
    try:
        record_id = int(form.get("id", ""))
    except ValueError as error:
        raise EarthError("invalid record ID") from error
    if record_id < 1:
        raise EarthError("invalid record ID")
    return record_id


def mutate_web(db, path, form):
    if path == "/character":
        update_character(
            db,
            {
                field: form.get(field, "")
                for field in (
                    "values_text",
                    "strengths",
                    "frictions",
                    "purpose",
                    "anti_vision",
                )
            },
        )
    elif path == "/quest/add":
        create_quest(
            db,
            form.get("title"),
            form.get("next_action"),
            form.get("why", ""),
            form.get("pillar") or None,
            form.get("driver") or None,
            form.get("horizon", ""),
        )
    elif path == "/quest/start":
        start_quest(db, web_form_id(form))
    elif path == "/quest/done":
        complete_quest(db, web_form_id(form))
    elif path == "/quest/drop":
        drop_quest(db, web_form_id(form))
    elif path == "/loop/add":
        create_loop(db, form.get("description"))
    elif path == "/loop/close":
        close_loop(db, web_form_id(form))
    elif path == "/review":
        save_review(
            db,
            {
                field: form.get(field, "")
                for field in (
                    "love_connection",
                    "adaptation",
                    "alignment",
                    "contribution",
                    "next_action",
                )
            },
            form.get("update_quest") == "1",
        )
    else:
        raise EarthError("unknown action")


def web_server(port):
    csrf_token = secrets.token_urlsafe(32)
    access_key = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        server_version = "EarthGame"
        sys_version = ""

        def trusted_host(self):
            port_number = self.server.server_port
            return self.headers.get("Host") in {
                f"127.0.0.1:{port_number}",
                f"localhost:{port_number}",
            }

        def authenticated(self):
            try:
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
            except CookieError:
                return False
            session = cookies.get("earth_session")
            return bool(session) and secrets.compare_digest(session.value, access_key)

        def security_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                "base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")

        def respond(self, status, content, content_type="text/html; charset=utf-8"):
            body = content.encode("utf-8") if isinstance(content, str) else content
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.security_headers()
            self.end_headers()
            self.wfile.write(body)

        def redirect(self):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.security_headers()
            self.end_headers()

        def establish_session(self):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie",
                f"earth_session={access_key}; HttpOnly; SameSite=Strict; Path=/",
            )
            self.send_header("Content-Length", "0")
            self.security_headers()
            self.end_headers()

        def reject_untrusted(self):
            if not self.trusted_host():
                self.respond(
                    HTTPStatus.BAD_REQUEST,
                    "Untrusted Host",
                    "text/plain; charset=utf-8",
                )
                return True
            if not self.authenticated():
                self.respond(
                    HTTPStatus.UNAUTHORIZED,
                    "Open the private URL printed by 'earth web'.",
                    "text/plain; charset=utf-8",
                )
                return True
            return False

        def read_form(self):
            if not self.headers.get("Content-Type", "").startswith(
                "application/x-www-form-urlencoded"
            ):
                self.respond(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "Form data required",
                    "text/plain; charset=utf-8",
                )
                return None
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.respond(
                    HTTPStatus.LENGTH_REQUIRED,
                    "Content-Length required",
                    "text/plain; charset=utf-8",
                )
                return None
            if length < 0 or length > 65536:
                self.respond(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Request too large",
                    "text/plain; charset=utf-8",
                )
                return None
            try:
                values = parse_qs(
                    self.rfile.read(length).decode("utf-8"),
                    keep_blank_values=True,
                    max_num_fields=50,
                )
            except (UnicodeError, ValueError):
                self.respond(
                    HTTPStatus.BAD_REQUEST,
                    "Invalid form data",
                    "text/plain; charset=utf-8",
                )
                return None
            form = {key: value[-1] for key, value in values.items()}
            if not secrets.compare_digest(form.get("csrf", ""), csrf_token):
                self.respond(
                    HTTPStatus.FORBIDDEN,
                    "Invalid CSRF token",
                    "text/plain; charset=utf-8",
                )
                return None
            return form

        def do_GET(self):
            if not self.trusted_host():
                self.respond(
                    HTTPStatus.BAD_REQUEST,
                    "Untrusted Host",
                    "text/plain; charset=utf-8",
                )
                return
            parts = urlsplit(self.path)
            supplied_key = parse_qs(parts.query).get("key", [""])[-1]
            if parts.path == "/" and secrets.compare_digest(supplied_key, access_key):
                self.establish_session()
                return
            if self.reject_untrusted():
                return
            try:
                with database() as db:
                    if parts.path == "/":
                        self.respond(HTTPStatus.OK, render_web(db, csrf_token))
                    elif parts.path == "/export":
                        output = exported_json(db).encode("utf-8")
                        self.send_response(HTTPStatus.OK)
                        self.send_header(
                            "Content-Type", "application/json; charset=utf-8"
                        )
                        self.send_header(
                            "Content-Disposition",
                            'attachment; filename="earth-export.json"',
                        )
                        self.send_header("Content-Length", str(len(output)))
                        self.security_headers()
                        self.end_headers()
                        self.wfile.write(output)
                    else:
                        self.respond(
                            HTTPStatus.NOT_FOUND,
                            "Not found",
                            "text/plain; charset=utf-8",
                        )
            except (EarthError, OSError, sqlite3.Error) as error:
                self.respond(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    html_text(error),
                    "text/plain; charset=utf-8",
                )

        def do_POST(self):
            if self.reject_untrusted():
                return
            path = urlsplit(self.path).path
            allowed = {
                "/character",
                "/quest/add",
                "/quest/start",
                "/quest/done",
                "/quest/drop",
                "/loop/add",
                "/loop/close",
                "/review",
            }
            if path not in allowed:
                self.respond(
                    HTTPStatus.NOT_FOUND,
                    "Not found",
                    "text/plain; charset=utf-8",
                )
                return
            form = self.read_form()
            if form is None:
                return
            try:
                with database() as db:
                    mutate_web(db, path, form)
                self.redirect()
            except EarthError as error:
                with database() as db:
                    self.respond(
                        HTTPStatus.BAD_REQUEST,
                        render_web(db, csrf_token, str(error)),
                    )
            except (OSError, sqlite3.Error) as error:
                self.respond(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    html_text(error),
                    "text/plain; charset=utf-8",
                )

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.access_key = access_key
    return server


def serve(port, open_browser=True):
    with database():
        pass
    server = web_server(port)
    url = f"http://127.0.0.1:{server.server_port}/?key={server.access_key}"
    print(f"Earth Game web UI: {url}", flush=True)
    print("Press Ctrl-C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
    finally:
        server.server_close()
