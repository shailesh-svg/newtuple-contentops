"""Interactive ContentOps dashboard — a WebInterface adapter over ReviewService.

Stakeholders sign in, watch the pipeline, open an item, and (per RBAC) edit or
approve/revise/reject it. Every write goes through the platform-neutral
``review_service`` exactly like the Slack adapter — same RBAC, same audit trail,
no duplicated logic. Identity comes from ``identity.resolve(...)`` so a person's
role is the same here as in Slack.

Two ways to sign in (both built in):
  - Sign in with Slack (OpenID Connect) — production identity. Enabled when
    SLACK_CLIENT_ID/SECRET are set.
  - Dev login (Slack user id + DASHBOARD_TOKEN) — for local use before OAuth is
    configured. Auto-disabled once OAuth is configured (unless DASHBOARD_DEV_LOGIN=true).

Run:  python main.py dashboard
"""

from __future__ import annotations

import logging
import secrets
from functools import wraps

import identity
import observability
import quality_gate
import review_service
import schema
from config import (
    CONTENTOPS_SHEET_NAME,
    DASHBOARD_BASE_URL,
    DASHBOARD_DEV_LOGIN,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DASHBOARD_SECRET_KEY,
    DASHBOARD_TOKEN,
    SLACK_CLIENT_ID,
    SLACK_CLIENT_SECRET,
)
from flask import (
    Flask,
    abort,
    flash,
    get_flashed_messages,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

log = logging.getLogger(__name__)
app = Flask(__name__)
app.secret_key = DASHBOARD_SECRET_KEY or secrets.token_hex(32)

_FUNNEL = ["Idea", "Draft", "Needs Review", "Approved", "Scheduled", "Published"]
_OFF_TRACK = ["Needs Revision", "Rejected"]
_REVIEW_STATUSES = {"Needs Review", "Needs Revision", "Draft", "Idea"}
# Fields a stakeholder may edit from the dashboard (alias → normalised by schema).
_EDITABLE = [
    ("title", "Working Title / Hook"),
    ("bucket", "Bucket"),
    ("key_message", "Key Message"),
    ("draft_text", "Draft Text"),
]


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _oauth_enabled() -> bool:
    return bool(SLACK_CLIENT_ID and SLACK_CLIENT_SECRET)


def _dev_login_enabled() -> bool:
    flag = (DASHBOARD_DEV_LOGIN or "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    # Default: dev login is available only when OAuth isn't configured.
    return not _oauth_enabled()


def current_principal():
    """Re-resolve the logged-in actor each request so role changes take effect."""
    uid = session.get("uid")
    if not uid:
        return None
    return identity.resolve(session.get("platform", "slack"), uid,
                            session.get("display_name", ""))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_principal() is None:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def _csrf_token() -> str:
    tok = session.get("csrf")
    if not tok:
        tok = secrets.token_hex(16)
        session["csrf"] = tok
    return tok


def _check_csrf() -> None:
    if not session.get("csrf") or request.form.get("csrf") != session.get("csrf"):
        abort(400, "CSRF token mismatch")


# ─── Data helpers ─────────────────────────────────────────────────────────────

def _pipeline_snapshot() -> dict:
    try:
        from tools.sheets import read_tracker
        data = read_tracker(limit=10000)
        if "error" in data:
            return {"error": data["error"], "funnel": [], "off_track": [],
                    "buckets": [], "total": 0, "items": []}
        rows = data.get("rows", [])
    except Exception as e:
        return {"error": str(e), "funnel": [], "off_track": [], "buckets": [],
                "total": 0, "items": []}

    pk = schema.primary_key()
    status_counts, bucket_counts, items = {}, {}, []
    for r in rows:
        status = str(r.get("Status", "") or "Unknown").strip() or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        bucket = str(r.get("Bucket", "") or "Unassigned").strip() or "Unassigned"
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        cid = str(r.get(pk, "")).strip()
        if cid:
            items.append({"id": cid, "title": r.get("Working Title / Hook", "") or "(untitled)",
                          "status": status, "bucket": bucket})

    total = len(rows)
    funnel = [{"label": s, "count": status_counts.get(s, 0),
               "pct": round(100 * status_counts.get(s, 0) / total) if total else 0}
              for s in _FUNNEL]
    off_track = [{"label": s, "count": status_counts.get(s, 0)} for s in _OFF_TRACK]
    other = {s: c for s, c in status_counts.items() if s not in _FUNNEL and s not in _OFF_TRACK}
    buckets = sorted(({"label": b, "count": c} for b, c in bucket_counts.items()),
                     key=lambda x: x["count"], reverse=True)
    # Review-needed items first, capped so a 1000-row sheet stays usable.
    items.sort(key=lambda i: (i["status"] not in _REVIEW_STATUSES, i["title"]))
    return {"error": "", "funnel": funnel, "off_track": off_track, "other": other,
            "buckets": buckets, "total": total, "items": items[:50]}


def _get_item(content_id: str):
    from tools.sheets import read_tracker
    data = read_tracker(limit=10000)
    if "error" in data:
        return None
    pk = schema.primary_key()
    for r in data.get("rows", []):
        if str(r.get(pk, "")).strip() == content_id:
            return r
    return None


# ─── Public routes ────────────────────────────────────────────────────────────

@app.route("/healthz")
def healthz():
    try:
        observability.ops_metrics(window_hours=1)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not _dev_login_enabled():
            abort(403, "Dev login is disabled")
        uid = (request.form.get("user_id") or "").strip()
        if not uid:
            flash("Enter your Slack user id (e.g. U0123ABCD).")
            return redirect(url_for("login"))
        if DASHBOARD_TOKEN and request.form.get("token") != DASHBOARD_TOKEN:
            flash("Invalid access token.")
            return redirect(url_for("login"))
        session.clear()
        session["uid"] = uid
        session["platform"] = "slack"     # reuse Slack-keyed RBAC
        session["display_name"] = request.form.get("display_name", "").strip() or uid
        log.info("dev login: %s", uid)
        return redirect(url_for("index"))

    return render_template_string(
        _LOGIN_TEMPLATE,
        oauth_enabled=_oauth_enabled(),
        dev_login=_dev_login_enabled(),
        token_required=bool(DASHBOARD_TOKEN),
        insecure=(not DASHBOARD_TOKEN and _dev_login_enabled() and not _oauth_enabled()),
        messages=get_flashed_messages(),
        css=_CSS,
    )


@app.route("/auth/slack/start")
def slack_start():
    if not _oauth_enabled():
        abort(404)
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    from urllib.parse import urlencode
    params = urlencode({
        "response_type": "code",
        "scope": "openid profile",
        "client_id": SLACK_CLIENT_ID,
        "state": state,
        "redirect_uri": _redirect_uri(),
    })
    return redirect(f"https://slack.com/openid/connect/authorize?{params}")


@app.route("/auth/slack/callback")
def slack_callback():
    if not _oauth_enabled():
        abort(404)
    if not request.args.get("state") or request.args.get("state") != session.get("oauth_state"):
        abort(400, "Invalid OAuth state")
    code = request.args.get("code", "")
    try:
        from slack_sdk import WebClient
        client = WebClient()
        tok = client.openid_connect_token(
            client_id=SLACK_CLIENT_ID, client_secret=SLACK_CLIENT_SECRET,
            code=code, redirect_uri=_redirect_uri(),
        )
        info = client.openid_connect_userInfo(token=tok["access_token"])
        user_id = info.get("https://slack.com/user_id") or info.get("sub", "")
        display = info.get("name", "") or user_id
    except Exception as e:
        log.warning("slack oauth failed: %s", e)
        flash("Sign-in with Slack failed. Try again or use dev login.")
        return redirect(url_for("login"))

    session.clear()
    session["uid"] = user_id
    session["platform"] = "slack"
    session["display_name"] = display
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _redirect_uri() -> str:
    base = (DASHBOARD_BASE_URL or request.url_root).rstrip("/")
    return f"{base}/auth/slack/callback"


# ─── Authenticated routes ─────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    me = current_principal()
    pipeline = _pipeline_snapshot()
    ops = observability.ops_metrics()
    violations = observability.gate_violation_breakdown()
    runs = observability.recent_runs(limit=12)
    return render_template_string(
        _OVERVIEW_TEMPLATE, me=me, pipeline=pipeline, ops=ops, violations=violations,
        runs=runs, sheet_name=CONTENTOPS_SHEET_NAME, css=_CSS,
        messages=get_flashed_messages(),
    )


@app.route("/item/<content_id>")
@login_required
def item(content_id):
    me = current_principal()
    row = _get_item(content_id)
    if row is None:
        abort(404)
    return render_template_string(
        _ITEM_TEMPLATE, me=me, row=row, content_id=content_id,
        pk=schema.primary_key(), buckets=list(quality_gate.load_valid_buckets()),
        editable=_EDITABLE, csrf=_csrf_token(), css=_CSS,
        messages=get_flashed_messages(),
    )


@app.route("/item/<content_id>/decide", methods=["POST"])
@login_required
def decide(content_id):
    _check_csrf()
    me = current_principal()
    result = review_service.decide(
        me, content_id, request.form.get("decision", ""),
        notes=request.form.get("notes", "").strip(), source="web",
    )
    flash(result.message or result.error or "Done.")
    return redirect(url_for("item", content_id=content_id))


@app.route("/item/<content_id>/edit", methods=["POST"])
@login_required
def edit(content_id):
    _check_csrf()
    me = current_principal()
    current = _get_item(content_id) or {}
    fields = {}
    for form_key, column in _EDITABLE:
        new = request.form.get(form_key)
        if new is not None and new != (current.get(column, "") or ""):
            fields[form_key] = new
    if not fields:
        flash("No changes to save.")
        return redirect(url_for("item", content_id=content_id))
    result = review_service.edit(me, content_id, fields, source="web")
    flash(result.message or result.error or "Done.")
    return redirect(url_for("item", content_id=content_id))


@app.route("/api/metrics")
@login_required
def api_metrics():
    return jsonify({"pipeline": _pipeline_snapshot(), "ops": observability.ops_metrics(),
                    "gate_violations": observability.gate_violation_breakdown()})


def start_dashboard() -> None:
    observability.init_db()
    if not DASHBOARD_SECRET_KEY:
        log.warning("DASHBOARD_SECRET_KEY not set — using a random key (sessions reset on restart)")
    log.info("ContentOps dashboard on http://%s:%s (oauth=%s, dev_login=%s)",
             DASHBOARD_HOST, DASHBOARD_PORT, _oauth_enabled(), _dev_login_enabled())
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT)


# ─── Templates ────────────────────────────────────────────────────────────────

_CSS = """
:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;
--good:#34d399;--warn:#fbbf24;--bad:#f87171;--bar:#334155;}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{padding:16px 28px;border-bottom:1px solid #233047;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header h1{font-size:19px;margin:0}header .sub{color:var(--muted);font-size:13px}
header .spacer{flex:1}.who{font-size:13px;color:var(--muted)}
.wrap{padding:22px 28px;max-width:1180px;margin:0 auto}
.grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:20px}
.card{background:var(--card);border:1px solid #233047;border-radius:14px;padding:16px 18px}
.kpi .n{font-size:28px;font-weight:700}.kpi .l{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em;margin-top:6px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 12px}
.cols{display:grid;grid-template-columns:1.3fr 1fr;gap:16px}@media(max-width:840px){.cols{grid-template-columns:1fr}}
.funnel-row{display:flex;align-items:center;gap:12px;margin:9px 0}.funnel-row .lab{width:120px;font-size:13px}
.funnel-row .track{flex:1;background:var(--bar);border-radius:8px;height:24px}.funnel-row .fill{background:linear-gradient(90deg,#0ea5e9,#38bdf8);height:100%;border-radius:8px;min-width:2px}
.funnel-row .val{width:40px;text-align:right;font-weight:600}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
.pill.good{background:rgba(52,211,153,.15);color:var(--good)}.pill.warn{background:rgba(251,191,36,.15);color:var(--warn)}
.pill.bad{background:rgba(248,113,113,.15);color:var(--bad)}.pill.role{background:rgba(56,189,248,.15);color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #233047}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase}td.mono{font-family:ui-monospace,Menlo,monospace;color:var(--muted)}
.btn{display:inline-block;padding:9px 16px;border-radius:9px;border:1px solid #2b3a52;background:#22304a;color:var(--ink);font-size:14px;cursor:pointer}
.btn:hover{filter:brightness(1.1)}.btn.primary{background:#0ea5e9;border-color:#0ea5e9;color:#04222e}
.btn.danger{background:#7f1d1d;border-color:#991b1b;color:#fee2e2}.btn.warn{background:#78510a;border-color:#a16207}
input,textarea,select{width:100%;background:#0b1424;border:1px solid #2b3a52;color:var(--ink);border-radius:8px;padding:9px;font-size:14px;font-family:inherit}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 5px}
.flash{background:rgba(56,189,248,.12);border:1px solid var(--accent);color:#cffafe;padding:9px 14px;border-radius:10px;margin-bottom:14px;font-size:13px}
.err{background:rgba(248,113,113,.12);border:1px solid var(--bad);color:#fecaca;padding:9px 14px;border-radius:10px;margin-bottom:14px;font-size:13px}
.muted{color:var(--muted)}.row-actions form{display:inline}
.login{max-width:380px;margin:8vh auto}.login .card{padding:24px}
"""

_LOGIN_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ContentOps — Sign in</title>
<style>{{ css }}</style></head><body><div class="login">
<h1 style="text-align:center">📊 ContentOps</h1>
{% for m in messages %}<div class="err">{{ m }}</div>{% endfor %}
<div class="card">
  {% if oauth_enabled %}
    <a class="btn primary" style="display:block;text-align:center" href="{{ url_for('slack_start') }}">Sign in with Slack</a>
  {% endif %}
  {% if oauth_enabled and dev_login %}<p class="muted" style="text-align:center;margin:14px 0">or</p>{% endif %}
  {% if dev_login %}
    {% if insecure %}<div class="err">Dev login with no DASHBOARD_TOKEN set — identity is self-asserted. Not for real approvals.</div>{% endif %}
    <form method="post">
      <label>Slack user id</label>
      <input name="user_id" placeholder="U0123ABCD" autofocus>
      <label>Display name (optional)</label>
      <input name="display_name" placeholder="Alice">
      {% if token_required %}<label>Access token</label><input name="token" type="password">{% endif %}
      <button class="btn primary" style="width:100%;margin-top:16px" type="submit">Continue</button>
    </form>
    <p class="muted" style="font-size:12px;margin-top:12px">Dev login. Use “Sign in with Slack” in production.</p>
  {% endif %}
  {% if not oauth_enabled and not dev_login %}
    <p class="muted">No sign-in method configured. Set SLACK_CLIENT_ID/SECRET for Slack OAuth, or DASHBOARD_DEV_LOGIN=true (+ DASHBOARD_TOKEN) for dev login.</p>
  {% endif %}
</div></div></body></html>"""

_TOPBAR = """<header><h1>📊 ContentOps</h1><span class="sub">{{ sheet_name }}</span>
<span class="spacer"></span>
<span class="who">{{ me.display_name }} · <span class="pill role">{{ me.role }}</span></span>
<a class="btn" href="{{ url_for('logout') }}">Sign out</a></header>"""

_OVERVIEW_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>ContentOps</title><style>{{ css }}</style></head><body>
""" + _TOPBAR + """
<div class="wrap">
{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}
<div class="grid kpis">
  <div class="card kpi"><div class="n">{{ pipeline.total }}</div><div class="l">Items</div></div>
  <div class="card kpi"><div class="n">{{ ops.runs_total }}</div><div class="l">Runs (7d)</div></div>
  <div class="card kpi"><div class="n">{{ ops.gate_pass_rate }}%</div><div class="l">Gate pass</div></div>
  <div class="card kpi"><div class="n">{{ (ops.avg_duration_ms/1000)|round(1) }}s</div><div class="l">Avg run</div></div>
  <div class="card kpi"><div class="n">{{ ops.provider_fallbacks }}</div><div class="l">Fallbacks</div></div>
</div>
{% if pipeline.error %}<div class="err">Could not read tracker: {{ pipeline.error }}</div>{% endif %}
<div class="cols">
  <div class="card"><h2>Pipeline</h2>
    {% for r in pipeline.funnel %}<div class="funnel-row"><div class="lab">{{ r.label }}</div>
      <div class="track"><div class="fill" style="width:{{ r.pct }}%"></div></div><div class="val">{{ r.count }}</div></div>{% endfor %}
    <div style="margin-top:10px">{% for o in pipeline.off_track %}<span class="pill {{ 'warn' if o.label=='Needs Revision' else 'bad' }}">{{ o.label }}: {{ o.count }}</span> {% endfor %}
    {% for k,v in (pipeline.other or {}).items() %}<span class="pill">{{ k }}: {{ v }}</span> {% endfor %}</div>
  </div>
  <div class="card"><h2>Quality-gate blocks</h2><table><tr><th>Rule</th><th>#</th></tr>
    {% for v in violations %}<tr><td>{{ v.rule }}</td><td class="mono">{{ v.count }}</td></tr>
    {% else %}<tr><td colspan="2" class="muted">No blocks 🎉</td></tr>{% endfor %}</table></div>
</div>
<div class="card" style="margin-top:16px"><h2>Content items {% if pipeline['items'] %}<span class="muted">(review-needed first)</span>{% endif %}</h2>
  <table><tr><th>ID</th><th>Title</th><th>Bucket</th><th>Status</th><th></th></tr>
  {% for it in pipeline['items'] %}<tr>
    <td class="mono">{{ it.id }}</td><td>{{ it.title }}</td><td class="muted">{{ it.bucket }}</td>
    <td>{{ it.status }}</td><td><a href="{{ url_for('item', content_id=it.id) }}">open →</a></td></tr>
  {% else %}<tr><td colspan="5" class="muted">No items.</td></tr>{% endfor %}</table>
</div>
<div class="card" style="margin-top:16px"><h2>Recent runs</h2><table>
  <tr><th>When</th><th>Command</th><th>By</th><th>Status</th></tr>
  {% for r in runs %}<tr><td class="mono">{{ r.ts_start[:19].replace('T',' ') }}</td><td>{{ r.command }}</td>
    <td class="mono">{{ r.user_id or '—' }}</td><td>{{ r.status }}</td></tr>
  {% else %}<tr><td colspan="4" class="muted">No runs yet.</td></tr>{% endfor %}</table></div>
</div></body></html>"""

_ITEM_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ content_id }}</title>
<style>{{ css }}</style></head><body>
""" + _TOPBAR.replace("{{ sheet_name }}", "Item") + """
<div class="wrap">
<p><a href="{{ url_for('index') }}">← back to pipeline</a></p>
{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}
<div class="card">
  <h2>{{ content_id }} · {{ row.get('Status','') }}</h2>
  <div style="font-size:18px;font-weight:600;margin-bottom:8px">{{ row.get('Working Title / Hook','(untitled)') }}</div>
  <div class="muted" style="margin-bottom:12px">Bucket: {{ row.get('Bucket','—') }} · Channel: {{ row.get('Channel','—') }}
    {% if row.get('Approved By') %}· Reviewed by {{ row.get('Approved By') }}{% endif %}</div>
  <div style="white-space:pre-wrap;background:#0b1424;border:1px solid #2b3a52;border-radius:10px;padding:14px;font-size:14px">{{ row.get('Draft Text','') or row.get('Key Message','') }}</div>
  {% if row.get('Review Notes') %}<p class="muted" style="margin-top:10px">📝 {{ row.get('Review Notes') }}</p>{% endif %}
