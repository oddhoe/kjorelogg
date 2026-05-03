#!/usr/bin/env python3
# Minimal error-log patch for index1.html (test-fil)
# Legger til:
#   - Separat IDB-database for error-log (egen fra nvdb_tiles)
#   - logError() wrapper
#   - exportErrorLogTxt() for nedlasting som .txt
#   - To menyknapper i toppmenyen
# Ingen endring av eksisterende IDB-skjema eller funksjoner.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / 'docs'
TARGET = DOCS_DIR / 'index1.html'

if not TARGET.exists():
    print(f'[ERROR] {TARGET} finnes ikke')
    sys.exit(1)

html = TARGET.read_text(encoding='utf-8')
print(f'[INFO] Leste {TARGET.name} ({len(html)} bytes)')

# Sjekk at vi ikke kjorer dobbelt
if 'ERRLOG_DB_NAME' in html:
    print('[INFO] Error-log finnes allerede, hopper over')
    sys.exit(0)

# 1. JS-modul: separat IDB-database for error-log
errorlog_js = '''
/* ERROR LOG - separat IDB-database, ingen interferens med nvdb_tiles */
const ERRLOG_DB_NAME = 'kjorelogg_errors';
const ERRLOG_DB_VER = 1;
const ERRLOG_STORE = 'log';
const ERRLOG_KEEP = 500;
let _errlogDb = null;
let _errlogBuffer = [];
let _errlogFlushTimer = null;
let _errlogFlushing = false;

function openErrLogDB() {
  if (_errlogDb) return Promise.resolve(_errlogDb);
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('no idb'));
  return new Promise(function(res, rej) {
    var req = indexedDB.open(ERRLOG_DB_NAME, ERRLOG_DB_VER);
    req.onupgradeneeded = function(e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains(ERRLOG_STORE)) {
        db.createObjectStore(ERRLOG_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = function(e) { _errlogDb = e.target.result; res(_errlogDb); };
    req.onerror = function() { rej(req.error); };
  });
}

function logError(level, source, message, context) {
  try {
    var entry = {
      ts: Date.now(),
      level: String(level || 'info'),
      source: String(source || 'unknown'),
      message: String(message == null ? '' : message),
      context: null
    };
    if (context != null) {
      try { entry.context = JSON.parse(JSON.stringify(context)); }
      catch (e) { entry.context = String(context); }
    }
    _errlogBuffer.push(entry);
    try {
      var fn = level === 'error' ? console.error : (level === 'warn' ? console.warn : console.log);
      fn('[' + entry.source + '] ' + entry.message, context || '');
    } catch (e) {}
    scheduleErrLogFlush();
  } catch (e) {
    try { console.warn('logError failed', e); } catch (e2) {}
  }
}

function scheduleErrLogFlush() {
  if (_errlogFlushTimer) return;
  _errlogFlushTimer = setTimeout(function() {
    _errlogFlushTimer = null;
    flushErrLog();
  }, 2000);
}

function flushErrLog() {
  if (_errlogFlushing || !_errlogBuffer.length) return Promise.resolve();
  _errlogFlushing = true;
  var toWrite = _errlogBuffer.splice(0, _errlogBuffer.length);
  return openErrLogDB().then(function(db) {
    return new Promise(function(res, rej) {
      var tx = db.transaction(ERRLOG_STORE, 'readwrite');
      var store = tx.objectStore(ERRLOG_STORE);
      for (var i = 0; i < toWrite.length; i++) store.add(toWrite[i]);
      tx.oncomplete = function() { res(); };
      tx.onerror = function() { rej(tx.error); };
      tx.onabort = function() { rej(tx.error); };
    }).then(function() {
      // Trim FIFO til ERRLOG_KEEP
      return new Promise(function(res) {
        var tx = db.transaction(ERRLOG_STORE, 'readwrite');
        var store = tx.objectStore(ERRLOG_STORE);
        var cnt = store.count();
        cnt.onsuccess = function() {
          var total = cnt.result;
          if (total <= ERRLOG_KEEP) { res(); return; }
          var toDel = total - ERRLOG_KEEP;
          var cur = store.openCursor();
          var del = 0;
          cur.onsuccess = function(e) {
            var c = e.target.result;
            if (c && del < toDel) { store.delete(c.primaryKey); del++; c.continue(); }
            else res();
          };
          cur.onerror = function() { res(); };
        };
        cnt.onerror = function() { res(); };
      });
    });
  }).catch(function(e) {
    try { console.warn('errlog flush failed', e); } catch (e2) {}
    _errlogBuffer.unshift.apply(_errlogBuffer, toWrite);
  }).then(function() {
    _errlogFlushing = false;
  });
}

function exportErrorLogTxt() {
  return flushErrLog().then(function() {
    return openErrLogDB();
  }).then(function(db) {
    return new Promise(function(res, rej) {
      var tx = db.transaction(ERRLOG_STORE, 'readonly');
      var req = tx.objectStore(ERRLOG_STORE).getAll();
      req.onsuccess = function() { res(req.result || []); };
      req.onerror = function() { rej(req.error); };
    });
  }).then(function(entries) {
    if (!entries.length) {
      try { setMessage('Ingen feilloggoppfoeringer aa eksportere.', 'notice'); } catch (e) {}
      return;
    }
    entries.sort(function(a, b) { return (a.ts || 0) - (b.ts || 0); });
    var ver = (typeof APP_VERSION !== 'undefined') ? APP_VERSION : 'unknown';
    var lines = ['Kjorelogg feillogg ' + ver,
                 'Eksportert: ' + new Date().toISOString(),
                 'Antall: ' + entries.length, ''];
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      var ts = new Date(e.ts).toISOString();
      var ctx = e.context ? ' ' + JSON.stringify(e.context) : '';
      lines.push(ts + ' [' + e.level.toUpperCase() + '] [' + e.source + '] ' + e.message + ctx);
    }
    var text = lines.join('\\n');
    var stamp = new Date().toISOString().slice(0, 16).replace(/[-:]/g, '').replace('T', '-');
    var fileName = 'kjorelogg-feillogg-' + stamp + '.txt';
    var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = fileName;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
    try { setMessage('Feillogg eksportert: ' + entries.length + ' oppfoeringer.', 'success'); } catch (e) {}
  }).catch(function(err) {
    try { setMessage('Eksport av feillogg feilet: ' + (err && err.message ? err.message : err), 'error'); } catch (e) {}
  });
}

function clearErrorLog() {
  if (!confirm('Slette hele feilloggen?')) return Promise.resolve();
  _errlogBuffer = [];
  return openErrLogDB().then(function(db) {
    return new Promise(function(res, rej) {
      var tx = db.transaction(ERRLOG_STORE, 'readwrite');
      var req = tx.objectStore(ERRLOG_STORE).clear();
      req.onsuccess = function() { res(); };
      req.onerror = function() { rej(req.error); };
    });
  }).then(function() {
    try { setMessage('Feillogg toemt.', 'success'); } catch (e) {}
  }).catch(function(err) {
    try { setMessage('Kunne ikke toemme: ' + err, 'error'); } catch (e) {}
  });
}

window.addEventListener('pagehide', function() {
  try { flushErrLog(); } catch (e) {}
});

// Logg en oppstart-melding sa vi vet at modulen er aktivert
logError('info', 'errlog', 'Error-log modul lastet', { version: (typeof APP_VERSION !== 'undefined') ? APP_VERSION : 'unknown' });

// Wire opp meny-knapper nar DOM er klar
function _wireErrLogButtons() {
  var btn1 = document.getElementById('btn-export-errorlog');
  if (btn1 && !btn1._wired) {
    btn1._wired = true;
    btn1.addEventListener('click', function() {
      try { closeMenu(); } catch (e) {}
      exportErrorLogTxt();
    });
  }
  var btn2 = document.getElementById('btn-clear-errorlog');
  if (btn2 && !btn2._wired) {
    btn2._wired = true;
    btn2.addEventListener('click', function() {
      try { closeMenu(); } catch (e) {}
      clearErrorLog();
    });
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _wireErrLogButtons);
} else {
  _wireErrLogButtons();
}
setTimeout(_wireErrLogButtons, 1000);
setTimeout(_wireErrLogButtons, 3000);
'''

