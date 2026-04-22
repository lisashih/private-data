"""
口袋證券廣告成效儀表板
平台：ASA / Google KW / Google PMax
時間維度：手動選擇日期區間
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from data_processor import (
    load_data, filter_dates,
    sdiv, fmt_money, fmt_num, wow_pct, shorten_camp,
    build_conv_report, build_conv_report_day
)

# ══════════════════════════════════════════════════════
# 頁面設定
# ══════════════════════════════════════════════════════
st.set_page_config(
    page_title="口袋證券廣告儀表板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="block-container"] { padding-top: 1.2rem; }
.kpi {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 14px 18px 10px;
    height: 100%;
}
.kpi-label { font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: .05em; font-weight: 500; }
.kpi-value { font-size: 22px; font-weight: 700; color: #0F172A; margin: 4px 0 2px; line-height: 1.2; }
.kpi-sub   { font-size: 11px; color: #94A3B8; }
.kpi-wow   { font-size: 12px; font-weight: 600; }
.kpi-wow.up { color: #16A34A; }
.kpi-wow.dn { color: #DC2626; }
.kpi-wow.na { color: #94A3B8; }
.note-box {
    background: #FFF7ED;
    border-left: 3px solid #F97316;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
    color: #7C2D12;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

C = {'asa': '#2563EB', 'kw': '#D97706', 'pmax': '#16A34A', 'up': '#16A34A', 'dn': '#DC2626'}


# ══════════════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════════════
def kpi_card(label, val, wow=None, good_down=False, sub=""):
    if wow is not None:
        arrow = '▲' if wow > 0 else '▼'
        good  = (wow < 0) if good_down else (wow > 0)
        wcls  = 'up' if good else 'dn'
        wow_html = f'<div class="kpi-wow {wcls}">{arrow} {abs(wow):.1f}% vs 對比期</div>'
    else:
        wow_html = '<div class="kpi-wow na">—</div>'
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ''
    return f"""<div class="kpi">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{val}</div>
  {wow_html}{sub_html}
