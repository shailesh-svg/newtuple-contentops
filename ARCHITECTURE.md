# ContentOps — Modular Architecture

ContentOps is built to be **plug-and-play over any system**. Two contracts make
that possible: a single **schema contract** for the data, and a **storage
adapter interface** for where that data lives. The agent, prompts, Slack layer,
and dashboard depend only on these contracts — never on a specific backend.

```
                ┌─────────────────────────────────────────────┐
   Slack /      │                 Agent core                  │
   CLI    ─────▶│  contentops_agent.py · prompts.py · main.py │
                └───────────────┬───────────────┬─────────────┘
                                │               │
                  quality_gate.py        tools/sheets.py  ◀── stable facade
                  (deterministic         (applies schema, delegates I/O)
                   content checks)               │
                                                 ▼
                              agent/schema.py  ◀── canonical contract
                              (loads tracker.schema.json)
                                                 │
                                                 ▼
                          tools/tracker_backends.py  ◀── adapter registry
                       ┌─────────────┬─────────────┬───────────────┐
                       ▼             ▼             ▼               ▼
                 SheetsBackend  AppsScript    JsonFileBackend   (your next
                 (service acct)  Backend      (no creds)         backend)
```

## 1. The schema contract — one source of truth

`contentops/schema/tracker.schema.json` is the **only** place the tracker shape
is defined: canonical column names, agent-facing aliases (`idea_id → Content
ID`), the status vocabulary + aliases (`new → Idea`), create-time defaults, and
header detection. It is versioned (`version` field).

`agent/schema.py` loads and validates it and exposes the helpers everything else
uses:

| Helper | Purpose |
|--------|---------|
| `normalize_field_name` / `normalize_fields` | alias → canonical column |
| `normalize_status` | any casing/alias → canonical status |
| `build_create_row` | full row for a new item, defaults + fallbacks applied |
| `is_header_row` | detect the header row in a messy sheet |
| `primary_key`, `column_names`, `canonical_statuses`, `schema_version` | introspection |

**Before:** the same field map was hand-duplicated in `sheets.py`
(`FIELD_ALIASES`), `ContentOpsAgent.gs` (`FIELD_MAP`), and two `append_idea`
column lists. **Now:** Python derives everything from the JSON. Change a field in
one place.

To evolve the schema: edit the JSON, bump `version`, run `pytest` (the contract
self-validates on load).

## 2. The storage adapter interface — plug in any system

`tools/tracker_backends.py` defines `TrackerBackend` (read / update / upsert /
get_schema) and a registry. `tools/sheets.py` is a thin facade: it normalises
inputs via the schema, then calls the active backend. Backends only do I/O and
speak canonical column names.

Shipped backends:

| `TRACKER_BACKEND` | Backend | Notes |
|-------------------|---------|-------|
| `sheets` | `SheetsBackend` | Google Sheets via service account |
| `apps_script` | `AppsScriptBackend` | Apps Script web-app bridge |
| `jsonfile` | `JsonFileBackend` | local JSON file — **no credentials**, ideal for dev/test/demos |

Selection: explicit `TRACKER_BACKEND` wins; otherwise it's derived from the
legacy `GOOGLE_AUTH_MODE` (so existing deployments keep working).

### Add a new backend (e.g. Notion, Airtable, Postgres) in 3 steps

```python
# tools/tracker_backends.py
class NotionBackend:
    def read(self, status, limit): ...      # -> {"rows": [...], "count": n} | {"error": ...}
    def update(self, content_id, fields): ...  # fields use canonical column names
    def upsert(self, row): ...                  # row uses canonical column names
    def get_schema(self): ...

_BACKENDS["notion"] = NotionBackend            # 2) register
# 3) set TRACKER_BACKEND=notion
```

No changes to the agent, prompts, Slack handlers, or dashboard are required —
they all go through the facade. `JsonFileBackend` is a complete worked example.

## 3. Security boundary (Apps Script bridge)

The Apps Script bridge (`agent/google-apps-script/ContentOpsAgent.gs`) is
config-driven via **Script Properties** (token + allowlists), not source
literals:

- `sheetId` / `folderId` are validated against `ALLOWED_SHEET_IDS` /
  `ALLOWED_FOLDER_IDS`; unknown IDs are rejected. A request can't reach an
  arbitrary spreadsheet or read an arbitrary Drive file.
- The token is compared in constant time; error responses never leak stack
  traces; `GET` is a tokenless health probe.

See `agent/google-apps-script/README.md`.

## 4. Verify

```bash
python agent/main.py doctor   # reports schema version + active backend
pytest                        # schema, backends (incl. JSON round-trip), gate, telemetry

# Try the credential-free backend end to end:
TRACKER_BACKEND=jsonfile TRACKER_JSON_FILE=/tmp/t.json \
  python agent/main.py update-status CNT-1 approved
```

Related docs: `OBSERVABILITY.md` (gate + telemetry + dashboard),
`TRACKER-SCHEMA-HARDENING.md` (history of the schema contract).
