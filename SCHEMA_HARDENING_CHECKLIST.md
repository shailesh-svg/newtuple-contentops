# Schema Hardening Checklist

## Completed

- [x] Added live tracker columns: `Content ID`, `Draft Text`, `Review Notes`, `Approved By`, `Approval Timestamp`
- [x] Updated local `.env.example` default sheet tab to `Content Tracker`
- [x] Updated `agent/tools/sheets.py` to map old agent fields into the live tracker schema
- [x] Added token-compatible Apps Script bridge code
- [x] Synced `APPS_SCRIPT_CODE.js` with canonical Apps Script source
- [x] Added a live tracker template CSV

## Still Manual

- [ ] Paste `agent/google-apps-script/ContentOpsAgent.gs` into the existing Apps Script project
- [ ] Preserve the existing `CONTENTOPS_TOKEN`
- [ ] Deploy a new web app version
- [ ] Run `python main.py doctor`
- [ ] Run `@contentops help`
- [ ] Test one approval update by `Content ID`

## Success Criteria

- `read_tracker(status="Needs Review")` returns rows with `Content ID`
- `write_tracker("<Content ID>", {"status": "Approved"})` updates the live row
- Slack approval replies update `Status`, `Review Notes`, `Approved By`, and `Approval Timestamp`
