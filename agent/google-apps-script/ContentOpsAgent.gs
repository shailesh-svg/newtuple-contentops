// ContentOps Agent — Google Apps Script bridge
// Deploy as Web App: Execute as Me, Access: Anyone with Google account (or Anyone)
// Set CONTENTOPS_TOKEN to a long random string and put the same value in agent/.env

const CONTENTOPS_TOKEN = 'CHANGE_ME_TO_A_LONG_RANDOM_TOKEN';

// ─── Router ──────────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (body.token !== CONTENTOPS_TOKEN) {
      return jsonResponse({ ok: false, error: 'Unauthorized' });
    }

    const action = body.action;
    if (action === 'health')           return jsonResponse({ ok: true,  data: { status: 'ok' } });
    if (action === 'get_schema')       return jsonResponse({ ok: true,  data: getSchema(body) });
    if (action === 'read_tracker')     return jsonResponse({ ok: true,  data: readTracker(body) });
    if (action === 'write_tracker')    return jsonResponse({ ok: true,  data: writeTracker(body) });
    if (action === 'append_idea')      return jsonResponse({ ok: true,  data: appendIdea(body) });
    if (action === 'upsert_tracker_row') return jsonResponse({ ok: true, data: upsertTrackerRow(body) });
    if (action === 'update_approval')  return jsonResponse({ ok: true,  data: updateApproval(body) });
    if (action === 'list_drive_files') return jsonResponse({ ok: true,  data: listDriveFiles(body) });
    if (action === 'read_drive_doc')   return jsonResponse({ ok: true,  data: readDriveDoc(body) });

    return jsonResponse({ ok: false, error: `Unknown action: ${action}` });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err && err.stack ? err.stack : err) });
  }
}

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

// ─── Sheet helpers ───────────────────────────────────────────────────────────

function openSheet_(sheetId, sheetName) {
  const ss = SpreadsheetApp.openById(sheetId);
  return ss.getSheetByName(sheetName) || ss.getSheets()[0];
}

/**
 * Find the header row index (1-based).
 * Handles sheets that have a title row above the actual column headers.
 * Looks for a row containing "Content ID" or at least 3 of the known markers.
 */
function findHeaderRow_(sheet) {
  const markers = ['Content ID', 'Status', 'Working Title / Hook', 'Bucket', 'idea_id'];
  const values = sheet.getDataRange().getValues();

  for (let i = 0; i < Math.min(values.length, 10); i++) {
    const row = values[i].map(String);
    if (row.indexOf('Content ID') >= 0) return i + 1;
    if (row.indexOf('idea_id') >= 0)    return i + 1;
    const matched = markers.filter(m => row.indexOf(m) >= 0).length;
    if (matched >= 3) return i + 1;
  }
  // Fallback: assume row 1 is headers
  return 1;
}

function getHeaders_(sheet) {
  const headerRow = findHeaderRow_(sheet);
  const lastCol = sheet.getLastColumn();
  return {
    headerRow,
    headers: sheet.getRange(headerRow, 1, 1, lastCol).getValues()[0].map(String),
  };
}

/**
 * Return the column name used for the primary ID field.
 * Supports both the old schema (idea_id) and the new schema (Content ID).
 */
function idColumnName_(headers) {
  if (headers.indexOf('Content ID') >= 0) return 'Content ID';
  if (headers.indexOf('idea_id') >= 0)    return 'idea_id';
  return null;
}

function findRowByIdValue_(sheet, headerRow, idColIndex, value) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= headerRow) return -1;
  const col = sheet.getRange(headerRow + 1, idColIndex + 1, lastRow - headerRow, 1).getValues();
  for (let i = 0; i < col.length; i++) {
    if (String(col[i][0]) === String(value)) return headerRow + 1 + i; // 1-based row
  }
  return -1;
}

function rowToObject_(headers, row) {
  const obj = {};
  headers.forEach((h, i) => { obj[h] = row[i] === undefined ? '' : row[i]; });
  return obj;
}

