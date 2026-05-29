"""Read-only ContentOps dashboard for non-technical team members.

A single self-refreshing web page that answers, at a glance:
  - Where is everything in the pipeline? (funnel from the Google Sheet tracker)
  - Is the agent healthy? (run success rate, latency, provider fallbacks)
  - Is quality being enforced? (gate pass-rate + which rules fail most)
  - What happened recently? (runs + review decisions)

No build step, no JS framework — server-rendered HTML + a meta refresh. Pulls
content state from the tracker and ops state from the local SQLite telemetry DB.

Run:  python main.py dashboard      (or: python dashboard.py)
"""

from __future__ import annotations

import logging
from functools import wraps

import observability
from config import (
    CONTENTOPS_SHEET_NAME,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DASHBOARD_TOKEN,
)
from flask import Flask, Response, jsonify, render_template_string, request

log = logging.getLogger(__name__)
app = Flask(__name__)

# Canonical pipeline order for the funnel. Off-track states are shown separately.
_FUNNEL = ["Idea", "Draft", "Needs Review", "Approved", "Scheduled", "Published"]
_OFF_TRACK = ["Needs Revision", "Rejected"]


def _require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not DASHBOARD_TOKEN:
            return fn(*args, **kwargs)
        supplied = request.args.get("token", "")
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            supplied = auth[7:].strip()
        if supplied != DASHBOARD_TOKEN:
            return Response("Unauthorized — append ?token=… to the URL.", status=401)
        return fn(*args, **kwargs)

    return wrapper


def _pipeline_snapshot() -> dict:
    """Read the tracker and bucket rows by status + bucket. Degrades gracefully."""
    try:
        from tools.sheets import read_tracker

        data = read_tracker(limit=10000)
        if "error" in data:
            return {"error": data["error"], "funnel": [], "off_track": [],
                    "buckets": [], "total": 0}
        rows = data.get("rows", [])
    except Exception as e:  # creds missing, offline, etc.
        return {"error": str(e), "funnel": [], "off_track": [], "buckets": [], "total": 0}

    status_counts: dict = {}
    bucket_counts: dict = {}
    for r in rows:
        status = str(r.get("Status", "") or "Unknown").strip() or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        bucket = str(r.get("Bucket", "") or "Unassigned").strip() or "Unassigned"
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    total = len(rows)
    funnel = [{"label": s, "count": status_counts.get(s, 0),
               "pct": round(100 * status_counts.get(s, 0) / total) if total else 0}
              for s in _FUNNEL]
    off_track = [{"label": s, "count": status_counts.get(s, 0)} for s in _OFF_TRACK]
    # Surface any statuses we don't model so nothing is silently hidden.
    other = {s: c for s, c in status_counts.items()
             if s not in _FUNNEL and s not in _OFF_TRACK}
    buckets = sorted(
        ({"label": b, "count": c} for b, c in bucket_counts.items()),
        key=lambda x: x["count"], reverse=True,
    )
    return {"error": "", "funnel": funnel, "off_track": off_track, "other": other,
            "buckets": buckets, "total": total}


@app.route("/healthz")
def healthz():
    """Liveness + telemetry-store check (no token required)."""
    try:
        observability.ops_metrics(window_hours=1)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/metrics")
@_require_token
def api_metrics():
    return jsonify({
        "pipeline": _pipeline_snapshot(),
        "ops": observability.ops_metrics(),
        "gate_violations": observability.gate_violation_breakdown(),
    })


@app.route("/")
@_require_token
def index():
    pipeline = _pipeline_snapshot()
    ops = observability.ops_metrics()
    violations = observability.gate_violation_breakdown()
    runs = observability.recent_runs(limit=15)
    approvals = observability.recent_events(kind="approval", limit=10)
    return render_template_string(
        _TEMPLATE,
        pipeline=pipeline,
        ops=ops,
        violations=violations,
        runs=runs,
        approvals=approvals,
        sheet_name=CONTENTOPS_SHEET_NAME,
        token_qs=(f"?token={DASHBOARD_TOKEN}" if DASHBOARD_TOKEN else ""),
    )


def start_dashboard() -> None:
    observability.init_db()
    log.info("ContentOps dashboard on http://%s:%s", DASHBOARD_HOST, DASHBOARD_PORT)
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT)


