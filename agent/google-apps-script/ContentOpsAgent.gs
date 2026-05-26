const CONTENTOPS_TOKEN = 'CHANGE_ME_TO_A_LONG_RANDOM_TOKEN';

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (body.token !== CONTENTOPS_TOKEN) {
      return jsonResponse({ ok: false, error: 'Unauthorized' });
    }

    const action = body.action;
    if (action === 'health') return jsonResponse({ ok: true, data: { status: 'ok' } });
    if (action === 'read_tracker') return jsonResponse({ ok: true, data: readTracker(body) });
    if (action === 'write_tracker') return jsonResponse({ ok: true, data: writeTracker(body) });
    if (action === 'append_idea') return jsonResponse({ ok: true, data: appendIdea(body) });
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

function readTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length === 0) return { rows: [], count: 0 };

  const headers = values[0].map(String);
  let rows = values.slice(1).map(row => rowToObject_(headers, row));

  if (body.status) {
    const target = String(body.status).toLowerCase();
    rows = rows.filter(row => String(row.status || '').toLowerCase() === target);
  }

  const limit = Number(body.limit || 30);
  return { rows: rows.slice(0, limit), count: rows.length };
}

function writeTracker(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length === 0) throw new Error('Tracker is empty');

  const headers = values[0].map(String);
  const idCol = headers.indexOf('idea_id');
  if (idCol < 0) throw new Error('idea_id column not found');

  const targetRowIndex = values.findIndex((row, index) => {
    return index > 0 && String(row[idCol]) === String(body.idea_id);
  });
  if (targetRowIndex < 0) throw new Error(`idea_id not found: ${body.idea_id}`);

  const fields = body.fields || {};
  Object.keys(fields).forEach(field => {
    const col = headers.indexOf(field);
    if (col >= 0) {
      sheet.getRange(targetRowIndex + 1, col + 1).setValue(fields[field]);
    }
  });

  return { updated: body.idea_id, fields: Object.keys(fields) };
}

function appendIdea(body) {
  const sheet = openSheet_(body.sheetId, body.sheetName);
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  const rowMap = {
    idea_id: body.idea_id,
    created_at: new Date().toISOString().slice(0, 10),
    title: body.title,
    bucket: body.bucket,
    source_type: body.source_type || 'manual',
    raw_input: body.raw_input,
    status: body.status || 'new',
  };
  sheet.appendRow(headers.map(header => rowMap[header] || ''));
  return { appended: body.idea_id, title: body.title };
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
