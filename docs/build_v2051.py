#!/usr/bin/env python3
"""Bygg v2.0.51-ios fra v2.0.50-ios. Meny-rydding."""
import sys
import re

if len(sys.argv) != 3:
    print(__doc__); sys.exit(1)
INPUT, OUTPUT = sys.argv[1], sys.argv[2]
with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()
original_len = len(html)
print(f"Lest {original_len} tegn")

# 1. APP_VERSION
old = "const APP_VERSION='v2.0.50-ios';"
assert old in html
html = html.replace(old, "const APP_VERSION='v2.0.51-ios';")
html = html.replace("Vegmåling · v2.0.50-ios", "Vegmåling · v2.0.51-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.50", "kjorelogg-nvdb-fartsgrense/v2.0.51")
html = html.replace("kjorelogg-nvdb-gps/v2.0.50", "kjorelogg-nvdb-gps/v2.0.51")
print("OK 1: APP_VERSION")

# 2. Bytt ut menyen
new_menu = (
'<div class="menu-section-title">Daglig bruk</div>'
'<button class="menu-item" id="btn-refreshcenter">🔄 Oppdater området</button>'
'<div class="menu-sep"></div>'
'<div class="menu-section-title">Backup og data</div>'
'<button class="menu-item" id="btn-export">📤 Eksporter</button>'
' <button class="menu-item" id="btn-restoresnap">⏪ Gjenopprett fra snapshot</button>'
' <button class="menu-item" id="btn-exportgpx">🛰 Eksporter GPX-spor</button>'
' <button class="menu-item" id="btn-import">📥 Importer</button>'
'<div class="menu-sep"></div>'
'<div class="menu-section-title">Verktøy</div>'
'<button class="menu-item" id="btn-repairdir">🔄 Korriger retning</button>'
' <button class="menu-item" id="btn-manualcenter">📍 Sett manuell kartmarkør</button>'
' <button class="menu-item" id="btn-clearmanual">🧹 Fjern manuell markør</button>'
'<div class="menu-sep"></div>'
'<div class="menu-section-title">Innstillinger</div>'
'<button class="menu-item" id="btn-backgroundgps">📍 Bakgrunns-GPS PÅ</button>'
'<div class="menu-sep"></div>'
'<div class="menu-section-title">Vegkategorier</div>'
'<div class="menu-cat-wrap">'
'<button class="cat-chip" data-cat="E">EV</button>'
' <button class="cat-chip" data-cat="EGSV">EV-GSV</button>'
' <button class="cat-chip" data-cat="R">RV</button>'
' <button class="cat-chip" data-cat="RGSV">RV-GSV</button>'
' <button class="cat-chip active" data-cat="F">FV</button>'
' <button class="cat-chip" data-cat="FGSV">FV-GSV</button>'
' <button class="cat-mini" id="cat-all">Alle</button>'
' <button class="cat-mini" id="cat-none">Ingen</button>'
'</div>'
'<div class="menu-sep"></div>'
'<button class="menu-item" onclick="resetAll()">🗑 Nullstill</button>'
)

pattern = re.compile(r'(<div id="top-menu">)(.*?)(</div><input type="file" id="import-file")', re.DOTALL)
m = pattern.search(html)
assert m, "Fant ikke top-menu blokk"
html = html.replace(m.group(0), m.group(1) + new_menu + m.group(3))
print("OK 2: Meny-HTML byttet")