_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>ContentOps Dashboard</title>
<style>
  :root {
    --bg:#0f172a; --card:#1e293b; --ink:#e2e8f0; --muted:#94a3b8;
    --accent:#38bdf8; --good:#34d399; --warn:#fbbf24; --bad:#f87171; --bar:#334155;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:var(--bg); color:var(--ink); }
  header { padding:20px 28px; border-bottom:1px solid #233047;
           display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
  header h1 { font-size:20px; margin:0; }
  header .sub { color:var(--muted); font-size:13px; }
  .wrap { padding:24px 28px; max-width:1180px; margin:0 auto; }
  .grid { display:grid; gap:18px; }
  .kpis { grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); margin-bottom:22px; }
  .card { background:var(--card); border:1px solid #233047; border-radius:14px; padding:18px 20px; }
  .kpi .n { font-size:30px; font-weight:700; line-height:1.1; }
  .kpi .l { color:var(--muted); font-size:12px; text-transform:uppercase;
            letter-spacing:.05em; margin-top:6px; }
  .kpi .sub { font-size:12px; margin-top:4px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.06em;
       color:var(--muted); margin:0 0 14px; }
  .cols { display:grid; grid-template-columns:1.3fr 1fr; gap:18px; }
  @media (max-width:840px){ .cols{ grid-template-columns:1fr; } }
  .funnel-row { display:flex; align-items:center; gap:12px; margin:10px 0; }
  .funnel-row .lab { width:120px; font-size:13px; color:var(--ink); }
  .funnel-row .track { flex:1; background:var(--bar); border-radius:8px; height:26px; position:relative; }
  .funnel-row .fill { background:linear-gradient(90deg,#0ea5e9,#38bdf8);
                      height:100%; border-radius:8px; min-width:2px; }
  .funnel-row .val { width:46px; text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }
  .pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px;
          font-weight:600; }
  .pill.good{ background:rgba(52,211,153,.15); color:var(--good); }
  .pill.warn{ background:rgba(251,191,36,.15); color:var(--warn); }
  .pill.bad{ background:rgba(248,113,113,.15); color:var(--bad); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:7px 8px; border-bottom:1px solid #233047; }
  th { color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase; }
  td.mono { font-family:ui-monospace,Menlo,monospace; color:var(--muted); }
  .tag { font-size:11px; padding:2px 8px; border-radius:6px; }
  .tag.success{ background:rgba(52,211,153,.15); color:var(--good); }
  .tag.error{ background:rgba(248,113,113,.15); color:var(--bad); }
  .tag.running{ background:rgba(56,189,248,.15); color:var(--accent); }
  .bars .b { display:flex; align-items:center; gap:10px; margin:7px 0; font-size:13px; }
  .bars .b .lab{ width:200px; } .bars .b .tk{ flex:1; background:var(--bar); height:16px; border-radius:5px;}
  .bars .b .fl{ background:#a78bfa; height:100%; border-radius:5px; }
  .err { background:rgba(248,113,113,.12); border:1px solid var(--bad);
         color:#fecaca; padding:10px 14px; border-radius:10px; font-size:13px; margin-bottom:16px; }
  .foot { color:var(--muted); font-size:12px; margin-top:24px; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>📊 ContentOps</h1>
  <span class="sub">Content pipeline &amp; agent health · tracker: {{ sheet_name }} · auto-refreshes every 30s</span>
</header>
<div class="wrap">

  {% set ops = ops %}
  {% set sr = ops.run_success_rate %}
  {% set gr = ops.gate_pass_rate %}
  <div class="grid kpis">
    <div class="card kpi"><div class="n">{{ pipeline.total }}</div><div class="l">Items in tracker</div></div>
    <div class="card kpi"><div class="n">{{ ops.runs_total }}</div><div class="l">Agent runs (7d)</div>
      <div class="sub"><span class="pill {{ 'good' if sr>=95 else 'warn' if sr>=80 else 'bad' }}">{{ sr }}% ok</span></div></div>
    <div class="card kpi"><div class="n">{{ gr }}%</div><div class="l">Quality-gate pass</div>
      <div class="sub muted">{{ ops.gate_pass }}/{{ ops.gate_total }} drafts</div></div>
    <div class="card kpi"><div class="n">{{ (ops.avg_duration_ms/1000)|round(1) }}s</div><div class="l">Avg run time</div>
      <div class="sub muted">p95 {{ (ops.p95_duration_ms/1000)|round(1) }}s</div></div>
    <div class="card kpi"><div class="n">{{ ops.output_tokens }}</div><div class="l">Output tokens (7d)</div></div>
    <div class="card kpi"><div class="n">{{ ops.provider_fallbacks }}</div><div class="l">Provider fallbacks</div>
      <div class="sub"><span class="pill {{ 'good' if ops.provider_fallbacks==0 else 'warn' }}">{{ 'stable' if ops.provider_fallbacks==0 else 'check' }}</span></div></div>
  </div>

  {% if pipeline.error %}
    <div class="err">⚠️ Could not read the content tracker: {{ pipeline.error }} — showing agent metrics only.</div>
  {% endif %}

  <div class="cols">
    <div class="card">
      <h2>Content pipeline</h2>
      {% for row in pipeline.funnel %}
        <div class="funnel-row">
          <div class="lab">{{ row.label }}</div>
          <div class="track"><div class="fill" style="width:{{ row.pct }}%"></div></div>
          <div class="val">{{ row.count }}</div>
        </div>
      {% endfor %}
      {% if pipeline.off_track %}
        <div style="margin-top:14px;color:var(--muted);font-size:12px;">
          {% for o in pipeline.off_track %}
            <span class="pill {{ 'warn' if o.label=='Needs Revision' else 'bad' }}">{{ o.label }}: {{ o.count }}</span>
          {% endfor %}
          {% for k,v in (pipeline.other or {}).items() %}<span class="pill">{{ k }}: {{ v }}</span>{% endfor %}
        </div>
      {% endif %}
    </div>

    <div class="card">
      <h2>By content bucket</h2>
      <div class="bars">
        {% set maxb = (pipeline.buckets|map(attribute='count')|max) if pipeline.buckets else 1 %}
        {% for b in pipeline.buckets %}
          <div class="b"><div class="lab">{{ b.label }}</div>
            <div class="tk"><div class="fl" style="width:{{ (100*b.count/maxb)|round }}%"></div></div>
            <div>{{ b.count }}</div></div>
        {% else %}
          <div class="sub muted">No rows yet.</div>
        {% endfor %}
      </div>
    </div>
  </div>

  <div class="cols" style="margin-top:18px;">
    <div class="card">
      <h2>Recent agent runs</h2>
      <table>
        <tr><th>When</th><th>Command</th><th>By</th><th>Status</th><th>Time</th></tr>
        {% for r in runs %}
          <tr>
            <td class="mono">{{ r.ts_start[:19].replace('T',' ') }}</td>
            <td>{{ r.command }}</td>
            <td class="mono">{{ r.user_id or '—' }}</td>
            <td><span class="tag {{ r.status }}">{{ r.status }}</span></td>
            <td class="mono">{{ ((r.duration_ms or 0)/1000)|round(1) }}s</td>
          </tr>
        {% else %}
          <tr><td colspan="5" class="sub muted">No runs recorded yet.</td></tr>
        {% endfor %}
      </table>
    </div>

    <div class="card">
      <h2>Quality-gate blocks (top rules)</h2>
      <table>
        <tr><th>Rule</th><th>Times blocked</th></tr>
        {% for v in violations %}
          <tr><td>{{ v.rule }}</td><td class="mono">{{ v.count }}</td></tr>
        {% else %}
          <tr><td colspan="2" class="sub muted">No gate blocks — clean drafts. 🎉</td></tr>
        {% endfor %}
      </table>
      <h2 style="margin-top:18px;">Recent review decisions</h2>
      <table>
        <tr><th>When</th><th>ID</th><th>Decision</th></tr>
        {% for a in approvals %}
          <tr><td class="mono">{{ a.ts[:19].replace('T',' ') }}</td>
              <td class="mono">{{ a.detail.idea_id if a.detail else '' }}</td>
              <td>{{ a.name }}</td></tr>
        {% else %}
          <tr><td colspan="3" class="sub muted">No decisions yet.</td></tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <div class="foot">ContentOps · tool failure rate {{ ops.tool_failure_rate }}% over {{ ops.tool_calls }} tool calls · window {{ ops.window_hours }}h</div>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    start_dashboard()
