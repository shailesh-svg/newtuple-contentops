const CONTENTOPS_TOKEN = 'CHANGE_ME_TO_A_LONG_RANDOM_TOKEN';

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (body.token !== CONTENTOPS_TOKEN) {
      return jsonResponse({ ok: false, error: 'Unauthorized' });
    }

    const action = body.action;
    if (action === 'health') return jsonResponse({ ok: true, data: { status: 'ok' } });
    if (action === 'get_schema') return jsonResponse({ ok: true, data: getSchema(body) });
    if (action === 'read_tracker') return jsonResponse({ ok: true, data: readTracker(body) });
    if (action === 'write_tracker') return jsonResponse({ ok: true, data: writeTracker(body) });
    if (action === 'append_idea') return jsonResponse({ ok: true, data: appendIdea(body) });
    if (action === 'upsert_tracker_row') return jsonResponse({ ok: true, data: upsertTrackerRow(body) });
    if (action === 'update_approval') return jsonResponse({ ok: true, data: updateApproval(body) });
    if (action === 'list_drive_files') return jsonResponse({ ok: true, data: listDriveFiles(body) });
    if (action === 'read_drive_doc') return jsonResponse({ ok: true, data: readDriveDoc(body) });

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

function openSheet_(sheetId, sheetName) {
  const ss = SpreadsheetApp.openById(sheetId);
  return ss.getSheetByName(sheetName) || ss.getSheets()[0];
}

function getSchema(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const headerRow = findHeaderRow_(sheet);
  const headers = sheet.getRange(headerRow, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  const columns = {};
  headers.forEach((header, index) => {
    if (header) columns[header] = index + 1;
  });
  return { header_row: headerRow, columns };
}

function findHeaderRow_(sheet) {
  const values = sheet.getDataRange().getValues();
  const markers = ['Content ID', 'Working Title / Hook', 'Status', 'Week'];

  for (let i = 0; i < Math.min(values.length, 20); i++) {
    const row = values[i].map(String);
    if (row.indexOf('Content ID') >= 0) return i + 1;
    const matched = markers.filter(marker => row.indexOf(marker) >= 0).length;
    if (matched >= 3) return i + 1;
  }

  throw new Error('Tracker header row not found');
}

function readTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length === 0) return { rows: [], count: 0 };

  const headerRow = findHeaderRow_(sheet);
  const headers = values[headerRow - 1].map(String);
  let rows = values.slice(headerRow).map(row => rowToObject_(headers, row));

  if (body.status) {
    const target = String(body.status).toLowerCase();
    rows = rows.filter(row => String(row.Status || row.status || '').toLowerCase() === target);
  }

  const limit = Number(body.limit || 30);
  return { rows: rows.slice(0, limit), count: rows.length };
}

function writeTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const schema = getSchema(body);
  const headers = Object.keys(schema.columns);
  const idField = schema.columns['Content ID'] ? 'Content ID' : 'idea_id';
  const contentId = String(body.content_id || body.idea_id || '');
  if (!contentId) throw new Error('content_id is required');

  const targetRow = findRowByValue_(sheet, schema.header_row, schema.columns[idField], contentId);
  if (!targetRow) throw new Error(`${idField} not found: ${contentId}`);

  const fields = body.fields || {};
  Object.keys(fields).forEach(field => {
    const columnName = normalizeField_(field);
    const col = schema.columns[columnName];
    if (col) {
      sheet.getRange(targetRow, col).setValue(fields[field]);
    }
  });

  return { updated: contentId, fields: Object.keys(fields) };
}

function appendIdea(body) {
  const row = {
    'Content ID': body.content_id || body.idea_id,
    'Publish Date': new Date().toISOString().slice(0, 10),
    'Bucket': body.bucket,
    'Series Theme': body.source_type || 'manual',
    'Working Title / Hook': body.title,
    'Audience Intent': 'Educate and build trust',
    'Key Message': body.raw_input,
    'Draft Text': body.raw_input,
    'Format': 'Text Post',
    'Channel': 'LinkedIn',
    'Status': normalizeStatus_(body.status || 'Idea'),
    'Priority': 'Medium',
    'CTA Type': 'Start a conversation',
  };
  return upsertTrackerRow(Object.assign({}, body, { row }));
}

