/**
 * Keep/Trade/Cut vote collector -- Trade Desk #1 — IDP position weight
 * recalibration (DL/LB/DB constants themselves) script.
 *
 * B10R/B10C Package Adjustment V9 — FULL MERGED PRIVATE COLLECTOR V4 + P5 MONITOR
 *
 * Baseline: exact live Code.gs exported from the currently deployed Apps Script
 * project on 2026-10-05. The project is on the legacy Apps Script runtime, so
 * this merged source intentionally uses legacy-compatible JavaScript syntax.
 *
 * Existing non-V9 contract is preserved:
 *   - bound spreadsheet via SpreadsheetApp.getActiveSpreadsheet()
 *   - public tab name: votes
 *   - request body: JSON text sent as text/plain
 *   - required fields: keep, trade, cut, voterRosterId
 *   - stored columns: timestamp | voter_roster_id | keep | trade | cut
 *   - success response: {ok:true}
 *   - malformed/missing-field response behavior unchanged
 *
 * B10R infrastructure-only change:
 *   - ONLY keep values beginning with __pkgv9val__| are routed to the separate
 *     private V9 spreadsheet/tab below.
 *   - V9 private-route failures throw; there is NO fallback write to votes.
 *   - all non-V9 rows continue through the original public votes sheet.
 *   - preserves the launch-test sentinel mode.
 *   - adds the P5 outcome-blind structural-status monitor; it never returns choices.
 */

var B10R_V9_PREFIX = '__pkgv9val__|';
var B10R_V9_LAUNCHTEST_PREFIX = '__pkgv9val__|pkgv9val_LAUNCHTEST|';
var B10R_V9_PRIVATE_SPREADSHEET_ID = '1F9FVasO1nSRJO4IBMwA9sq1OCPxoVMfW_DRD3fNhr7c';
var B10R_V9_PRIVATE_SHEET_NAME = 'v9_validation';
var B10R_EXPECTED_HEADER = ['timestamp', 'voter_roster_id', 'keep', 'trade', 'cut'];

function b10rJson_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function b10rHeaderMatches_(sheet) {
  if (!sheet || sheet.getLastRow() < 1) return false;
  var values = sheet.getRange(1, 1, 1, 5).getDisplayValues()[0];
  for (var i = 0; i < B10R_EXPECTED_HEADER.length; i++) {
    if (String(values[i] || '') !== B10R_EXPECTED_HEADER[i]) return false;
  }
  return true;
}

function b10rGetPrivateSheet_() {
  var privateBook = SpreadsheetApp.openById(B10R_V9_PRIVATE_SPREADSHEET_ID);
  var privateSheet = privateBook.getSheetByName(B10R_V9_PRIVATE_SHEET_NAME);
  if (!privateSheet) throw new Error('B10R V9 private destination sheet missing');
  if (!b10rHeaderMatches_(privateSheet)) throw new Error('B10R V9 private destination header mismatch');
  return privateSheet;
}

function b10rHex_(bytes) {
  var out = '';
  for (var i = 0; i < bytes.length; i++) {
    var b = bytes[i];
    if (b < 0) b += 256;
    var x = b.toString(16);
    if (x.length === 1) x = '0' + x;
    out += x;
  }
  return out;
}

function b10rSha256_(text) {
  return b10rHex_(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    text,
    Utilities.Charset.UTF_8
  ));
}