</div>"""


def kpi_row(items):
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label   = item[0]
        val     = item[1]
        wow     = item[2] if len(item) > 2 else None
        gd      = item[3] if len(item) > 3 else False
        sub     = item[4] if len(item) > 4 else ""
        col.markdown(kpi_card(label, val, wow, gd, sub), unsafe_allow_html=True)


def sc(df, col, default=0):
    if df.empty or col not in df.columns: return default
    return float(df[col].sum())

def sec(title):
    st.markdown(f"#### {title}")



def daily_bar(daily_cur, daily_cmp, col, color, height=260):
    fig = go.Figure()
    if daily_cmp is not None and not daily_cmp.empty:
        fig.add_trace(go.Bar(
            name='對比期', x=daily_cmp['date_str'], y=daily_cmp[col],
            marker_color='#CBD5E1', opacity=0.6
        ))
    if not daily_cur.empty:
        fig.add_trace(go.Bar(
            name='選取期', x=daily_cur['date_str'], y=daily_cur[col],
            marker_color=color
        ))
    fig.update_layout(
        height=height, margin=dict(t=10, b=30, l=0, r=0),
        barmode='overlay', legend=dict(orientation='h', y=1.08),
        xaxis_title='', yaxis_title=col,
    )
    return fig


def daily_line(daily_cur, daily_cmp, col, color, height=240):
    fig = go.Figure()
    if daily_cmp is not None and not daily_cmp.empty and col in daily_cmp.columns:
        fig.add_trace(go.Scatter(
            name='對比期', x=daily_cmp['date_str'], y=daily_cmp[col],
            mode='lines', line=dict(color='#CBD5E1', width=1.5, dash='dot')
        ))
    if not daily_cur.empty and col in daily_cur.columns:
        fig.add_trace(go.Scatter(
            name='選取期', x=daily_cur['date_str'], y=daily_cur[col],
            mode='lines+markers', line=dict(color=color, width=2), marker=dict(size=4)
        ))
    fig.update_layout(
        height=height, margin=dict(t=10, b=30, l=0, r=0),
        legend=dict(orientation='h', y=1.08),
        xaxis_title='', yaxis_title=col,
    )
    return fig


# ══════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 口袋證券廣告儀表板")
    st.markdown("---")

    uploaded = st.file_uploader(
        "📂 上傳廣告資料 (.xlsx)",
        type=["xlsx"],
        help="包含 ASA / Google KW / Google Pmax / 進件數完開數 四個分頁"
    )

    if uploaded:
        with st.spinner("載入資料..."):
            try:
                data = load_data(uploaded)
                meta = data.get('meta', {})
            except Exception as e:
                st.error(f"❌ 讀取失敗：{e}")
                st.stop()

        if not meta:
            st.error("❌ 找不到有效日期資料")
            st.stop()

        min_d = date.fromisoformat(meta['min_date'])
        max_d = date.fromisoformat(meta['max_date'])

        st.markdown("---")
        st.markdown("**📅 選取期間**")

        # 快速選擇按鈕（先於 date_input，設 internal state）
        st.caption("快速選取：")
        qcols = st.columns(3)
        if qcols[0].button("本月", use_container_width=True):
            ms = max_d.replace(day=1)
            st.session_state['_qs'] = ms
            st.session_state['_qe'] = max_d
            # 對比上個月同期
            import calendar
            prev_month = ms.replace(day=1) - timedelta(days=1)
            prev_ms = prev_month.replace(day=1)
            prev_me = min(prev_month, prev_ms.replace(day=ms.day - 1) if ms.day > 1 else prev_month)
            st.session_state['_cs'] = max(min_d, prev_ms)
            st.session_state['_ce'] = max(min_d, prev_me)
            st.session_state['_use_cmp'] = True
            st.rerun()
        if qcols[1].button("近7天", use_container_width=True):
            qs = max(min_d, max_d - timedelta(days=6))
            st.session_state['_qs'] = qs
            st.session_state['_qe'] = max_d
            # 對比前7天
            st.session_state['_cs'] = max(min_d, qs - timedelta(days=7))
            st.session_state['_ce'] = max(min_d, qs - timedelta(days=1))
            st.session_state['_use_cmp'] = True
            st.rerun()
        if qcols[2].button("近14天", use_container_width=True):
            qs = max(min_d, max_d - timedelta(days=13))
            st.session_state['_qs'] = qs
            st.session_state['_qe'] = max_d
            # 對比前14天
            st.session_state['_cs'] = max(min_d, qs - timedelta(days=14))
            st.session_state['_ce'] = max(min_d, qs - timedelta(days=1))
            st.session_state['_use_cmp'] = True
            st.rerun()

        # 初始預設值：從 quick-select state 取，否則用資料範圍
        _def_s = st.session_state.get('_qs', min_d)
        _def_e = st.session_state.get('_qe', max_d)
        # 確保在資料範圍內
        _def_s = max(min_d, min(_def_s, max_d))
        _def_e = max(min_d, min(_def_e, max_d))

        col_s, col_e = st.columns(2)
        with col_s:
            sel_start = st.date_input("開始", value=_def_s, min_value=min_d, max_value=max_d)
        with col_e:
            sel_end = st.date_input("結束", value=_def_e, min_value=min_d, max_value=max_d)

        if sel_start > sel_end:
            st.error("開始日期不能晚於結束日期")
            st.stop()

        st.markdown("---")
        st.markdown("**📊 對比期間**")
        _use_cmp_def = st.session_state.get('_use_cmp', False)
        use_cmp = st.checkbox("啟用對比", value=_use_cmp_def)
        cmp_start = cmp_end = None
        if use_cmp:
            _def_cs = st.session_state.get('_cs', min_d)
            _def_ce = st.session_state.get('_ce', min_d + timedelta(days=(sel_end - sel_start).days))
            _def_cs = max(min_d, min(_def_cs, max_d))
            _def_ce = max(min_d, min(_def_ce, max_d))
            cmp_col1, cmp_col2 = st.columns(2)
            with cmp_col1:
                cmp_start = st.date_input("對比開始", value=_def_cs, min_value=min_d, max_value=max_d, key='cmp_s')
            with cmp_col2:
                cmp_end = st.date_input("對比結束", value=_def_ce, min_value=min_d, max_value=max_d, key='cmp_e')

        st.markdown("---")
        st.markdown("**💰 預算設定（本月，NT$）**")

        # 預設預算
        BUDGET_DEFAULT = {'品牌字': 350000, '廣字': 235000, '投資入門': 15000,
                          'PMAX': 300000, 'ASA 台股字': 300000, 'ASA 美股字': 50000}

        # 從 session_state 讀取已儲存的預算，第一次用預設值
        if 'budget_plan' not in st.session_state:
            st.session_state['budget_plan'] = dict(BUDGET_DEFAULT)

        BUDGET = {}
        budget_actual = {}
        for k, default_bud in BUDGET_DEFAULT.items():
            col_bud, col_act = st.columns(2)
            with col_bud:
                new_bud = st.number_input(
                    f"{k} 預算", min_value=0, max_value=2000000,
                    value=st.session_state['budget_plan'].get(k, default_bud),
                    step=5000, key=f'plan_{k}'
                )
                BUDGET[k] = new_bud
                st.session_state['budget_plan'][k] = new_bud
            with col_act:
                budget_actual[k] = st.number_input(
                    f"{k} 實際", min_value=0, max_value=2000000,
                    value=0, step=5000, key=f'b_{k}'
                )

        st.markdown("---")
        st.caption(f"資料區間：{meta['min_date']} ~ {meta['max_date']}\n產生時間：{meta['generated']}")
    else:
        data = None
        meta = {}


# ══════════════════════════════════════════════════════
# 主畫面
# ══════════════════════════════════════════════════════
st.title("📊 口袋證券廣告成效儀表板")

if not data:
    st.info("👈 請從左側上傳 `廣告raw.xlsx` 開始分析")
    with st.expander("📋 xlsx 格式說明", expanded=True):
        st.markdown("""
| 分頁 | 必要欄位 |
|------|---------|
| **ASA** | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 下載數, 花費（台幣） |
| **Google KW** | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 花費 |
| **Google Pmax** | Date, 廣告活動, 曝光, 點擊, 花費 |
| **進件數完開數** | Date, 平台, 廣告活動, 進件數, 完開數 ⭐ 手填轉換資料 |