// ─── Status normalisation ────────────────────────────────────────────────────

function normalizeStatus_(raw) {
  const s = String(raw || '').toLowerCase().replace(/[-\s]+/g, '_');
  const map = {
    new: 'Idea', idea: 'Idea',
    draft: 'Draft',
    needs_review: 'Needs Review',
    needs_revision: 'Needs Revision', revise: 'Needs Revision',
    approved: 'Approved', approve: 'Approved',
    rejected: 'Rejected', reject: 'Rejected',
    scheduled: 'Scheduled',
    published: 'Published',
  };
  return map[s] || raw;
}

// ─── Field name normalisation ────────────────────────────────────────────────
// Accepts both old snake_case names (idea_id, title, …) and real column names.

const FIELD_MAP = {
  idea_id:          'Content ID',
  content_id:       'Content ID',
  title:            'Working Title / Hook',
  hook:             'Working Title / Hook',
  draft_text:       'Draft Text',
  bucket:           'Bucket',
  status:           'Status',
  reviewer:         'Approved By',
  approved_by:      'Approved By',
  review_notes:     'Review Notes',
  review_action_ts: 'Approval Timestamp',
  approval_ts:      'Approval Timestamp',
  source_link:      'Source / Input Link',
  raw_input:        'Key Message',
  key_message:      'Key Message',
  platform:         'Channel',
  published_url:    'Published URL',
  source_type:      'Series Theme',
  created_at:       'Publish Date',
  publish_date:     'Publish Date',
};

function normalizeFieldName_(name) {
  return FIELD_MAP[name] || name;
}

function normalizeFields_(fields) {
  const out = {};
  Object.keys(fields || {}).forEach(k => { out[normalizeFieldName_(k)] = fields[k]; });
  return out;
}

// ─── Actions ─────────────────────────────────────────────────────────────────

function getSchema(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const { headerRow, headers } = getHeaders_(sheet);
  const columns = {};
  headers.forEach((h, i) => { if (h) columns[h] = i + 1; });
  return { header_row: headerRow, columns };
}

function readTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const { headerRow, headers } = getHeaders_(sheet);
  const lastRow = sheet.getLastRow();

  if (lastRow <= headerRow) return { rows: [], count: 0 };

  const data = sheet.getRange(headerRow + 1, 1, lastRow - headerRow, headers.length).getValues();
  let rows = data.map(row => rowToObject_(headers, row));

  // Filter by status — case-insensitive, normalised
  if (body.status) {
    const target = normalizeStatus_(body.status).toLowerCase();
    rows = rows.filter(row => {
      const val = String(row['Status'] || row['status'] || '').toLowerCase();
      return val === target;
    });
  }

  // Filter out empty rows
  const idCol = idColumnName_(headers);
  if (idCol) rows = rows.filter(row => String(row[idCol] || '').trim() !== '');

  const limit = Number(body.limit || 30);
  return { rows: rows.slice(0, limit), count: rows.length };
}

function writeTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const { headerRow, headers } = getHeaders_(sheet);

  // Accept content_id or idea_id from the caller
  const contentId = String(body.content_id || body.idea_id || '').trim();
  if (!contentId) throw new Error('content_id (or idea_id) is required');

  const idColName = idColumnName_(headers);
  if (!idColName) throw new Error('No ID column found (expected "Content ID" or "idea_id")');

  const idColIndex = headers.indexOf(idColName);
  const targetRow = findRowByIdValue_(sheet, headerRow, idColIndex, contentId);
  if (targetRow < 0) throw new Error(`${idColName} not found: ${contentId}`);

  const fields = normalizeFields_(body.fields || {});
  if (fields['Status']) fields['Status'] = normalizeStatus_(fields['Status']);

  Object.keys(fields).forEach(colName => {
    const col = headers.indexOf(colName);
    if (col >= 0) sheet.getRange(targetRow, col + 1).setValue(fields[colName]);
  });

  return { updated: contentId, fields: Object.keys(fields) };
}