function doPost(e) {
  // Preserve the original public-sheet acquisition and header initialization.
  // This executes for every request exactly as the live baseline did. A V9
  // request may touch public sheet metadata/header, but no V9 outcome row is
  // ever appended there.
  var publicBook = SpreadsheetApp.getActiveSpreadsheet();
  var publicSheet = publicBook.getSheetByName('votes');
  if (!publicSheet) {
    publicSheet = publicBook.insertSheet('votes');
  }

  if (publicSheet.getLastRow() === 0) {
    publicSheet.appendRow(['timestamp', 'voter_roster_id', 'keep', 'trade', 'cut']);
  }

  var data;
  try {
    // e.postData.contents is the raw JSON text sent by the client, even
    // though it is labeled text/plain to avoid the CORS preflight.
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: 'malformed request body' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // Preserve the original required-field validation exactly.
  if (!data.keep || !data.trade || !data.cut || !data.voterRosterId) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: 'missing required field' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // B10R routing boundary. Non-V9 uses the exact publicSheet already obtained
  // above. V9 opens only the private destination. If private access/header
  // validation fails, the exception propagates and NO public fallback occurs.
  var sheet = publicSheet;
  if (String(data.keep).indexOf(B10R_V9_PREFIX) === 0) {
    sheet = b10rGetPrivateSheet_();
  }

  // Exactly one append per accepted request, preserving the original column
  // order, server timestamp, and String coercion.
  sheet.appendRow([
    new Date().toISOString(),
    String(data.voterRosterId),
    String(data.keep),
    String(data.trade),
    String(data.cut),
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Outcome-blind launch-test status endpoint.
 *
 * It can match ONLY the invalid-by-design B10 launch sentinel:
 *   - mode must be v9_launchtest_status
 *   - session must be exactly 48 lowercase hex chars (192 bits)
 *   - voter envelope must be slot 0
 *   - keep must be pkgv9val_LAUNCHTEST
 *
 * It never returns row contents, a canonical choice, a display choice, a real
 * slot, or human aggregates. A real B8/B9 human row cannot satisfy the match.
 */
function b10rHandleV9LaunchTestGet_(e) {
  var p = (e && e.parameter) || {};
  if (String(p.mode || '') !== 'v9_launchtest_status') return null;

  var session = String(p.session || '').toLowerCase();
  if (!/^[0-9a-f]{48}$/.test(session)) {
    return b10rJson_({ ok: false, error: 'invalid_session' });
  }

  var envelope = '__pkgv9val_session__|0|' + session;
  var sheet;
  try {
    sheet = b10rGetPrivateSheet_();
  } catch (err) {
    return b10rJson_({ ok: false, error: 'private_destination_unavailable' });
  }

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return b10rJson_({ ok: true, found: false, count: 0, field_sha256: null });
  }

  // Launch checks are rare and happen before real collection. Read only the
  // recent tail so this endpoint is never a general-purpose study reader.
  var firstRow = Math.max(2, lastRow - 499);
  var rowCount = lastRow - firstRow + 1;
  var rows = sheet.getRange(firstRow, 1, rowCount, 5).getDisplayValues();
  var hits = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var voter = String(row[1] || '');
    var keep = String(row[2] || '');
    if (voter === envelope && keep.indexOf(B10R_V9_LAUNCHTEST_PREFIX) === 0) {
      hits.push(row);
    }
  }

  if (hits.length !== 1) {
    return b10rJson_({
      ok: true,
      found: hits.length > 0,
      count: hits.length,
      field_sha256: null
    });
  }

  var hit = hits[0];
  var canonical = [
    String(hit[1] || ''),
    String(hit[2] || ''),
    String(hit[3] || ''),
    String(hit[4] || '')
  ].join('\n');

  return b10rJson_({
    ok: true,
    found: true,
    count: 1,
    field_sha256: b10rSha256_(canonical)
  });
}


/**
 * B10C / P5 outcome-blind structural monitoring.
 *
 * This monitor is deliberately incapable of reporting human choices. It uses
 * choice/display fields only to enforce the frozen B8 transport-consistency
 * rule, then discards them. Public output is restricted to per-slot session
 * counts, structural validity/completeness, and collection maturity.
 */
var B10C_MONITOR_SCHEMA = 1;
var B10C_STUDY_ID = 'package-adjustment-v9-discordant-human-validation';
var B10C_B8_FREEZE_COMMIT = '2ff1ca2a6ea440f2e1a4c390ae974a9666e9912a';
var B10C_B8_SCHEDULE_SHA256 = '9626fd524d721289fd5494c140d026a085b70dd44ec753c9a24f4838ea59737d';
var B10C_B8_SCHEDULE_URL = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/' +
  B10C_B8_FREEZE_COMMIT +
  '/research/package-adjustment-v9/b8-human-catalog-assignment-freeze/b8_voter_assignment_schedule.json';

function b10cFetchFrozenSchedule_() {
  var response = UrlFetchApp.fetch(B10C_B8_SCHEDULE_URL, {
    method: 'get',
    followRedirects: true,
    muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('B10C frozen B8 schedule fetch failed');
  }
  var text = response.getContentText();
  if (b10rSha256_(text) !== B10C_B8_SCHEDULE_SHA256) {
    throw new Error('B10C frozen B8 schedule SHA256 mismatch');
  }
  var schedule = JSON.parse(text);
  if (!schedule || Number(schedule.accepted_voter_slots) !== 40 ||
      Number(schedule.challenges_per_slot) !== 24 || !schedule.slots) {
    throw new Error('B10C frozen B8 schedule contract mismatch');
  }
  for (var slot = 1; slot <= 40; slot++) {
    var s = schedule.slots[String(slot)];
    if (!s || Number(s.accepted_voter_slot) !== slot ||
        !s.challenge_order || s.challenge_order.length !== 24 ||
        !s.display_left_by_challenge) {
      throw new Error('B10C frozen B8 slot schedule mismatch');
    }
  }
  return schedule;
}

function b10cParseUtcMillis_(text) {
  var value = String(text || '');
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(value)) return null;
  var ms = Date.parse(value);
  return isNaN(ms) ? null : ms;
}

function b10cParseRealV9Row_(row, schedule) {
  var voter = String(row[1] || '');
  var keep = String(row[2] || '');
  var trade = String(row[3] || '');
  var cut = String(row[4] || '');

  if (keep.indexOf(B10R_V9_PREFIX) !== 0) return { relevant: false };
  if (keep.indexOf(B10R_V9_LAUNCHTEST_PREFIX) === 0) return { relevant: false, launchtest: true };

  var envelopeMatch = /^__pkgv9val_session__\|([1-9]|[1-3][0-9]|40)\|([0-9a-f]{48})$/.exec(voter);
  if (!envelopeMatch) return { relevant: true, assignable: false, valid: false };

  var slot = Number(envelopeMatch[1]);
  var envelopeSession = envelopeMatch[2];
  var voteParts = keep.split('|');
  var metaParts = trade.split('|');
  var scheduleSlot = schedule.slots[String(slot)];

  var parsed = {
    relevant: true,
    assignable: true,
    slot: slot,
    session: envelopeSession,
    valid: false,
    challenge: null,
    finalMillis: null
  };

  if (voteParts.length !== 6 || voteParts[0] !== '__pkgv9val__') return parsed;
  if (metaParts.length !== 6 || metaParts[0] !== '__pkgv9val_meta__') return parsed;
  if (cut !== '__pkgv9val_schema__|1') return parsed;

  var challenge = String(voteParts[1] || '');
  var canonicalChoice = String(voteParts[2] || '');
  var clickedDisplay = String(voteParts[3] || '');
  var voteSession = String(voteParts[4] || '');
  var timestampText = String(voteParts[5] || '');

  var metaChallenge = String(metaParts[1] || '');
  var canonicalLeft = String(metaParts[2] || '');
  var metaSlotText = String(metaParts[3] || '');
  var displayOrderText = String(metaParts[4] || '');
  var metaSession = String(metaParts[5] || '');

  if (!/^pkgv9val_\d{4}$/.test(challenge)) return parsed;
  if (canonicalChoice !== 'A' && canonicalChoice !== 'B') return parsed;
  if (clickedDisplay !== 'L' && clickedDisplay !== 'R') return parsed;
  if (canonicalLeft !== 'A' && canonicalLeft !== 'B') return parsed;
  if (voteSession !== envelopeSession || metaSession !== envelopeSession) return parsed;
  if (metaChallenge !== challenge) return parsed;
  if (metaSlotText !== String(slot)) return parsed;
  if (!/^(?:[0-9]|1[0-9]|2[0-3])$/.test(displayOrderText)) return parsed;

  var displayOrder = Number(displayOrderText);
  if (!scheduleSlot || scheduleSlot.challenge_order[displayOrder] !== challenge) return parsed;
  if (String(scheduleSlot.display_left_by_challenge[challenge] || '') !== canonicalLeft) return parsed;

  // Frozen B8 row-validity consistency check. This never records or aggregates
  // the direction of the choice; it only verifies that canonical and displayed
  // encodings describe the same click.
  if (clickedDisplay === 'L' && canonicalChoice !== canonicalLeft) return parsed;
  if (clickedDisplay === 'R' && canonicalChoice === canonicalLeft) return parsed;

  var finalMillis = b10cParseUtcMillis_(timestampText);
  if (finalMillis === null) return parsed;

  parsed.valid = true;
  parsed.challenge = challenge;
  parsed.finalMillis = finalMillis;
  return parsed;
}

function b10cSelectAcceptedSession_(completeSessions) {
  if (!completeSessions || completeSessions.length === 0) return null;
  var ordered = completeSessions.slice(0);
  ordered.sort(function(a, b) {
    if (a.finalMillis !== b.finalMillis) return a.finalMillis - b.finalMillis;
    if (a.session < b.session) return -1;
    if (a.session > b.session) return 1;
    return 0;
  });
  return ordered[0];
}

function b10cBuildStructuralStatus_(rows, schedule) {
  var sessions = {};
  var unassignedInvalidRows = 0;

  for (var i = 0; i < rows.length; i++) {
    var parsed = b10cParseRealV9Row_(rows[i], schedule);
    if (!parsed.relevant) continue;
    if (!parsed.assignable) {
      unassignedInvalidRows += 1;
      continue;
    }

    var key = parsed.session;
    if (!sessions[key]) {
      sessions[key] = {
        session: parsed.session,
        slot: parsed.slot,
        rows: 0,
        valid: true,
        seenChallenges: {},
        finalMillis: null
      };
    }
    var s = sessions[key];
    s.rows += 1;
    if (s.slot !== parsed.slot) s.valid = false;
    if (!parsed.valid) {
      s.valid = false;
      continue;
    }
    if (s.seenChallenges[parsed.challenge]) {
      s.valid = false;
    } else {
      s.seenChallenges[parsed.challenge] = true;
    }
    if (s.finalMillis === null || parsed.finalMillis > s.finalMillis) {
      s.finalMillis = parsed.finalMillis;
    }
  }

  var slotBuckets = {};
  var slot;
  for (slot = 1; slot <= 40; slot++) {
    slotBuckets[String(slot)] = [];
  }

  var sessionKeys = Object.keys(sessions);
  for (var j = 0; j < sessionKeys.length; j++) {
    var sessionObj = sessions[sessionKeys[j]];
    var expected = schedule.slots[String(sessionObj.slot)].challenge_order;
    var seenCount = Object.keys(sessionObj.seenChallenges).length;
    sessionObj.complete = sessionObj.valid && sessionObj.rows === 24 && seenCount === 24;
    if (sessionObj.complete) {
      for (var k = 0; k < expected.length; k++) {
        if (!sessionObj.seenChallenges[expected[k]]) {
          sessionObj.complete = false;
          break;
        }
      }
    }
    slotBuckets[String(sessionObj.slot)].push(sessionObj);
  }

  var slots = [];
  var acceptedCompleteSlots = 0;

  for (slot = 1; slot <= 40; slot++) {
    var bucket = slotBuckets[String(slot)];
    var validCount = 0;
    var complete = [];
    for (var m = 0; m < bucket.length; m++) {
      if (bucket[m].valid) validCount += 1;
      if (bucket[m].complete) complete.push(bucket[m]);
    }
    var accepted = b10cSelectAcceptedSession_(complete);
    if (accepted) acceptedCompleteSlots += 1;

    slots.push({
      slot: slot,
      candidate_sessions: bucket.length,
      valid_sessions: validCount,
      complete_sessions: complete.length,
      invalid_sessions: bucket.length - validCount,
      accepted_complete: accepted !== null
    });
  }

  return {
    ok: true,
    monitor_schema: B10C_MONITOR_SCHEMA,
    study_id: B10C_STUDY_ID,
    outcome_blind: true,
    all_40_slots_complete: acceptedCompleteSlots === 40,
    unassigned_invalid_rows: unassignedInvalidRows,
    slots: slots
  };
}

function b10cHandleV9StructuralStatusGet_(e) {
  var p = (e && e.parameter) || {};
  if (String(p.mode || '') !== 'v9_structural_status') return null;

  var schedule;
  var sheet;
  try {
    schedule = b10cFetchFrozenSchedule_();
    sheet = b10rGetPrivateSheet_();
  } catch (err) {
    return b10rJson_({ ok: false, error: 'structural_monitor_unavailable' });
  }

  var lastRow = sheet.getLastRow();
  var rows = [];
  if (lastRow >= 2) {
    rows = sheet.getRange(2, 1, lastRow - 1, 5).getDisplayValues();
  }

  try {
    return b10rJson_(b10cBuildStructuralStatus_(rows, schedule));
  } catch (err2) {
    return b10rJson_({ ok: false, error: 'structural_monitor_failed_closed' });
  }
}

function doGet(e) {
  var launch = b10rHandleV9LaunchTestGet_(e);
  if (launch) return launch;

  var structural = b10cHandleV9StructuralStatusGet_(e);
  if (structural) return structural;

  return b10rJson_({ ok: false, error: 'unsupported_mode' });
}
