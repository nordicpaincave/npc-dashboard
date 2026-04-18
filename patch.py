"""
NPC Dashboard — Patch para adicionar Rafael Lemos
Execute em C:\\npc-dashboard:
  python C:\\npc_sync\\npc_patch_dashboard.py
"""
import json, re

# ── template.html ──────────────────────────────────────────────────────────────
print("=== Patchando template.html ===")
with open('template.html', encoding='utf-8') as f:
    t = f.read()

changes = [
    # 1. Dropdown atleta
    ('<option value="gabriel">Gabriel</option>',
     '<option value="gabriel">Gabriel</option>\n        <option value="rafael">Rafael Lemos</option>'),
    # 2. Calendário buttons
    ('<button class="tab-btn" onclick="setCalAthlete(\'gabriel\',this)">Gabriel</button>',
     '<button class="tab-btn" onclick="setCalAthlete(\'gabriel\',this)">Gabriel</button>\n        <button class="tab-btn" onclick="setCalAthlete(\'rafael\',this)">Rafael</button>'),
    # 3. Macro buttons
    ('<button class="tab-btn" onclick="setMacroAthlete(\'gabriel\',this)">Gabriel</button>',
     '<button class="tab-btn" onclick="setMacroAthlete(\'gabriel\',this)">Gabriel</button>\n        <button class="tab-btn" onclick="setMacroAthlete(\'rafael\',this)">Rafael</button>'),
    # 4. ATHLETES array
    ("const ATHLETES = ['bruno','jean','gabriel'];",
     "const ATHLETES = ['bruno','jean','gabriel','rafael'];"),
    # 5. NAMES
    ("const NAMES    = {bruno:'Bruno',jean:'Jean',gabriel:'Gabriel'};",
     "const NAMES    = {bruno:'Bruno',jean:'Jean',gabriel:'Gabriel',rafael:'Rafael'};"),
    # 6. COLORS
    ("const COLORS   = {bruno:'#4a9eff',jean:'#ff7c3a',gabriel:'#4db87a'};",
     "const COLORS   = {bruno:'#4a9eff',jean:'#ff7c3a',gabriel:'#4db87a',rafael:'#c084fc'};"),
    # 7. Objetivos prova
    ("Meta: Top 5 M40-44 + vaga Mundial (Jean) / sub-5h (Bruno) / sub-4h50 (Gabriel)",
     "Meta: Top 5 M40-44 + vaga Mundial (Jean) / sub-5h (Bruno) / sub-4h50 (Gabriel) / sub-5h30 (Rafael)"),
    # 8. CTL pico na fase específico
    ("CTL pico: 120 (Jean) / 102 (Bruno) / 90 (Gabriel)",
     "CTL pico: 120 (Jean) / 102 (Bruno) / 90 (Gabriel) / 95 (Rafael)"),
]

for old, new in changes:
    if old in t:
        t = t.replace(old, new)
        print(f"  OK: {old[:50]}...")
    else:
        print(f"  SKIP (não encontrado): {old[:50]}...")

with open('template.html', 'w', encoding='utf-8') as f:
    f.write(t)
print("template.html atualizado\n")

# ── generate.py ───────────────────────────────────────────────────────────────
print("=== Patchando generate.py ===")
with open('generate.py', encoding='utf-8') as f:
    g = f.read()

gen_changes = [
    # 1. ATHLETES dict
    ('"gabriel": {"id": 5775491, "name": "Gabriel"},\n}',
     '"gabriel": {"id": 5775491, "name": "Gabriel"},\n    "rafael":  {"id": None,    "name": "Rafael Lemos"},\n}'),
    # 2. Protótipo rafael (inserir antes do gabriel)
    ('''    "gabriel": {
        "kpis":{"ctl":58,"atl":72,"tsb":-14,"tss_week":380},''',
     '''    "rafael": {
        "kpis":{"ctl":0,"atl":0,"tsb":0,"tss_week":0},
        "kpi_delta":{"ctl":"\u2014","atl":"\u2014","tsb":"\u2014","tss_week":"\u2014"},
        "pmc":{"labels":["S1","S2","S3","S4","S5","S6","S7","S8"],
               "ctl":[0,0,0,0,0,0,0,0],"atl":[0,0,0,0,0,0,0,0],"tsb":[0,0,0,0,0,0,0,0]},
        "zones":{"labels":["Nata\u00e7\u00e3o","Bike","Corrida"],"z1":[80,80,80],"z2":[15,15,15],"z3":[5,5,5]},
        "vol":{"swim":0,"bike":0,"run":0,"strength":0},
        "hrv":{"labels":[],"vals":[],"baseline":0,"sleep":[],"resting_hr":[],"body_battery":[]},
        "adherence":[],
        "alerts":[{"type":"info","msg":"TP ID pendente \u2014 dados dispon\u00edveis ap\u00f3s integra\u00e7\u00e3o"}],
        "sessions":[],"planned":{},"week_notes":{}
    },
    "gabriel": {
        "kpis":{"ctl":58,"atl":72,"tsb":-14,"tss_week":380},'''),
    # 3. Skip atletas sem TP ID
    ('        try:\n            raw_w  = fetch_workouts(cfg["id"], days=75)',
     '        if cfg.get("id") is None:\n            print(f"    sem TP ID \u2014 usando prot\u00f3tipo vazio")\n            db[key] = json.loads(json.dumps(PROTOTYPE[key]))\n            continue\n        try:\n            raw_w  = fetch_workouts(cfg["id"], days=75)'),
]

for old, new in gen_changes:
    if old in g:
        g = g.replace(old, new)
        print(f"  OK: {old[:50]}...")
    else:
        print(f"  SKIP (não encontrado): {old[:50]}...")

with open('generate.py', 'w', encoding='utf-8') as f:
    f.write(g)
print("generate.py atualizado\n")

print("=== Patch concluído ===")
print("Agora execute: python generate.py")
print("Depois: git add -A && git commit -m 'feat: Rafael Lemos' && git push")