function upsertTrackerRow(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const schema = getSchema(body);
  const rowMap = body.row || {};
  const contentId = String(rowMap['Content ID'] || body.content_id || body.idea_id || '');
  if (!contentId) throw new Error('Content ID is required');

  rowMap['Content ID'] = contentId;
  if (rowMap.Status) rowMap.Status = normalizeStatus_(rowMap.Status);

  const idCol = schema.columns['Content ID'];
  if (!idCol) throw new Error('Content ID column not found');

  let targetRow = findRowByValue_(sheet, schema.header_row, idCol, contentId);
  const append = !targetRow;
  if (!targetRow) targetRow = sheet.getLastRow() + 1;

  Object.keys(rowMap).forEach(field => {
    const col = schema.columns[field];
    if (col) sheet.getRange(targetRow, col).setValue(rowMap[field]);
  });

  return { status: append ? 'appended' : 'updated', content_id: contentId, row: targetRow };
}

function updateApproval(body) {
  const fields = {
    Status: normalizeStatus_(body.status),
    'Review Notes': body.review_notes || body.reviewNotes || '',
    'Approved By': body.approved_by || body.approvedBy || '',
    'Approval Timestamp': new Date().toISOString(),
  };
  return writeTracker(Object.assign({}, body, { fields }));
}

function findRowByValue_(sheet, headerRow, col, value) {
  if (!col) return 0;
  const lastRow = sheet.getLastRow();
  if (lastRow <= headerRow) return 0;
  const values = sheet.getRange(headerRow + 1, col, lastRow - headerRow, 1).getValues();
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0]) === String(value)) return headerRow + 1 + i;
  }
  return 0;
}

function normalizeField_(field) {
  const map = {
    idea_id: 'Content ID',
    content_id: 'Content ID',
    title: 'Working Title / Hook',
    draft_text: 'Draft Text',
    bucket: 'Bucket',
    status: 'Status',
    reviewer: 'Approved By',
    review_notes: 'Review Notes',
    review_action_ts: 'Approval Timestamp',
    source_link: 'Source / Input Link',
    raw_input: 'Key Message',
    platform: 'Channel',
    published_url: 'Published URL',
  };
  return map[field] || field;
}

function normalizeStatus_(status) {
  const raw = String(status || '').toLowerCase().replace(/[-\s]+/g, '_');
  const map = {
    new: 'Idea',
    draft: 'Draft',
    needs_review: 'Needs Review',
    needs_revision: 'Needs Revision',
    approved: 'Approved',
    rejected: 'Rejected',
    scheduled: 'Scheduled',
    published: 'Published',
  };
  return map[raw] || status;
}

function listDriveFiles(body) {
  const folder = DriveApp.getFolderById(body.folderId);
  const query = String(body.query || '').toLowerCase();
  const files = [];
  const it = folder.getFiles();

  while (it.hasNext() && files.length < 30) {
    const file = it.next();
    const name = file.getName();
    if (query && name.toLowerCase().indexOf(query) < 0) continue;
    files.push({
      id: file.getId(),
      name,
      mimeType: file.getMimeType(),
      modifiedTime: file.getLastUpdated().toISOString(),
    });
  }

  return { files };
}

function readDriveDoc(body) {
  const fileId = extractId_(body.doc_id);
  const file = DriveApp.getFileById(fileId);
  const mimeType = file.getMimeType();
  let content = '';

  if (mimeType === MimeType.GOOGLE_DOCS) {
    content = DocumentApp.openById(fileId).getBody().getText();
  } else {
    content = file.getBlob().getDataAsString();
  }

  return {
    file_id: fileId,
    name: file.getName(),
    content,
  };
}

function extractId_(input) {
  const text = String(input || '');
  const patterns = [
    /\/document\/d\/([a-zA-Z0-9_-]+)/,
    /\/file\/d\/([a-zA-Z0-9_-]+)/,
    /id=([a-zA-Z0-9_-]+)/,
    /\/folders\/([a-zA-Z0-9_-]+)/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return text;
}

function rowToObject_(headers, row) {
  const obj = {};
  headers.forEach((header, index) => {
    obj[header] = row[index] === undefined ? '' : row[index];
  });
  return obj;
}
