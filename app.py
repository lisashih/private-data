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
    load_data, filter_by_dates, reagg_camp_from_raw,
    sdiv, fmt_money, fmt_num, wow_pct, shorten_camp
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
        col_s, col_e = st.columns(2)
        with col_s:
            sel_start = st.date_input("開始", value=min_d, min_value=min_d, max_value=max_d, key='sel_s')
        with col_e:
            sel_end = st.date_input("結束", value=max_d, min_value=min_d, max_value=max_d, key='sel_e')

        if sel_start > sel_end:
            st.error("開始日期不能晚於結束日期")
            st.stop()

        # 快速選擇按鈕
        st.caption("快速選取：")
        qcols = st.columns(3)
        if qcols[0].button("本月", use_container_width=True):
            st.session_state['sel_s'] = max_d.replace(day=1)
            st.session_state['sel_e'] = max_d
            st.rerun()
        if qcols[1].button("近7天", use_container_width=True):
            st.session_state['sel_s'] = max(min_d, max_d - timedelta(days=6))
            st.session_state['sel_e'] = max_d
            st.rerun()
        if qcols[2].button("近14天", use_container_width=True):
            st.session_state['sel_s'] = max(min_d, max_d - timedelta(days=13))
            st.session_state['sel_e'] = max_d
            st.rerun()

        st.markdown("---")
        st.markdown("**📊 對比期間**")
        use_cmp = st.checkbox("啟用對比", value=False)
        cmp_start = cmp_end = None
        if use_cmp:
            cmp_col1, cmp_col2 = st.columns(2)
            with cmp_col1:
                cmp_start = st.date_input("對比開始", value=min_d, min_value=min_d, max_value=max_d, key='cmp_s')
            with cmp_col2:
                cmp_end = st.date_input("對比結束", value=min_d + timedelta(days=(sel_end - sel_start).days), min_value=min_d, max_value=max_d, key='cmp_e')

        st.markdown("---")
        st.markdown("**💰 預算進度（本月，NT$）**")
        BUDGET = {'品牌字': 350000, '廣字': 235000, '投資入門': 15000,
                  'PMAX': 300000, 'ASA 台股字': 300000, 'ASA 美股字': 50000}
        budget_actual = {}
        for k, bud in BUDGET.items():
            budget_actual[k] = st.number_input(
                f"{k}（{bud//1000}K）", min_value=0, max_value=bud*2, value=0, step=5000, key=f'b_{k}'
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

# ── 篩選選取期 ────────────────────────────────────────
asa_d  = filter_by_dates(asa_daily_all, 'date_str', S, E)
kw_d   = filter_by_dates(kw_daily_all,  'date_str', S, E)
pm_d   = filter_by_dates(pm_daily_all,  'date_str', S, E)

# 廣告活動層級從 raw 重新彙總（確保日期篩選準確）
asa_raw_f = filter_by_dates(asa_raw_all, 'date_str', S, E)
kw_raw_f  = filter_by_dates(kw_raw_all,  'date_str', S, E)
pm_raw_f  = filter_by_dates(pm_raw_all,  'date_str', S, E)

def reagg_asa(raw_f):
    if raw_f.empty: return pd.DataFrame()
    c = raw_f.groupby('廣告活動').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()
    c['CTR%'] = c.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    c['CPI']  = c.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    return c

def reagg_kw_camp(raw_f):
    if raw_f.empty: return pd.DataFrame()
    c = raw_f.groupby(['廣告活動','camp_short']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    c['CTR%'] = c.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    c['CPC']  = c.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    return c

def reagg_pm_camp(raw_f):
    if raw_f.empty: return pd.DataFrame()
    c = raw_f.groupby('廣告活動').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    c['CTR%'] = c.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    c['CPC']  = c.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    return c

asa_c = reagg_asa(asa_raw_f)
kw_c  = reagg_kw_camp(kw_raw_f)
pm_c  = reagg_pm_camp(pm_raw_f)

# 關鍵字層級
def reagg_asa_kw(raw_f):
    if raw_f.empty: return pd.DataFrame()
    k = raw_f.groupby(['廣告活動','廣告群組','廣告關鍵字']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()
    k['CTR%'] = k.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    k['CPI']  = k.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    return k.sort_values('spend', ascending=False)

def reagg_kw_kw(raw_f):
    if raw_f.empty: return pd.DataFrame()
    k = raw_f.groupby(['camp_short','廣告關鍵字']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    k['CTR%'] = k.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    k['CPC']  = k.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    return k.sort_values('spend', ascending=False)

asa_kw_f = reagg_asa_kw(asa_raw_f)
kw_kw_f  = reagg_kw_kw(kw_raw_f)

# ── 篩選對比期 ────────────────────────────────────────
asa_d_c = filter_by_dates(asa_daily_all, 'date_str', CS, CE) if use_cmp and CS else None
kw_d_c  = filter_by_dates(kw_daily_all,  'date_str', CS, CE) if use_cmp and CS else None
pm_d_c  = filter_by_dates(pm_daily_all,  'date_str', CS, CE) if use_cmp and CS else None

def cmp_spend(daily_c):
    if daily_c is None or daily_c.empty: return 0
    return float(daily_c['spend'].sum()) if 'spend' in daily_c.columns else 0
def cmp_clk(daily_c):
    if daily_c is None or daily_c.empty: return 0
    return float(daily_c['clk'].sum()) if 'clk' in daily_c.columns else 0

# ── 轉換 join（用原始全量，因為轉換是廣告活動層級、不分日）─────────────
def join_conv(camp_df, camp_key, platform):
    if camp_df.empty: return camp_df
    from data_processor import _get_conv
    conv = _get_conv(conv_raw, platform)
    camp_df = camp_df.copy()
    if not conv.empty:
        cg = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp_df = camp_df.merge(cg, left_on=camp_key, right_on='campaign', how='left')
    else:
        camp_df['jin'] = 0; camp_df['wan'] = 0
    camp_df = camp_df.fillna(0)
    return camp_df

asa_c = join_conv(asa_c, '廣告活動', 'ASA')
if not asa_c.empty:
    asa_c['CPL']    = asa_c.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    asa_c['進件率%'] = asa_c.apply(lambda r: sdiv(r['jin'], r['dl'], 100), axis=1)
    asa_c['完開率%'] = asa_c.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

kw_c = join_conv(kw_c, '廣告活動', 'Google')
if not kw_c.empty:
    kw_c['CPL']    = kw_c.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    kw_c['進件率%'] = kw_c.apply(lambda r: sdiv(r['jin'], r['clk'], 100), axis=1)
    kw_c['完開率%'] = kw_c.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

pm_c = join_conv(pm_c, '廣告活動', 'Google')
if not pm_c.empty:
    pm_c['CPL']   = pm_c.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    pm_c['完開率%'] = pm_c.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)


# ══════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════
t_ov, t_asa, t_kw, t_pm, t_budget, t_conv, t_weekly = st.tabs([
    "🏠 總覽", "🍎 ASA", "🔍 Google KW", "⚡ Google PMax", "💰 預算進度", "🔄 轉換分析", "📅 週報表"
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
                cols_show = ['廣告活動','spend','dl','CTR%','CPI']
                if 'jin' in asa_c.columns: cols_show += ['jin','wan','CPL','進件率%','完開率%']
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
        st.dataframe(conv_raw[['date_str','platform','campaign','jin','wan']].head(30),
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
    all_camp = pd.concat([
        asa_c[['clk','dl','jin','wan']].rename(columns={'dl':'mid'}) if not asa_c.empty else pd.DataFrame(),
        kw_c[['clk','jin','wan']].assign(mid=0) if not kw_c.empty else pd.DataFrame(),
        pm_c[['clk','jin','wan']].assign(mid=0) if not pm_c.empty else pd.DataFrame(),
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
# 週報表（進件數完開數週資料）
# ════════════════════════════════════════════════════
with t_weekly:
    sec("📅 週報表 — 進件數 / 完開數 / 實動數")
    conv = data.get('conv_raw', pd.DataFrame())

    if conv.empty:
        st.info("💡 尚無週轉換資料。請在「進件數完開數」分頁填入後重新上傳。\n\n格式：Week, 平台, 廣告活動, 花費, 進件數, 進件成本, 完開數, 完開成本, 完開率, 實動, 實動率")
    else:
        # 週次選擇
        weeks = sorted(conv['week_str'].unique())
        sel_week = st.selectbox("選擇週次", options=["全部"] + list(weeks), index=0)
        df_w = conv if sel_week == "全部" else conv[conv['week_str'] == sel_week]

        # 彙總 KPI
        total_jin = df_w['jin'].sum()
        total_wan = df_w['wan'].sum()
        total_sd  = df_w['shidong'].sum()
        total_spend = df_w['spend'].sum()

        sec(f"彙總 — {sel_week}")
        kpi_row([
            ("進件數",  fmt_num(total_jin), None),
            ("完開數",  fmt_num(total_wan), None),
            ("實動數",  fmt_num(total_sd),  None),
            ("整體完開率", f"{sdiv(total_wan, total_jin, 100):.1f}%", None),
            ("整體實動率", f"{sdiv(total_sd,  total_wan, 100):.1f}%", None),
        ])

        st.markdown("---")
        sec("各平台明細")
        disp = df_w[['week_str','platform','campaign','jin','wan','shidong',
                     'jin_cost','wan_cost','wan_rate']].copy()
        disp.columns = ['週次','平台','廣告活動','進件數','完開數','實動數',
                        '進件成本','完開成本','完開率']
        disp['進件成本'] = disp['進件成本'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else "–")
        disp['完開成本'] = disp['完開成本'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else "–")
        disp['完開率']   = disp['完開率'].apply(lambda x: f"{x*100:.1f}%" if x > 0 else "–")
        st.dataframe(disp, use_container_width=True, hide_index=True)

        st.markdown("---")
        # 各平台進件/完開橫向比較
        if not df_w.empty:
            sec("各平台進件數 vs 完開數")
            agg = df_w.groupby('platform').agg(jin=('jin','sum'), wan=('wan','sum'), sd=('shidong','sum')).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(name='進件數', x=agg['platform'], y=agg['jin'], marker_color='#2563EB'))
            fig.add_trace(go.Bar(name='完開數', x=agg['platform'], y=agg['wan'], marker_color='#16A34A'))
            fig.add_trace(go.Bar(name='實動數', x=agg['platform'], y=agg['sd'],  marker_color='#D97706'))
            fig.update_layout(barmode='group', height=280, margin=dict(t=10,b=20),
                               legend=dict(orientation='h',y=1.1))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.caption("""
**「進件數完開數」分頁填寫格式：**
| 欄位 | 說明 |
|------|------|
| Week | 週次，格式 Week15_0406~0412 |
| 平台 | Google廣告 / ASA廣告 / Pmax廣告 |
| 廣告活動 | 品牌字 / ASA廣告 / Pmax廣告 等 |
| 進件數 / 完開數 / 實動 | 填入數字即可 |
| 進件成本 / 完開成本 | 選填 |
""")