> **⚠️ 進件數/完開數** 在關鍵字層級無法匹配，只在廣告活動層級有效。
""")
    st.stop()

# ── 日期字串 ─────────────────────────────────────────
S = sel_start.isoformat()
E = sel_end.isoformat()
CS = cmp_start.isoformat() if cmp_start else None
CE = cmp_end.isoformat()   if cmp_end   else None

st.caption(
    f"**選取期間：{S} → {E}**"
    + (f"　｜　對比期間：{CS} → {CE}" if use_cmp and CS else "")
    + f"　｜　資料區間：{meta['min_date']} ~ {meta['max_date']}"
)

# ── 取出全量資料 ──────────────────────────────────────
asa_daily_all = data.get('asa_daily', pd.DataFrame())
asa_camp_all  = data.get('asa_camp',  pd.DataFrame())
asa_kw_all    = data.get('asa_kw',    pd.DataFrame())
asa_raw_all   = data.get('asa_raw',   pd.DataFrame())
kw_daily_all  = data.get('kw_daily',  pd.DataFrame())
kw_camp_all   = data.get('kw_camp',   pd.DataFrame())
kw_kw_all     = data.get('kw_kw',     pd.DataFrame())
kw_raw_all    = data.get('kw_raw',    pd.DataFrame())
pm_daily_all  = data.get('pm_daily',  pd.DataFrame())
pm_camp_all   = data.get('pm_camp',   pd.DataFrame())
pm_raw_all    = data.get('pm_raw',    pd.DataFrame())
conv_raw      = data.get('conv_raw',  pd.DataFrame())
conv_day      = data.get('conv_day',  pd.DataFrame())
conv_week     = data.get('conv_week', pd.DataFrame())

# ── 篩選選取期 ────────────────────────────────────────
asa_d  = filter_dates(asa_daily_all, 'date_str', S, E)
kw_d   = filter_dates(kw_daily_all,  'date_str', S, E)
pm_d   = filter_dates(pm_daily_all,  'date_str', S, E)

# 廣告活動層級：從篩選後的 raw 重新聚合，jin/wan 從 data_processor 的 camp 結果合併
asa_raw_f = filter_dates(asa_raw_all, 'date_str', S, E)
kw_raw_f  = filter_dates(kw_raw_all,  'date_str', S, E)
pm_raw_f  = filter_dates(pm_raw_all,  'date_str', S, E)

def _reagg(raw_f, group_cols, extra_cols=None):
    if raw_f.empty: return pd.DataFrame()
    agg = {'spend': ('spend','sum'), 'imp': ('imp','sum'), 'clk': ('clk','sum')}
    if extra_cols:
        for c in extra_cols:
            if c in raw_f.columns:
                agg[c] = (c, 'sum')
    return raw_f.groupby(group_cols).agg(**agg).reset_index()

# ASA camp：從 raw 聚合花費/曝光/點擊/下載，再從全期 asa_camp_all 合併 jin/wan
_asa_base = _reagg(asa_raw_f, ['廣告活動'], ['dl'])
if not _asa_base.empty:
    _asa_base['CTR%'] = _asa_base.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    _asa_base['CPI']  = _asa_base.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    if not asa_camp_all.empty and 'jin' in asa_camp_all.columns:
        _cols = [c for c in ['廣告活動','jin','wan','shidong'] if c in asa_camp_all.columns]
        _asa_base = _asa_base.merge(asa_camp_all[_cols], on='廣告活動', how='left')
    for col in ['jin','wan','shidong']:
        if col not in _asa_base.columns: _asa_base[col] = 0
    _asa_base[['jin','wan','shidong']] = _asa_base[['jin','wan','shidong']].fillna(0)
    _asa_base['CPL'] = _asa_base.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
asa_c = _asa_base

# KW camp
_kw_base = _reagg(kw_raw_f, ['廣告活動','camp_short'])
if not _kw_base.empty:
    _kw_base['CTR%'] = _kw_base.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    _kw_base['CPC']  = _kw_base.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    if not kw_camp_all.empty and 'jin' in kw_camp_all.columns:
        _cols = [c for c in ['廣告活動','camp_short','jin','wan','shidong'] if c in kw_camp_all.columns]
        _kw_base = _kw_base.merge(kw_camp_all[_cols], on=['廣告活動','camp_short'], how='left')
    for col in ['jin','wan','shidong']:
        if col not in _kw_base.columns: _kw_base[col] = 0
    _kw_base[['jin','wan','shidong']] = _kw_base[['jin','wan','shidong']].fillna(0)
    _kw_base['CPL'] = _kw_base.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
kw_c = _kw_base

# PMax camp
_pm_base = _reagg(pm_raw_f, ['廣告活動'])
if not _pm_base.empty:
    _pm_base['CTR%'] = _pm_base.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    _pm_base['CPC']  = _pm_base.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    if not pm_camp_all.empty and 'jin' in pm_camp_all.columns:
        _cols = [c for c in ['廣告活動','jin','wan','shidong'] if c in pm_camp_all.columns]
        _pm_base = _pm_base.merge(pm_camp_all[_cols], on='廣告活動', how='left')
    for col in ['jin','wan','shidong']:
        if col not in _pm_base.columns: _pm_base[col] = 0
    _pm_base[['jin','wan','shidong']] = _pm_base[['jin','wan','shidong']].fillna(0)
    _pm_base['CPL'] = _pm_base.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
pm_c = _pm_base

# 關鍵字層級
def _asa_kw(raw_f):
    if raw_f.empty: return pd.DataFrame()
    k = raw_f.groupby(['廣告活動','廣告群組','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()
    k['CTR%'] = k.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    k['CPI']  = k.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    return k.sort_values('spend', ascending=False)

def _kw_kw(raw_f):
    if raw_f.empty: return pd.DataFrame()
    k = raw_f.groupby(['camp_short','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    k['CTR%'] = k.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    k['CPC']  = k.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    return k.sort_values('spend', ascending=False)

asa_kw_f = _asa_kw(asa_raw_f)
kw_kw_f  = _kw_kw(kw_raw_f)

# ── 篩選對比期 ────────────────────────────────────────
asa_d_c = filter_dates(asa_daily_all, 'date_str', CS, CE) if use_cmp and CS else None
kw_d_c  = filter_dates(kw_daily_all,  'date_str', CS, CE) if use_cmp and CS else None
pm_d_c  = filter_dates(pm_daily_all,  'date_str', CS, CE) if use_cmp and CS else None

def cmp_spend(daily_c):
    if daily_c is None or daily_c.empty: return 0
    return float(daily_c['spend'].sum()) if 'spend' in daily_c.columns else 0
def cmp_clk(daily_c):
    if daily_c is None or daily_c.empty: return 0
    return float(daily_c['clk'].sum()) if 'clk' in daily_c.columns else 0




# ══════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════
t_ov, t_asa, t_kw, t_pm, t_budget, t_conv, t_weekly = st.tabs([
    "🏠 總覽", "🍎 ASA", "🔍 Google KW", "⚡ Google PMax", "💰 預算進度", "🔄 轉換分析", "📅 進件數完開數"
])


# ════════════════════════════════════════════════════
# 總覽
# ════════════════════════════════════════════════════
with t_ov:
    st.subheader(f"全平台加總　{S} – {E}")

    asa_sp = sc(asa_d, 'spend');  asa_sp_c = cmp_spend(asa_d_c)
    kw_sp  = sc(kw_d,  'spend');  kw_sp_c  = cmp_spend(kw_d_c)
    pm_sp  = sc(pm_d,  'spend');  pm_sp_c  = cmp_spend(pm_d_c)
    total  = asa_sp + kw_sp + pm_sp
    total_c = asa_sp_c + kw_sp_c + pm_sp_c

    asa_clk = sc(asa_d, 'clk');  asa_clk_c = cmp_clk(asa_d_c)
    kw_clk  = sc(kw_d,  'clk');  kw_clk_c  = cmp_clk(kw_d_c)
    pm_clk  = sc(pm_d,  'clk');  pm_clk_c  = cmp_clk(pm_d_c)
    total_clk = asa_clk + kw_clk + pm_clk
    total_clk_c = asa_clk_c + kw_clk_c + pm_clk_c

    asa_dl = sc(asa_d, 'dl')

    total_jin = sc(asa_c, 'jin') + sc(kw_c, 'jin') + sc(pm_c, 'jin')
    total_wan = sc(asa_c, 'wan') + sc(kw_c, 'wan') + sc(pm_c, 'wan')

    kpi_row([
        ("總花費",   fmt_money(total),     wow_pct(total, total_c) if use_cmp else None, True),
        ("總點擊",   fmt_num(total_clk),   wow_pct(total_clk, total_clk_c) if use_cmp else None),
        ("ASA 下載", fmt_num(asa_dl),      None),
        ("進件數",   fmt_num(total_jin),   None, False, "廣告活動層級"),
        ("完開數",   fmt_num(total_wan),   None, False, "廣告活動層級"),
    ])

    st.markdown("---")

    # 每日花費趨勢（堆疊 bar）
    st.markdown(f"#### 每日花費趨勢　{S} – {E}")
    all_d_cur = sorted(set(
        (asa_d['date_str'].tolist() if not asa_d.empty else []) +
        (kw_d['date_str'].tolist()  if not kw_d.empty  else []) +
        (pm_d['date_str'].tolist()  if not pm_d.empty  else [])
    ))
    if all_d_cur:
        def get_d(df, col='spend'):
            m = dict(zip(df['date_str'], df[col])) if not df.empty and col in df.columns else {}
            return [m.get(d, 0) for d in all_d_cur]

        fig = go.Figure()
        fig.add_trace(go.Bar(name='ASA',       x=all_d_cur, y=get_d(asa_d), marker_color=C['asa']))
        fig.add_trace(go.Bar(name='Google KW', x=all_d_cur, y=get_d(kw_d),  marker_color=C['kw']))
        fig.add_trace(go.Bar(name='PMax',      x=all_d_cur, y=get_d(pm_d),  marker_color=C['pmax']))
        fig.update_layout(barmode='stack', height=300, margin=dict(t=10, b=30, l=0, r=0),
                          legend=dict(orientation='h', y=1.08), yaxis_title='NT$')
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 花費佔比")
        pie_df = pd.DataFrame({
            '平台': ['ASA', 'Google KW', 'PMax'],
            '花費': [asa_sp, kw_sp, pm_sp],
        })
        fig_p = px.pie(pie_df, values='花費', names='平台',
                       color='平台',
                       color_discrete_map={'ASA': C['asa'], 'Google KW': C['kw'], 'PMax': C['pmax']},
                       hole=0.42)
        fig_p.update_layout(height=260, margin=dict(t=10, b=10))
        st.plotly_chart(fig_p, use_container_width=True)

    with col2:
        if use_cmp and total_c > 0:
            st.markdown("#### 各平台花費對比")
            cmp_df = pd.DataFrame({
                '平台': ['ASA','Google KW','PMax'],
                '選取期': [asa_sp,  kw_sp,  pm_sp],
                '對比期': [asa_sp_c, kw_sp_c, pm_sp_c],
            })
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(name='選取期', x=cmp_df['平台'], y=cmp_df['選取期'],
                                     marker_color=[C['asa'], C['kw'], C['pmax']]))
            fig_cmp.add_trace(go.Bar(name='對比期', x=cmp_df['平台'], y=cmp_df['對比期'],
                                     marker_color='#CBD5E1'))
            fig_cmp.update_layout(height=260, margin=dict(t=10, b=10), barmode='group',
                                  yaxis_title='NT$')
            st.plotly_chart(fig_cmp, use_container_width=True)
        else:
            st.markdown("#### 各平台點擊比較")
            bar_df = pd.DataFrame({
                '平台':  ['ASA', 'Google KW', 'PMax'],
                '點擊':  [asa_clk, kw_clk, pm_clk],
            })
            fig_b = px.bar(bar_df, x='平台', y='點擊',
                           color='平台',
                           color_discrete_map={'ASA': C['asa'], 'Google KW': C['kw'], 'PMax': C['pmax']})
            fig_b.update_layout(height=260, margin=dict(t=10, b=10), showlegend=False)
            st.plotly_chart(fig_b, use_container_width=True)


# ════════════════════════════════════════════════════
# ASA
# ════════════════════════════════════════════════════
with t_asa:
    st.subheader(f"🍎 Apple Search Ads　{S} – {E}")

    if asa_c.empty and asa_d.empty:
        st.warning("此期間無 ASA 資料")
    else:
        tot_sp = sc(asa_d, 'spend');  tot_sp_c = cmp_spend(asa_d_c)
        tot_dl = sc(asa_d, 'dl');     tot_imp  = sc(asa_d, 'imp')
        tot_clk = sc(asa_d, 'clk')
        ctr = sdiv(tot_clk, tot_imp, 100)
        cpi = sdiv(tot_sp, tot_dl, 1, 0)

        kpi_row([
            ("花費台幣", fmt_money(tot_sp),  wow_pct(tot_sp, tot_sp_c) if use_cmp else None, True),
            ("曝光",    fmt_num(tot_imp),   None),
            ("點擊",    fmt_num(tot_clk),   None),
            ("下載數",  fmt_num(tot_dl),    None),
            ("CTR%",   f"{ctr:.2f}%",      None),
            ("CPI",    fmt_money(cpi),     None, True),
        ])

        if sc(asa_c, 'jin') > 0:
            jin = sc(asa_c, 'jin'); wan = sc(asa_c, 'wan')
            st.markdown("**轉換指標（廣告活動層級）**")
            kpi_row([
                ("進件數",  fmt_num(jin),  None),
                ("完開數",  fmt_num(wan),  None),
                ("CPL",   fmt_money(sdiv(tot_sp, jin, 1, 0)), None, True),
                ("進件率%", f"{sdiv(jin, tot_dl, 100):.1f}%", None),
                ("完開率%", f"{sdiv(wan, jin, 100):.1f}%",    None),
            ])
        else:
            st.markdown('<div class="note-box">💡 進件數/完開數尚未填入「進件數完開數」分頁，或此期間無轉換資料</div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns([1.2, 1])

        with col1:
            st.markdown("#### 廣告活動明細")
            if not asa_c.empty:
                cols_show = [c for c in ['廣告活動','spend','dl','CTR%','CPI','jin','wan','CPL','進件率%','完開率%'] if c in asa_c.columns]
                disp = asa_c[cols_show].copy()
                rename = {'spend':'花費台幣','dl':'下載數','jin':'進件數','wan':'完開數'}
                disp.rename(columns=rename, inplace=True)
                disp['花費台幣'] = disp['花費台幣'].apply(lambda x: f"NT${x:,.0f}")
                disp['CPI']     = disp['CPI'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
                if 'CPL' in disp.columns:
                    disp['CPL'] = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
                st.dataframe(disp, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("#### CPI 比較（NT$/下載）")
            if not asa_c.empty and 'CPI' in asa_c.columns:
                cc = asa_c[asa_c['CPI'] > 0].sort_values('CPI', ascending=True)
                if not cc.empty:
                    clrs = ['#DC2626' if v > 1000 else '#F59E0B' if v > 500 else '#16A34A' for v in cc['CPI']]
                    fig = go.Figure(go.Bar(
                        x=cc['CPI'], y=cc['廣告活動'], orientation='h', marker_color=clrs,
                        text=[f"NT${v:,.0f}" for v in cc['CPI']], textposition='outside'
                    ))
                    fig.add_vline(x=500,  line_dash='dash', line_color='#F59E0B', annotation_text='500')
                    fig.add_vline(x=1000, line_dash='dash', line_color='#DC2626', annotation_text='1000')
                    fig.update_layout(height=max(240, len(cc)*45+60),
                                      margin=dict(t=10, b=10, r=80), showlegend=False, xaxis_title='CPI (NT$)')
                    st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 每日下載數趨勢")
        st.plotly_chart(daily_bar(asa_d, asa_d_c, 'dl', C['asa']), use_container_width=True)

        st.markdown("---")
        st.markdown("#### 關鍵字效益（流量指標）")
        st.markdown('<div class="note-box">⚠️ 關鍵字層級無法匹配進件數/完開數，轉換指標請看上方廣告活動層級</div>', unsafe_allow_html=True)
        if not asa_kw_f.empty:
            k_disp = asa_kw_f[['廣告活動','廣告關鍵字','spend','imp','clk','dl','CTR%','CPI']].head(60).copy()
            k_disp.columns = ['廣告活動','關鍵字','花費台幣','曝光','點擊','下載數','CTR%','CPI']
            k_disp['花費台幣'] = k_disp['花費台幣'].apply(lambda x: f"NT${x:,.0f}")
            k_disp['CPI']     = k_disp['CPI'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
            st.dataframe(k_disp, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════
# Google KW
# ════════════════════════════════════════════════════
with t_kw:
    st.subheader(f"🔍 Google Keyword　{S} – {E}")

    if kw_c.empty and kw_d.empty:
        st.warning("此期間無 Google KW 資料")
    else:
        tot_sp  = sc(kw_d, 'spend'); tot_sp_c = cmp_spend(kw_d_c)
        tot_imp = sc(kw_d, 'imp');   tot_clk  = sc(kw_d, 'clk')
        ctr = sdiv(tot_clk, tot_imp, 100)
        cpc = sdiv(tot_sp, tot_clk, 1, 1)

        kpi_row([
            ("花費",  fmt_money(tot_sp),  wow_pct(tot_sp, tot_sp_c) if use_cmp else None, True),
            ("曝光",  fmt_num(tot_imp),  None),
            ("點擊",  fmt_num(tot_clk),  None),
            ("CTR%", f"{ctr:.2f}%",     None),
            ("CPC",  fmt_money(cpc),    None, True),
        ])

        if sc(kw_c, 'jin') > 0:
            jin = sc(kw_c, 'jin'); wan = sc(kw_c, 'wan')
            st.markdown("**轉換指標（廣告活動層級）**")
            kpi_row([
                ("進件數",  fmt_num(jin),  None),
                ("完開數",  fmt_num(wan),  None),
                ("CPL",   fmt_money(sdiv(tot_sp, jin, 1, 0)), None, True),
                ("進件率%", f"{sdiv(jin, tot_clk, 100):.2f}%", None),
                ("完開率%", f"{sdiv(wan, jin, 100):.1f}%",     None),
            ])
        else:
            st.markdown('<div class="note-box">💡 進件數/完開數尚未填入「進件數完開數」分頁，或此期間無轉換資料</div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.markdown("#### 廣告活動明細")
            if not kw_c.empty:
                c_show = ['廣告活動','camp_short','spend','imp','clk','CTR%','CPC']
                if 'jin' in kw_c.columns: c_show += ['jin','wan','CPL','進件率%','完開率%']
                disp = kw_c[[c for c in c_show if c in kw_c.columns]].copy()
                disp.rename(columns={'camp_short':'活動簡稱','spend':'花費','imp':'曝光','clk':'點擊','jin':'進件數','wan':'完開數'}, inplace=True)
                if '花費' in disp.columns: disp['花費'] = disp['花費'].apply(lambda x: f"NT${x:,.0f}")
                if 'CPL'  in disp.columns: disp['CPL']  = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
                st.dataframe(disp, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("#### 廣告活動花費比較")
            if not kw_c.empty:
                fc = kw_c.sort_values('spend', ascending=True).tail(10)
                fig = go.Figure(go.Bar(
                    x=fc['spend'], y=fc['camp_short'], orientation='h',
                    marker_color=C['kw'],
                    text=[f"NT${v:,.0f}" for v in fc['spend']], textposition='outside'
                ))
                fig.update_layout(height=max(240, len(fc)*42+60),
                                  margin=dict(t=10, b=10, r=80), showlegend=False, xaxis_title='花費 (NT$)')
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 每日點擊趨勢")
        st.plotly_chart(daily_line(kw_d, kw_d_c, 'clk', C['kw']), use_container_width=True)

        st.markdown("---")
        st.markdown("#### 關鍵字明細（純流量指標）")
        st.markdown('<div class="note-box">⚠️ 關鍵字層級無法匹配進件數/完開數，轉換指標請看上方廣告活動層級</div>', unsafe_allow_html=True)
        if not kw_kw_f.empty:
            k_disp = kw_kw_f[['camp_short','廣告關鍵字','spend','imp','clk','CTR%','CPC']].head(60).copy()
            k_disp.columns = ['活動','關鍵字','花費','曝光','點擊','CTR%','CPC']
            k_disp['花費'] = k_disp['花費'].apply(lambda x: f"NT${x:,.0f}")
            k_disp['CPC']  = k_disp['CPC'].apply(lambda x: f"NT${x:,.1f}" if x > 0 else '–')
            st.dataframe(k_disp, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════
# Google PMax
# ════════════════════════════════════════════════════
with t_pm:
    st.subheader(f"⚡ Google PMax　{S} – {E}")

    if pm_c.empty and pm_d.empty:
        st.warning("此期間無 PMax 資料")
    else:
        tot_sp  = sc(pm_d, 'spend'); tot_sp_c = cmp_spend(pm_d_c)
        tot_imp = sc(pm_d, 'imp');   tot_clk  = sc(pm_d, 'clk')
        ctr = sdiv(tot_clk, tot_imp, 100)
        cpc = sdiv(tot_sp, tot_clk, 1, 1)

        kpi_row([
            ("花費",  fmt_money(tot_sp),  wow_pct(tot_sp, tot_sp_c) if use_cmp else None, True),
            ("曝光",  fmt_num(tot_imp),  None),
            ("點擊",  fmt_num(tot_clk),  None),
            ("CTR%", f"{ctr:.2f}%",     None),
            ("CPC",  fmt_money(cpc),    None, True),
        ])

        if sc(pm_c, 'jin') > 0:
            jin = sc(pm_c, 'jin'); wan = sc(pm_c, 'wan')
            st.markdown("**轉換指標（廣告活動層級）**")
            kpi_row([
                ("進件數",  fmt_num(jin), None),
                ("完開數",  fmt_num(wan), None),
                ("CPL",   fmt_money(sdiv(tot_sp, jin, 1, 0)), None, True),
                ("完開率%", f"{sdiv(wan, jin, 100):.1f}%", None),
            ])
        else:
            st.markdown('<div class="note-box">💡 進件數/完開數尚未填入「進件數完開數」分頁，或此期間無轉換資料</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 每日點擊 & 花費")
        if not pm_d.empty:
            fig = go.Figure()
            if pm_d_c is not None and not pm_d_c.empty:
                fig.add_trace(go.Bar(name='點擊（對比期）', x=pm_d_c['date_str'], y=pm_d_c['clk'],
                                     marker_color='#D1FAE5', yaxis='y'))
            fig.add_trace(go.Bar(name='點擊（選取期）', x=pm_d['date_str'], y=pm_d['clk'],
                                 marker_color='#86EFAC', yaxis='y'))
            fig.add_trace(go.Scatter(name='花費（選取期）', x=pm_d['date_str'], y=pm_d['spend'],
                                     mode='lines+markers', line=dict(color=C['pmax'], width=2),
                                     marker=dict(size=4), yaxis='y2'))
            fig.update_layout(
                height=300, margin=dict(t=10, b=30, l=0, r=0), barmode='overlay',
                yaxis=dict(title='點擊'),
                yaxis2=dict(title='花費 (NT$)', overlaying='y', side='right', showgrid=False),
                legend=dict(orientation='h', y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 廣告活動明細")
        if not pm_c.empty:
            c_show = ['廣告活動','spend','imp','clk','CTR%','CPC']
            if 'jin' in pm_c.columns: c_show += ['jin','wan','CPL','完開率%']
            disp = pm_c[[c for c in c_show if c in pm_c.columns]].copy()
            disp.rename(columns={'spend':'花費','imp':'曝光','clk':'點擊','jin':'進件數','wan':'完開數'}, inplace=True)
            if '花費' in disp.columns: disp['花費'] = disp['花費'].apply(lambda x: f"NT${x:,.0f}")
            if 'CPC'  in disp.columns: disp['CPC']  = disp['CPC'].apply(lambda x: f"NT${x:,.1f}")
            if 'CPL'  in disp.columns: disp['CPL']  = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
            st.dataframe(disp, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════
# 預算進度
# ════════════════════════════════════════════════════
with t_budget:
    st.subheader("💰 預算進度追蹤（本月）")

    google_act = sum(budget_actual.get(k, 0) for k in ['品牌字','廣字','投資入門','PMAX'])
    asa_act    = sum(budget_actual.get(k, 0) for k in ['ASA 台股字','ASA 美股字'])
    total_act  = google_act + asa_act
    total_bud  = sum(BUDGET.values())

    c1, c2, c3 = st.columns(3)
    for col, (lbl, act, bud) in zip([c1, c2, c3], [
        ('Google 合計', google_act, 900000),
        ('ASA 合計',    asa_act,    350000),
        ('全渠道合計',  total_act,  total_bud),
    ]):
        pct = act / bud * 100 if bud else 0
        color = '#DC2626' if pct > 100 else '#D97706' if pct > 85 else '#16A34A'
        col.markdown(f"""<div class="kpi">
  <div class="kpi-label">{lbl}</div>
  <div class="kpi-value">NT${act:,}</div>
  <div class="kpi-sub">預算 NT${bud:,}</div>
  <div style="font-size:18px;font-weight:700;color:{color}">{pct:.1f}%{'  ⚠️' if pct>100 else ''}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 各項目進度條")
    for k, bud in BUDGET.items():
        act = budget_actual.get(k, 0)
        pct = min(act / bud * 100, 100) if bud else 0
        over = act > bud
        bar_color = '#DC2626' if over else '#2563EB'
        st.markdown(f"""<div style="margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
    <span style="font-weight:500">{k}</span>
    <span style="color:#64748B">NT${act:,} / NT${bud:,} &nbsp;
      <span style="color:{'#DC2626' if over else '#0F172A'};font-weight:600">{pct:.1f}%{'  ⚠️' if over else ''}</span>
    </span>
  </div>
  <div style="background:#E2E8F0;border-radius:99px;height:8px;overflow:hidden">
    <div style="background:{bar_color};width:{pct:.1f}%;height:100%;border-radius:99px"></div>
  </div>
</div>""", unsafe_allow_html=True)

    # 全渠道總進度
    total_pct = total_act / total_bud * 100 if total_bud else 0
    st.markdown("---")
    st.markdown(f"""<div style="background:#F1F5F9;border-radius:12px;padding:16px 20px">
  <div style="font-weight:600;font-size:14px;margin-bottom:8px">全渠道總進度</div>
  <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
    <span>NT${total_act:,}</span>
    <span style="color:#64748B">/ NT${total_bud:,}</span>
  </div>
  <div style="background:#CBD5E1;border-radius:99px;height:12px;overflow:hidden">
    <div style="background:{'#DC2626' if total_pct>100 else '#4F46E5'};width:{min(total_pct,100):.1f}%;height:100%;border-radius:99px"></div>
  </div>
  <div style="font-size:20px;font-weight:700;color:{'#DC2626' if total_pct>100 else '#4F46E5'};margin-top:8px">{total_pct:.1f}%</div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# 轉換分析
# ════════════════════════════════════════════════════
with t_conv:
    st.subheader(f"🔄 轉換分析　{S} – {E}")
    st.markdown('<div class="note-box">⚠️ 轉換指標只在廣告活動層級有效。請在「進件數完開數」分頁填入資料後重新上傳。</div>', unsafe_allow_html=True)

    if not conv_raw.empty and conv_raw['jin'].sum() > 0:
        st.markdown("#### 轉換資料（全量）")
        st.dataframe(conv_raw[['week_str','platform','campaign','jin','wan']].head(30),
                     use_container_width=True, hide_index=True)
    else:
        st.info("「進件數完開數」分頁目前沒有有效資料。填入後重新上傳，系統將自動 join 到各廣告活動。")

    st.markdown("---")
    st.markdown("#### CPL 比較（廣告活動層級，選取期間）")
    cpl_rows = []
    for lbl, camp_df, name_col in [
        ('ASA', asa_c, '廣告活動'),
        ('Google KW', kw_c, '廣告活動'),
        ('PMax', pm_c, '廣告活動'),
    ]:
        if camp_df.empty or 'jin' not in camp_df.columns:
            continue
        for _, row in camp_df.iterrows():
            jin = row.get('jin', 0)
            if jin > 0:
                cpl_rows.append({
                    '平台':   lbl,
                    '廣告活動': row.get(name_col, '–'),
                    '花費':   f"NT${row.get('spend',0):,.0f}",
                    '進件數': int(jin),
                    '完開數': int(row.get('wan', 0)),
                    'CPL':   f"NT${sdiv(row.get('spend',0), jin, 1, 0):,.0f}",
                })
    if cpl_rows:
        st.dataframe(pd.DataFrame(cpl_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("填入轉換資料後，這裡將顯示各平台 CPL 比較。")

    # 漏斗圖
    st.markdown("---")
    st.markdown("#### 轉換漏斗（選取期間，全平台合計）")
    def _safe_funnel_row(df, has_dl=False):
        if df.empty: return pd.DataFrame()
        row = pd.DataFrame({'clk': [sc(df,'clk')], 'mid': [sc(df,'dl') if has_dl else 0],
                            'jin': [sc(df,'jin')], 'wan': [sc(df,'wan')]})
        return row
    all_camp = pd.concat([
        _safe_funnel_row(asa_c, has_dl=True),
        _safe_funnel_row(kw_c,  has_dl=False),
        _safe_funnel_row(pm_c,  has_dl=False),
    ], ignore_index=True)

    if not all_camp.empty:
        total_click_f = sc(all_camp, 'clk')
        total_jin_f   = sc(all_camp, 'jin')
        total_wan_f   = sc(all_camp, 'wan')
        if total_click_f > 0 or total_jin_f > 0:
            fig_f = go.Figure(go.Funnel(
                y=['點擊 / 下載', '進件', '完開'],
                x=[total_click_f, total_jin_f, total_wan_f],
                textinfo='value+percent initial',
                marker_color=[C['asa'], C['kw'], C['pmax']],
            ))
            fig_f.update_layout(height=280, margin=dict(t=10, b=10))
            st.plotly_chart(fig_f, use_container_width=True)
        else:
            st.caption("填入轉換資料後漏斗圖將自動更新")

# ════════════════════════════════════════════════════
# 週報表（進件/開戶 天+週 維度）
# ════════════════════════════════════════════════════
with t_weekly:
    sec("📅 週報表 — 進件數 / 開戶數")

    if conv_week.empty and conv_day.empty:
        st.info("💡 尚無進件資料。請確認 xlsx 包含「工作表1」分頁（含 date, week, 平台, 廣告, 開戶狀態, 人數 欄位）。")
    else:
        view_mode = st.radio("檢視維度", ["週", "天"], horizontal=True)

        if view_mode == "週":
            df_view = conv_week.copy() if not conv_week.empty else pd.DataFrame()
            if not df_view.empty:
                weeks = sorted(df_view['week'].unique())
                sel_week = st.selectbox("選擇週次", ["全部"] + list(weeks), index=0)
                df_w = df_view if sel_week == "全部" else df_view[df_view['week'] == sel_week]

                # KPI 彙總
                total_jin   = df_w['進件數'].sum()
                total_wan   = df_w['開戶數'].sum()
                total_spend = df_w['spend'].sum()
                sec(f"彙總 — {sel_week}")
                kpi_row([
                    ("進件數",   fmt_num(total_jin),        None),
                    ("開戶數",   fmt_num(total_wan),        None),
                    ("開戶率",   f"{sdiv(total_wan, total_jin, 100):.1f}%", None),
                    ("花費",     fmt_money(total_spend),    None, True),
                    ("開戶成本", fmt_money(sdiv(total_spend, total_wan, 1, 0)), None, True),
                ])

                st.markdown("---")
                # 週明細表（PMax 合計行 + 子行）
                rpt = build_conv_report(df_w)
                disp_cols = ['week', '廣告', 'imp', 'clk', 'spend', '進件數', '開戶數', '進件成本', '開戶成本', '開戶率%']
                disp_cols = [c for c in disp_cols if c in rpt.columns]
                disp = rpt[disp_cols].copy()
                disp.rename(columns={'week': '週次', 'imp': '曝光', 'clk': '點擊', 'spend': '花費'}, inplace=True)
                def _fmt_cell(x, is_money=False):
                    if x is None or (isinstance(x, float) and pd.isna(x)): return ''
                    if is_money: return f"NT${x:,.0f}" if x > 0 else '–'
                    return x
                for col in ['曝光', '點擊']:
                    if col in disp.columns:
                        disp[col] = disp[col].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"{int(x):,}")
                if '花費' in disp.columns:
                    disp['花費'] = disp['花費'].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"NT${x:,.0f}")
                for cost_col in ['進件成本', '開戶成本']:
                    if cost_col in disp.columns:
                        disp[cost_col] = disp[cost_col].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else (f"NT${x:,.0f}" if x > 0 else '–'))
                if '開戶率%' in disp.columns:
                    disp['開戶率%'] = disp['開戶率%'].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:.1f}%")
                st.dataframe(disp, use_container_width=True, hide_index=True)

                # 各廣告進件/開戶橫向比較
                st.markdown("---")
                sec("各廣告進件數 vs 開戶數")
                agg = df_w.groupby('廣告').agg(進件數=('進件數','sum'), 開戶數=('開戶數','sum')).reset_index()
                agg = agg.sort_values('進件數', ascending=False)
                fig = go.Figure()
                fig.add_trace(go.Bar(name='進件數', x=agg['廣告'], y=agg['進件數'], marker_color='#2563EB'))
                fig.add_trace(go.Bar(name='開戶數', x=agg['廣告'], y=agg['開戶數'], marker_color='#16A34A'))
                fig.update_layout(barmode='group', height=320, margin=dict(t=10,b=100),
                                   legend=dict(orientation='h',y=1.05),
                                   xaxis_tickangle=-30)
                st.plotly_chart(fig, use_container_width=True)

        else:  # 天維度
            df_view = conv_day.copy() if not conv_day.empty else pd.DataFrame()
            if not df_view.empty:
                # 依選取期間篩選
                df_d = filter_dates(df_view, 'date_str', S, E)
                if df_d.empty:
                    st.info("選取期間內無天維度資料")
                else:
                    total_jin   = df_d['進件數'].sum()
                    total_wan   = df_d['開戶數'].sum()
                    total_spend = df_d['spend'].sum()
                    sec(f"彙總 — {S} ~ {E}")
                    kpi_row([
                        ("進件數",   fmt_num(total_jin),        None),
                        ("開戶數",   fmt_num(total_wan),        None),
                        ("開戶率",   f"{sdiv(total_wan, total_jin, 100):.1f}%", None),
                        ("花費",     fmt_money(total_spend),    None, True),
                        ("開戶成本", fmt_money(sdiv(total_spend, total_wan, 1, 0)), None, True),
                    ])

                    st.markdown("---")
                    # 天明細表（PMax 合計行 + 子行）
                    rpt_d = build_conv_report_day(df_d)
                    disp_cols = ['date_str', '廣告', 'imp', 'clk', 'spend', '進件數', '開戶數', '進件成本', '開戶成本', '開戶率%']
                    disp_cols = [c for c in disp_cols if c in rpt_d.columns]
                    disp = rpt_d[disp_cols].copy()
                    disp.rename(columns={'date_str': '日期', 'imp': '曝光', 'clk': '點擊', 'spend': '花費'}, inplace=True)
                    for col in ['曝光', '點擊']:
                        if col in disp.columns:
                            disp[col] = disp[col].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"{int(x):,}")
                    if '花費' in disp.columns:
                        disp['花費'] = disp['花費'].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"NT${x:,.0f}")
                    for cost_col in ['進件成本', '開戶成本']:
                        if cost_col in disp.columns:
                            disp[cost_col] = disp[cost_col].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else (f"NT${x:,.0f}" if x > 0 else '–'))
                    if '開戶率%' in disp.columns:
                        disp['開戶率%'] = disp['開戶率%'].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:.1f}%")
                    st.dataframe(disp, use_container_width=True, hide_index=True)

                    # 每日進件/開戶趨勢
                    st.markdown("---")
                    sec("每日進件數 / 開戶數趨勢")
                    trend = df_d.groupby('date_str').agg(進件數=('進件數','sum'), 開戶數=('開戶數','sum')).reset_index()
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='進件數', x=trend['date_str'], y=trend['進件數'], marker_color='#2563EB'))
                    fig.add_trace(go.Scatter(name='開戶數', x=trend['date_str'], y=trend['開戶數'],
                                            mode='lines+markers', line=dict(color='#16A34A', width=2)))
                    fig.update_layout(height=280, margin=dict(t=10,b=30),
                                       legend=dict(orientation='h',y=1.08))
                    st.plotly_chart(fig, use_container_width=True)
