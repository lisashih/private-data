"""
patch_app.py — 修正 Streamlit app.py 的兩個 bug
執行方式：在你的 GitHub repo 資料夾內執行 python3 patch_app.py
"""
import re

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

original = src
changes = []

# ── Fix 1a: session_state key conflict ──────────────────────────────────────
count_before = len(re.findall(r"session_state\[['\"]sel_s['\"]\]", src))
src = re.sub(r"session_state\[['\"]sel_s['\"]\]", "session_state['_qs']", src)
src = re.sub(r"session_state\[['\"]sel_e['\"]\]", "session_state['_qe']", src)
if count_before > 0:
    changes.append(f"✅ Fix 1a: sel_s→_qs, sel_e→_qe ({count_before} refs fixed)")

# ── Fix 1b: date_input key='sel_s'/'sel_e' remove key, change value ─────────
# sel_start line
before = src
src = re.sub(
    r"(sel_start\s*=\s*st\.date_input\s*\([^)]*?)value\s*=\s*[\w_]+",
    lambda m: m.group(0).replace(m.group(0).split('value=')[1].split(',')[0].strip(),
              '_def_s') if 'sel_s' in m.group(0) else m.group(0),
    src
)
# Simpler approach: just find and replace the key= argument in both lines
src = re.sub(r"(st\.date_input\s*\(['\"]開始['\"][^)]*?),\s*key\s*=\s*['\"]sel_s['\"](\s*\))",
             r"\1\2", src)
src = re.sub(r"(st\.date_input\s*\(['\"]結束['\"][^)]*?),\s*key\s*=\s*['\"]sel_e['\"](\s*\))",
             r"\1\2", src)
# Change value=min_d to value=_def_s and value=max_d to value=_def_e in date_inputs
src = re.sub(r"(st\.date_input\s*\(['\"]開始['\"][^)]*?)value\s*=\s*min_d",
             r"\1value=_def_s", src)
src = re.sub(r"(st\.date_input\s*\(['\"]結束['\"][^)]*?)value\s*=\s*max_d",
             r"\1value=_def_e", src)
if src != before:
    changes.append("✅ Fix 1b: Removed key='sel_s'/'sel_e' from date_input, updated values")

# ── Fix 1c: inject _def_s/_def_e before date_input if not present ───────────
if "session_state.get('_qs'" not in src and "_def_s" in src:
    inject = (
        "\n        # 快速選取預設值\n"
        "        _def_s = st.session_state.get('_qs', min_d)\n"
        "        _def_e = st.session_state.get('_qe', max_d)\n"
        "        _def_s = max(min_d, min(_def_s, max_d))\n"
        "        _def_e = max(min_d, min(_def_e, max_d))\n"
    )
    src = re.sub(r'(\n        col_s, col_e = st\.columns\(2\))', inject + r'\1', src, count=1)
    changes.append("✅ Fix 1c: Injected _def_s/_def_e definitions")
elif "session_state.get('_qs'" in src:
    changes.append("ℹ️  Fix 1c: _def_s definitions already present")

# ── Fix 2: funnel asa_c 'dl' column guard ────────────────────────────────────
old_f = re.compile(
    r"asa_c\[\['clk','dl','jin','wan'\]\]\.rename\(columns=\{'dl':'mid'\}\)"
    r" if not asa_c\.empty else pd\.DataFrame\(\),"
)
new_f = (
    "asa_c[['clk','dl','jin','wan']].rename(columns={'dl':'mid'}) "
    "if (not asa_c.empty and 'dl' in asa_c.columns) "
    "else (asa_c[['clk','jin','wan']].assign(mid=0) if not asa_c.empty else pd.DataFrame()),"
)
if old_f.search(src):
    src = old_f.sub(new_f, src)
    changes.append("✅ Fix 2: Funnel asa_c 'dl' column guard added")
elif "'dl' in asa_c.columns" in src:
    changes.append("ℹ️  Fix 2: Already patched")
else:
    changes.append("⚠️  Fix 2: Pattern not found — check funnel code manually at all_camp = pd.concat()")

# ── Save ─────────────────────────────────────────────────────────────────────
print("Results:")
for c in changes:
    print(" ", c)

if src != original:
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(src)
    print(f"\n✅ app.py saved ({len(src)} bytes)")
    print("Next: git add app.py && git commit -m 'fix: session_state and funnel' && git push")
else:
    print("\n⚠️  No changes — may already be patched or patterns not matched.")