</div>

{% if me.can('approve') or me.can('reject') or me.can('revise') %}
<div class="card" style="margin-top:16px"><h2>Review</h2>
  <div class="row-actions" style="display:flex;gap:10px;flex-wrap:wrap">
    {% if me.can('approve') %}
    <form method="post" action="{{ url_for('decide', content_id=content_id) }}">
      <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="decision" value="approve">
      <button class="btn primary" type="submit">✅ Approve</button></form>{% endif %}
    {% if me.can('revise') %}
    <form method="post" action="{{ url_for('decide', content_id=content_id) }}">
      <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="decision" value="revise">
      <input type="hidden" name="notes" value="">
      <button class="btn warn" type="submit" onclick="this.form.notes.value=prompt('Revision notes:')||''">✏️ Request revision</button></form>{% endif %}
    {% if me.can('reject') %}
    <form method="post" action="{{ url_for('decide', content_id=content_id) }}">
      <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="decision" value="reject">
      <input type="hidden" name="notes" value="">
      <button class="btn danger" type="submit" onclick="this.form.notes.value=prompt('Reason for rejection:')||''">❌ Reject</button></form>{% endif %}
  </div></div>
{% endif %}

{% if me.can('edit') %}
<div class="card" style="margin-top:16px"><h2>Edit</h2>
  <form method="post" action="{{ url_for('edit', content_id=content_id) }}">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Working Title / Hook</label><input name="title" value="{{ row.get('Working Title / Hook','') }}">
    <label>Bucket</label><select name="bucket">
      {% for b in buckets %}<option {{ 'selected' if row.get('Bucket','')==b else '' }}>{{ b }}</option>{% endfor %}</select>
    <label>Key Message</label><input name="key_message" value="{{ row.get('Key Message','') }}">
    <label>Draft Text</label><textarea name="draft_text" rows="8">{{ row.get('Draft Text','') }}</textarea>
    <button class="btn primary" style="margin-top:14px" type="submit">Save changes</button>
  </form></div>
{% else %}<p class="muted">Your role ({{ me.role }}) can view but not edit this item.</p>{% endif %}
</div></body></html>"""


if __name__ == "__main__":
    start_dashboard()