# 2. Inject JS-modul rett for </script>
script_close = '</script>'
last_script_idx = html.rfind(script_close)
if last_script_idx < 0:
    print('[ERROR] Fant ikke </script>')
    sys.exit(1)
html = html[:last_script_idx] + errorlog_js + html[last_script_idx:]
print('[OK] JS-modul injisert')

# 3. Legg til to menyknapper rett etter btn-export (eller annen kjent knapp).
# Vi forer en SUPER-DEFENSIV strategi: bare proev a finne en knapp i menyen og legg etter den.
menu_btn_html = (
    '<button class="menu-item" id="btn-export-errorlog">Eksporter feillogg</button>'
    '<button class="menu-item" id="btn-clear-errorlog">Toem feillogg</button>'
)

# Provem flere kjente menyknapper i prioritert rekkefolge
candidate_anchors = [
    '<button class="menu-item" id="btn-exportgpx">',
    '<button class="menu-item" id="btn-export">',
    '<button class="menu-item" id="btn-import">',
    '<button class="menu-item" id="btn-restoresnap">',
]

inserted = False
for anchor in candidate_anchors:
    idx = html.find(anchor)
    if idx >= 0:
        # Finn slutten av denne knappen (</button>)
        end_idx = html.find('</button>', idx)
        if end_idx >= 0:
            ins_pos = end_idx + len('</button>')
            html = html[:ins_pos] + menu_btn_html + html[ins_pos:]
            print(f'[OK] Menyknapper lagt etter {anchor[:50]}...')
            inserted = True
            break

if not inserted:
    print('[WARN] Fant ingen meny-anchor. Knappene legges ikke til. Eksport via console: exportErrorLogTxt()')

TARGET.write_text(html, encoding='utf-8')
print(f'[INFO] Skrev {TARGET.name} ({len(html)} bytes)')
print('=== Ferdig ===')