# 3. Fjern event handlers via paren-matching
def find_handler_end(text, start_idx):
 open_paren = text.find('(', start_idx)
 if open_paren == -1: return -1
 i = open_paren
 depth = 0
 in_str = None
 in_line_comment = False
 in_block_comment = False
 while i < len(text):
  c = text[i]
  nxt = text[i+1] if i+1 < len(text) else ''
  if in_line_comment:
   if c == '\n': in_line_comment = False
   i += 1; continue
  if in_block_comment:
   if c == '*' and nxt == '/': in_block_comment = False; i += 2; continue
   i += 1; continue
  if in_str == 'single':
   if c == '\\': i += 2; continue
   if c == "'": in_str = None
   i += 1; continue
  if in_str == 'double':
   if c == '\\': i += 2; continue
   if c == '"': in_str = None
   i += 1; continue
  if in_str == 'template':
   if c == '\\': i += 2; continue
   if c == '`': in_str = None
   i += 1; continue
  if c == '/' and nxt == '/': in_line_comment = True; i += 2; continue
  if c == '/' and nxt == '*': in_block_comment = True; i += 2; continue
  if c == "'": in_str = 'single'; i += 1; continue
  if c == '"': in_str = 'double'; i += 1; continue
  if c == '`': in_str = 'template'; i += 1; continue
  if c == '(': depth += 1; i += 1; continue
  if c == ')':
   depth -= 1
   if depth == 0:
    j = i + 1
    while j < len(text) and text[j] in ' \t': j += 1
    if j < len(text) and text[j] == ';':
     return j + 1
    return i + 1
   i += 1; continue
  i += 1
 return -1

removed = ['btn-offline','btn-offlinemode','btn-datasaver','btn-sideanlegg',
           'btn-cleansideanlegg','btn-repairgeom','btn-planmode','btn-clear-plan-menu']

removed_count = 0
for btn_id in removed:
 pat = re.compile(r"document\.getElementById\('" + re.escape(btn_id) + r"'\)\??\.addEventListener")
 while True:
  m = pat.search(html)
  if not m: break
  start = m.start()
  end = find_handler_end(html, m.end())
  if end == -1:
   print(f"  ADVARSEL: {btn_id}")
   break
  while start > 0 and html[start-1] in ' \t': start -= 1
  if start > 0 and html[start-1] == '\n': start -= 1
  html = html[:start] + html[end:]
  removed_count += 1
print(f"OK 3: Fjernet {removed_count} handlers")

# 4. Fjern applySettingsToUI-referanser
apply_lines = [
 "document.getElementById('btn-datasaver').textContent=settings.dataSaver?'💾 Datasparing PÅ':'💾 Datasparing AV';",
 " const sa=document.getElementById('btn-sideanlegg'); if(sa) sa.textContent=settings.includeSideanlegg?'🅿️ Sideanlegg PÅ':'🅿️ Sideanlegg AV';",
 " const pm=document.getElementById('btn-planmode'); if(pm) pm.textContent=settings.planMode?'🗺 Planmodus PÅ':'🗺 Planmodus AV';",
]
removed_apply = 0
for line in apply_lines:
 if line in html:
  html = html.replace(line, '', 1)
  removed_apply += 1
print(f"OK 4: Fjernet {removed_apply} apply-linjer")

# Valider
final_len = len(html)
print(f"\nDifferanse: {final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.50-ios' not in html
assert 'v2.0.51-ios' in html

for btn_id in removed:
 assert f'id="{btn_id}"' not in html
 occ = [mm.start() for mm in re.finditer(re.escape(f"getElementById('{btn_id}')"), html)]
 for pos in occ:
  end = pos + len(f"getElementById('{btn_id}')")
  while end < len(html) and html[end] in ' \t\n': end += 1
  rest = html[end:end+30]
  assert '.addEventListener' not in rest, f"Orphan {btn_id}"

for btn_id in ['btn-refreshcenter','btn-export','btn-restoresnap','btn-exportgpx',
               'btn-import','btn-repairdir','btn-manualcenter','btn-clearmanual',
               'btn-backgroundgps','cat-all','cat-none']:
 assert f'id="{btn_id}"' in html

assert ("btn-backgroundgps').addEventListener" in html or 
        "btn-backgroundgps')?.addEventListener" in html)
print("OK Validering")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"OK Skrevet til {OUTPUT}")