function appendIdea(body) {
  // Build a row using the real column names, with fallbacks for old field names
  const contentId = body.content_id || body.idea_id || '';
  const row = {
    'Content ID':          contentId,
    'Publish Date':        new Date().toISOString().slice(0, 10),
    'Bucket':              body.bucket || '',
    'Series Theme':        body.source_type || 'manual',
    'Working Title / Hook': body.title || '',
    'Audience Intent':     'Educate and build trust',
    'Key Message':         body.raw_input || body.key_message || '',
    'Draft Text':          body.raw_input || body.key_message || '',
    'Format':              'Text Post',
    'Channel':             'LinkedIn',
    'Status':              normalizeStatus_(body.status || 'Idea'),
    'Priority':            'Medium',
    'CTA Type':            'Start a conversation',
  };
  return upsertTrackerRow(Object.assign({}, body, { row }));
}

function upsertTrackerRow(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const { headerRow, headers } = getHeaders_(sheet);

  const rowMap = body.row || {};
  const contentId = String(rowMap['Content ID'] || rowMap['idea_id'] || body.content_id || body.idea_id || '').trim();
  if (!contentId) throw new Error('Content ID is required for upsert');

  rowMap['Content ID'] = contentId;
  if (rowMap['Status']) rowMap['Status'] = normalizeStatus_(rowMap['Status']);

  const idColName = idColumnName_(headers);
  if (!idColName) throw new Error('No ID column found (expected "Content ID" or "idea_id")');

  const idColIndex = headers.indexOf(idColName);
  let targetRow = findRowByIdValue_(sheet, headerRow, idColIndex, contentId);
  const isNew = targetRow < 0;
  if (isNew) targetRow = sheet.getLastRow() + 1;

  headers.forEach((colName, i) => {
    const value = rowMap[colName];
    if (value !== undefined && value !== '') {
      sheet.getRange(targetRow, i + 1).setValue(value);
    }
  });

  return { status: isNew ? 'appended' : 'updated', content_id: contentId, row: targetRow };
}

function updateApproval(body) {
  const fields = {
    'Status':             normalizeStatus_(body.status),
    'Review Notes':       body.review_notes || body.reviewNotes || '',
    'Approved By':        body.approved_by  || body.approvedBy  || '',
    'Approval Timestamp': new Date().toISOString(),
  };
  return writeTracker(Object.assign({}, body, { fields }));
}

// ─── Drive ───────────────────────────────────────────────────────────────────

function listDriveFiles(body) {
  const folderId = body.folderId || body.folder_id;
  if (!folderId) return { files: [], error: 'folderId not provided' };

  const folder = DriveApp.getFolderById(folderId);
  const query  = String(body.query || '').toLowerCase();
  const files  = [];
  const it     = folder.getFiles();

  while (it.hasNext() && files.length < 30) {
    const file = it.next();
    const name = file.getName();
    if (query && name.toLowerCase().indexOf(query) < 0) continue;
    files.push({
      id:           file.getId(),
      name,
      mimeType:     file.getMimeType(),
      modifiedTime: file.getLastUpdated().toISOString(),
    });
  }
  return { files };
}

function readDriveDoc(body) {
  const fileId = extractId_(body.doc_id);
  const file   = DriveApp.getFileById(fileId);
  const mime   = file.getMimeType();
  let content  = '';

  if (mime === MimeType.GOOGLE_DOCS) {
    content = DocumentApp.openById(fileId).getBody().getText();
  } else {
    content = file.getBlob().getDataAsString();
  }

  return { file_id: fileId, name: file.getName(), content };
}

function extractId_(input) {
  const text = String(input || '');
  const patterns = [
    /\/document\/d\/([a-zA-Z0-9_-]+)/,
    /\/file\/d\/([a-zA-Z0-9_-]+)/,
    /id=([a-zA-Z0-9_-]+)/,
    /\/folders\/([a-zA-Z0-9_-]+)/,
  ];
  for (const p of patterns) {
    const m = text.match(p);
    if (m) return m[1];
  }
  return text;
}
