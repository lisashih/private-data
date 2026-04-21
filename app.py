"""
口袋證券廣告成效儀表板 v2
Streamlit App — 支援 META / ASA / Google KW / Google PMax 四平台
進件數/完開數 從「進件數完開數」分頁 join，廣告活動層級才有轉換指標
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data_processor import (
    load_data, period_slice, sdiv, fmt_money, fmt_num, wow_pct
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

# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="block-container"] { padding-top: 1.5rem; }
.kpi-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 20px 12px;
    height: 100%;
}
.kpi-label { font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: .05em; font-weight: 500; }
.kpi-value { font-size: 24px; font-weight: 700; color: #0F172A; margin: 4px 0 2px; }
.kpi-wow   { font-size: 12px; font-weight: 500; }
.kpi-wow.up   { color: #16A34A; }
.kpi-wow.dn   { color: #DC2626; }
.kpi-wow.neu  { color: #94A3B8; }
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
}
.pill-asa  { background: #EFF6FF; color: #1D4ED8; }
.pill-meta { background: #F3E8FF; color: #7C3AED; }
.pill-kw   { background: #FFFBEB; color: #B45309; }
.pill-pm   { background: #F0FDF4; color: #15803D; }
</style>
""", unsafe_allow_html=True)

COLORS = {
    'asa':  '#2563EB',
    'meta': '#7C3AED',
    'kw':   '#D97706',
    'pmax': '#16A34A',
    'up':   '#16A34A',
    'dn':   '#DC2626',
}


# ══════════════════════════════════════════════════════
# UI 工具
# ══════════════════════════════════════════════════════
def kpi_card(label: str, value: str, prev_value=None, good_down=False, note: str = ""):
    delta = wow_pct(
        float(str(value).replace('NT$', '').replace('萬', '0000').replace(',', '').replace('–', '0')),
        float(str(prev_value).replace('NT$', '').replace('萬', '0000').replace(',', '').replace('–', '0')) if prev_value else 0
    ) if prev_value is not None else None

    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        wow_html = '<span class="kpi-wow neu">—</span>'
    else:
        arrow = '▲' if delta > 0 else '▼'
        good = delta < 0 if good_down else delta > 0
        cls = 'up' if good else 'dn'
        wow_html = f'<span class="kpi-wow {cls}">{arrow} {abs(delta):.1f}% WoW</span>'

    note_html = f'<br><span style="font-size:10px;color:#94A3B8">{note}</span>' if note else ''
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      {wow_html}{note_html}
    </div>"""


def kpi_row(items: list, show_wow=False):
    """items = [(label, cur_val, prev_val_or_None, good_down, note), ...]"""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label = item[0]
        val   = item[1]
        prev  = item[2] if len(item) > 2 else None
        gd    = item[3] if len(item) > 3 else False
        note  = item[4] if len(item) > 4 else ""
        col.markdown(kpi_card(label, val, prev if show_wow else None, gd, note), unsafe_allow_html=True)


def sum_col(df: pd.DataFrame, col: str, default=0):
    if df.empty or col not in df.columns:
        return default
    return df[col].sum()


def wow_badge(cur, prev, good_down=False):
    d = wow_pct(cur, prev)
    if d is None:
        return ""
    arrow = '▲' if d > 0 else '▼'
    good = d < 0 if good_down else d > 0
    color = COLORS['up'] if good else COLORS['dn']
    return f'<span style="color:{color};font-size:12px;font-weight:600">{arrow} {abs(d):.1f}%</span>'


# ══════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 口袋證券廣告儀表板")
    st.markdown("---")

    uploaded = st.file_uploader(
        "📂 上傳廣告資料 (.xlsx)",
        type=["xlsx"],
        help="上傳包含 META / ASA / Google KW / Google Pmax / 進件數完開數 的 xlsx"
    )

    st.markdown("---")
    period_opt = st.radio(
        "📅 時間維度",
        ["本週 WoW", "月累計"],
        index=0,
        help="本週 = 最新 7 天；月累計 = 資料區間全部"
    )
    period = 'week' if period_opt == "本週 WoW" else 'month'
    show_wow = (period == 'week')

    st.markdown("---")
    st.markdown("**💰 預算進度（本月）**")
    st.caption("填入已花費金額（NT$）：")
    BUDGET = {
        'SEM 品牌字':  350000,
        'SEM 廣字':   235000,
        'SEM 投資入門': 15000,
        'PMAX':       300000,
        'ASA 台股字':  300000,
        'ASA 美股字':   50000,
    }
    budget_actual = {}
    for k, bud in BUDGET.items():
        budget_actual[k] = st.number_input(
            f"{k}（預算 {bud//1000}K）",
            min_value=0, max_value=bud * 2, value=0, step=5000, key=f'b_{k}'
        )

    st.markdown("---")
    st.caption("""
**資料架構說明**
- `進件數`/`完開數` 在「進件數完開數」分頁手動填入
- 廣告活動層級 join 轉換資料後才有 CPL/進件率/完開率
- 關鍵字層級只顯示流量指標
""")


# ══════════════════════════════════════════════════════
# 主畫面
# ══════════════════════════════════════════════════════
st.title("📊 口袋證券廣告成效儀表板")

if uploaded is None:
    st.info("👈 請從左側上傳 `廣告raw.xlsx` 開始分析")
    with st.expander("📋 xlsx 格式說明", expanded=True):
        st.markdown("""
| 分頁名稱 | 必要欄位 | 說明 |
|---------|---------|-----|
| **META** | 天數, 行銷活動名稱, 曝光次數, 連結點擊次數, 花費金額 (TWD) | Facebook/Meta 廣告 |
| **ASA** | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 下載數, 花費（台幣） | Apple Search Ads |
| **Google KW** | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 花費 | Google 關鍵字廣告 |
| **Google Pmax** | Date, 廣告活動, 曝光, 點擊, 花費 | Google PMax |
| **進件數完開數** | Date, 平台, 廣告活動, 進件數, 完開數 | ⭐ 轉換資料（手填）|

> **⚠️ 進件數/完開數** 需在「進件數完開數」分頁填入，系統會自動 join 到對應的廣告活動層級。
""")
    st.stop()


# 載入資料
with st.spinner("讀取資料中..."):
    try:
        data = load_data(uploaded)
    except Exception as e:
        st.error(f"❌ 讀取失敗：{e}")
        st.stop()

meta = data.get('meta', {})
if not meta:
    st.error("❌ 找不到有效的日期資料，請確認 xlsx 格式")
    st.stop()

st.caption(
    f"📅 資料區間：**{meta['min_date']}** – **{meta['max_date']}**　｜　"
    f"本週：{meta['w2_start']} ~ {meta['w2_end']}　上週：{meta['w1_start']} ~ {meta['w1_end']}"
)

# 取出各資料表
asa_daily  = data.get('asa_daily',  pd.DataFrame())
asa_camp   = data.get('asa_camp',   pd.DataFrame())
asa_kw     = data.get('asa_kw',     pd.DataFrame())
kw_daily   = data.get('kw_daily',   pd.DataFrame())
kw_camp    = data.get('kw_camp',    pd.DataFrame())
kw_kw      = data.get('kw_kw',      pd.DataFrame())
pm_daily   = data.get('pm_daily',   pd.DataFrame())
pm_camp    = data.get('pm_camp',    pd.DataFrame())
meta_daily = data.get('meta_daily', pd.DataFrame())
meta_camp  = data.get('meta_camp',  pd.DataFrame())
conv_raw   = data.get('conv_raw',   pd.DataFrame())

# 週期切割
def pw(df, col='date_str'): return period_slice(df, col, meta, 'week')
def pp(df, col='date_str'): return period_slice(df, col, meta, 'prev')
def pm_(df, col='date_str'): return df  # month = all


# ══════════════════════════════════════════════════════
# Tab 架構
# ══════════════════════════════════════════════════════
tabs = st.tabs([
    "🏠 總覽",
    "🍎 ASA",
    "🔍 Google KW",
    "⚡ Google PMax",
    "📘 META",
    "💰 預算進度",
    "🔄 轉換分析",
])
t_ov, t_asa, t_kw, t_pm, t_meta, t_budget, t_conv = tabs


# ════════════════════════════════════════════════════
# 總覽
# ════════════════════════════════════════════════════
with t_ov:
    st.subheader("全平台加總")

    def get_spend(daily, col='spend'):
        if daily.empty: return 0, 0
        cur  = pw(daily)['spend'].sum()  if 'spend' in pw(daily).columns  else 0
        prev = pp(daily)['spend'].sum()  if 'spend' in pp(daily).columns  else 0
        return cur, prev

    asa_sc,  asa_sp  = get_spend(asa_daily)
    kw_sc,   kw_sp   = get_spend(kw_daily)
    pm_sc,   pm_sp   = get_spend(pm_daily)
    meta_sc, meta_sp = get_spend(meta_daily)

    total_sc = asa_sc + kw_sc + pm_sc + meta_sc
    total_sp = asa_sp + kw_sp + pm_sp + meta_sp

    # 點擊
    def get_clk(daily):
        if daily.empty: return 0, 0
        return (pw(daily)['clk'].sum() if 'clk' in pw(daily).columns else 0,
                pp(daily)['clk'].sum() if 'clk' in pp(daily).columns else 0)
    asa_cc, asa_cp = get_clk(asa_daily)
    kw_cc,  kw_cp  = get_clk(kw_daily)
    pm_cc,  pm_cp  = get_clk(pm_daily)
    mt_cc,  mt_cp  = get_clk(meta_daily)
    total_cc = asa_cc + kw_cc + pm_cc + mt_cc
    total_cp = asa_cp + kw_cp + pm_cp + mt_cp

    # ASA 下載數
    asa_dl_c = asa_daily['dl'].sum() if not asa_daily.empty and 'dl' in asa_daily.columns else 0

    # 進件數/完開數（廣告活動層級合計）
    total_jin = (
        sum_col(asa_camp,  'jin') +
        sum_col(kw_camp,   'jin') +
        sum_col(pm_camp,   'jin') +
        sum_col(meta_camp, 'jin')
    )
    total_wan = (
        sum_col(asa_camp,  'wan') +
        sum_col(kw_camp,   'wan') +
        sum_col(pm_camp,   'wan') +
        sum_col(meta_camp, 'wan')
    )

    kpi_row([
        ("總花費",  fmt_money(total_sc), fmt_money(total_sp), True),
        ("總點擊",  fmt_num(total_cc),   fmt_num(total_cp)),
        ("ASA 下載數", fmt_num(asa_dl_c), None),
        ("進件數",  fmt_num(total_jin),  None, False, "廣告活動層級"),
        ("完開數",  fmt_num(total_wan),  None, False, "廣告活動層級"),
    ], show_wow=show_wow)

    st.markdown("---")

    # 每日花費趨勢
    st.subheader("每日花費趨勢")
    all_dates = sorted(set(
        asa_daily['date_str'].tolist() + kw_daily['date_str'].tolist() +
        pm_daily['date_str'].tolist()  + meta_daily['date_str'].tolist()
        if not all(df.empty for df in [asa_daily, kw_daily, pm_daily, meta_daily]) else []
    ))[-30:]

    if all_dates:
        def get_d(df, col='spend'):
            m = dict(zip(df['date_str'], df[col])) if not df.empty and col in df.columns else {}
            return [m.get(d, 0) for d in all_dates]

        fig = go.Figure()
        fig.add_trace(go.Bar(name='ASA',       x=all_dates, y=get_d(asa_daily),  marker_color=COLORS['asa']))
        fig.add_trace(go.Bar(name='Google KW', x=all_dates, y=get_d(kw_daily),   marker_color=COLORS['kw']))
        fig.add_trace(go.Bar(name='PMax',      x=all_dates, y=get_d(pm_daily),   marker_color=COLORS['pmax']))
        fig.add_trace(go.Bar(name='META',      x=all_dates, y=get_d(meta_daily), marker_color=COLORS['meta']))
        fig.update_layout(barmode='stack', height=320, margin=dict(t=20, b=30),
                          legend=dict(orientation='h', y=1.08),
                          yaxis=dict(title='NT$'))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("花費佔比（月累計）")
        pie_df = pd.DataFrame({
            '平台':   ['ASA', 'Google KW', 'PMax', 'META'],
            '花費':   [asa_daily['spend'].sum() if not asa_daily.empty else 0,
                       kw_daily['spend'].sum()  if not kw_daily.empty  else 0,
                       pm_daily['spend'].sum()  if not pm_daily.empty  else 0,
                       meta_daily['spend'].sum() if not meta_daily.empty else 0],
        })
        fig_p = px.pie(pie_df, values='花費', names='平台',
                       color='平台',
                       color_discrete_map={'ASA': COLORS['asa'], 'Google KW': COLORS['kw'],
                                           'PMax': COLORS['pmax'], 'META': COLORS['meta']},
                       hole=0.42)
        fig_p.update_layout(height=280, margin=dict(t=10, b=10),
                             legend=dict(orientation='h'))
        st.plotly_chart(fig_p, use_container_width=True)

    with col2:
        if show_wow:
            st.subheader("WoW 花費變化 %")
            wow_rows = []
            for lbl, sc, sp in [
                ('ASA',   asa_sc,  asa_sp),
                ('KW',    kw_sc,   kw_sp),
                ('PMax',  pm_sc,   pm_sp),
                ('META',  meta_sc, meta_sp),
            ]:
                d = wow_pct(sc, sp)
                if d is not None:
                    wow_rows.append({'平台': lbl, 'WoW%': round(d, 1)})
            if wow_rows:
                wdf = pd.DataFrame(wow_rows)
                clr = [COLORS['up'] if v >= 0 else COLORS['dn'] for v in wdf['WoW%']]
                fig_w = go.Figure(go.Bar(x=wdf['WoW%'], y=wdf['平台'], orientation='h', marker_color=clr))
                fig_w.update_layout(height=260, margin=dict(t=10, b=10), xaxis_title='WoW %')
                st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.subheader("各平台點擊比較")
            bar_df = pd.DataFrame({
                '平台':  ['ASA', 'Google KW', 'PMax', 'META'],
                '點擊':  [asa_daily['clk'].sum() if not asa_daily.empty else 0,
                           kw_daily['clk'].sum()  if not kw_daily.empty  else 0,
                           pm_daily['clk'].sum()  if not pm_daily.empty  else 0,
                           meta_daily['clk'].sum() if not meta_daily.empty else 0],
            })
            fig_b = px.bar(bar_df, x='平台', y='點擊',
                           color='平台',
                           color_discrete_map={'ASA': COLORS['asa'], 'Google KW': COLORS['kw'],
                                               'PMax': COLORS['pmax'], 'META': COLORS['meta']})
            fig_b.update_layout(height=260, margin=dict(t=10, b=10), showlegend=False)
            st.plotly_chart(fig_b, use_container_width=True)


# ════════════════════════════════════════════════════
# ASA Tab
# ════════════════════════════════════════════════════
with t_asa:
    st.subheader("🍎 Apple Search Ads")
    if asa_camp.empty:
        st.warning("尚無 ASA 資料"); st.stop()

    tot = asa_camp[['spend','imp','clk','dl','jin','wan']].sum()
    kpi_row([
        ("花費台幣",   fmt_money(tot['spend']), None),
        ("曝光",      fmt_num(tot['imp']),     None),
        ("點擊",      fmt_num(tot['clk']),     None),
        ("下載數",    fmt_num(tot['dl']),      None),
        ("CTR%",     f"{sdiv(tot['clk'], tot['imp'], 100):.2f}%", None),
        ("CPI",      fmt_money(sdiv(tot['spend'], tot['dl'], 1, 0)), None, True),
    ])

    has_conv = tot['jin'] > 0
    if has_conv:
        st.markdown("**轉換指標（廣告活動層級）**")
        kpi_row([
            ("進件數",  fmt_num(tot['jin']), None),
            ("完開數",  fmt_num(tot['wan']), None),
            ("CPL",   fmt_money(sdiv(tot['spend'], tot['jin'], 1, 0)), None, True),
            ("進件率%", f"{sdiv(tot['jin'], tot['dl'], 100):.1f}%", None),
            ("完開率%", f"{sdiv(tot['wan'], tot['jin'], 100):.1f}%", None),
        ])
    else:
        st.info("💡 尚未填入進件數/完開數（請在「進件數完開數」分頁填入後重新上傳）")

    st.markdown("---")
    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("#### 廣告活動明細")
        disp = asa_camp[['廣告活動','spend','dl','CTR%','CPI','jin','wan','進件率%','完開率%']].copy()
        disp.columns = ['廣告活動','花費台幣','下載數','CTR%','CPI','進件數','完開數','進件率%','完開率%']
        disp['花費台幣'] = disp['花費台幣'].apply(lambda x: f"NT${x:,.0f}")
        disp['CPI']     = disp['CPI'].apply(lambda x: f"NT${x:,.0f}")
        st.dataframe(disp, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### CPI 比較（NT$/下載）")
        cc = asa_camp[asa_camp['CPI'] > 0].sort_values('CPI', ascending=True)
        if not cc.empty:
            clrs = ['#DC2626' if v > 1000 else '#F59E0B' if v > 500 else '#16A34A' for v in cc['CPI']]
            fig = go.Figure(go.Bar(
                x=cc['CPI'], y=cc['廣告活動'], orientation='h',
                marker_color=clrs,
                text=[f"NT${v:,.0f}" for v in cc['CPI']], textposition='outside'
            ))
            fig.add_vline(x=500, line_dash='dash', line_color='#F59E0B', annotation_text='500')
            fig.add_vline(x=1000, line_dash='dash', line_color='#DC2626', annotation_text='1000')
            fig.update_layout(height=max(250, len(cc)*45+60), margin=dict(t=10, b=10, r=80),
                              showlegend=False, xaxis_title='CPI (NT$)')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 關鍵字效益（流量指標，不含轉換）")
    st.caption("⚠️ 關鍵字層級無法匹配進件數/完開數，請以廣告活動層級查看轉換指標")
    if not asa_kw.empty:
        kw_disp = asa_kw[['廣告活動','廣告關鍵字','spend','imp','clk','dl','CTR%','CPI']].head(50).copy()
        kw_disp.columns = ['廣告活動','關鍵字','花費台幣','曝光','點擊','下載數','CTR%','CPI']
        kw_disp['花費台幣'] = kw_disp['花費台幣'].apply(lambda x: f"NT${x:,.0f}")
        kw_disp['CPI']     = kw_disp['CPI'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
        st.dataframe(kw_disp, use_container_width=True, hide_index=True)

    # 每日下載趨勢
    if not asa_daily.empty:
        st.markdown("---")
        st.markdown("#### 每日下載數趨勢")
        fig_dl = px.bar(asa_daily, x='date_str', y='dl',
                        color_discrete_sequence=[COLORS['asa']])
        fig_dl.update_layout(height=240, margin=dict(t=10, b=30),
                              xaxis_title='', yaxis_title='下載數')
        st.plotly_chart(fig_dl, use_container_width=True)


# ════════════════════════════════════════════════════
# Google KW Tab
# ════════════════════════════════════════════════════
with t_kw:
    st.subheader("🔍 Google Keyword")
    if kw_camp.empty:
        st.warning("尚無 Google KW 資料")
    else:
        tot = kw_camp[['spend','imp','clk','jin','wan']].sum()
        kpi_row([
            ("花費",   fmt_money(tot['spend']), None),
            ("曝光",   fmt_num(tot['imp']),    None),
            ("點擊",   fmt_num(tot['clk']),    None),
            ("CTR%",  f"{sdiv(tot['clk'], tot['imp'], 100):.2f}%", None),
            ("CPC",   fmt_money(sdiv(tot['spend'], tot['clk'], 1, 1)), None, True),
        ])

        has_conv = tot['jin'] > 0
        if has_conv:
            kpi_row([
                ("進件數", fmt_num(tot['jin']), None),
                ("完開數", fmt_num(tot['wan']), None),
                ("CPL",  fmt_money(sdiv(tot['spend'], tot['jin'], 1, 0)), None, True),
                ("進件率%", f"{sdiv(tot['jin'], tot['clk'], 100):.2f}%", None),
                ("完開率%", f"{sdiv(tot['wan'], tot['jin'], 100):.1f}%", None),
            ])
        else:
            st.info("💡 尚未填入進件數/完開數")

        st.markdown("---")
        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.markdown("#### 廣告活動明細（含轉換指標）")
            cols_show = ['camp_short','spend','imp','clk','CTR%','CPC','jin','wan','CPL','進件率%','完開率%']
            cols_show = [c for c in cols_show if c in kw_camp.columns]
            disp = kw_camp[cols_show].copy()
            col_map = {'camp_short':'活動','spend':'花費','imp':'曝光','clk':'點擊',
                       'jin':'進件數','wan':'完開數','CPL':'CPL'}
            disp.rename(columns=col_map, inplace=True)
            if '花費' in disp.columns: disp['花費'] = disp['花費'].apply(lambda x: f"NT${x:,.0f}")
            if 'CPL'  in disp.columns: disp['CPL']  = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
            st.dataframe(disp, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("#### 廣告活動花費比較")
            if not kw_camp.empty:
                fc = kw_camp.sort_values('spend', ascending=True).tail(10)
                fig = go.Figure(go.Bar(
                    x=fc['spend'], y=fc['camp_short'], orientation='h',
                    marker_color=COLORS['kw'],
                    text=[f"NT${v:,.0f}" for v in fc['spend']], textposition='outside'
                ))
                fig.update_layout(height=max(240, len(fc)*42+60), margin=dict(t=10, b=10, r=80),
                                  showlegend=False, xaxis_title='花費 (NT$)')
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 關鍵字明細（純流量指標）")
        st.caption("⚠️ 關鍵字層級無法匹配進件數/完開數，轉換指標請看上方廣告活動層級")
        if not kw_kw.empty:
            kw_disp = kw_kw[['camp_short','廣告關鍵字','spend','imp','clk','CTR%','CPC']].head(60).copy()
            kw_disp.columns = ['活動','關鍵字','花費','曝光','點擊','CTR%','CPC']
            kw_disp['花費'] = kw_disp['花費'].apply(lambda x: f"NT${x:,.0f}")
            kw_disp['CPC']  = kw_disp['CPC'].apply(lambda x: f"NT${x:,.1f}" if x > 0 else '–')
            st.dataframe(kw_disp, use_container_width=True, hide_index=True)

        if not kw_daily.empty:
            st.markdown("---")
            st.markdown("#### 每日點擊趨勢")
            fig_kd = px.line(kw_daily, x='date_str', y='clk',
                             color_discrete_sequence=[COLORS['kw']], markers=True)
            fig_kd.update_layout(height=240, margin=dict(t=10, b=30),
                                  xaxis_title='', yaxis_title='點擊數')
            st.plotly_chart(fig_kd, use_container_width=True)


# ════════════════════════════════════════════════════
# Google PMax Tab
# ════════════════════════════════════════════════════
with t_pm:
    st.subheader("⚡ Google PMax")
    if pm_camp.empty:
        st.warning("尚無 PMax 資料")
    else:
        tot = pm_camp[['spend','imp','clk','jin','wan']].sum()
        kpi_row([
            ("花費",   fmt_money(tot['spend']), None),
            ("曝光",   fmt_num(tot['imp']),    None),
            ("點擊",   fmt_num(tot['clk']),    None),
            ("CTR%",  f"{sdiv(tot['clk'], tot['imp'], 100):.2f}%", None),
            ("CPC",   fmt_money(sdiv(tot['spend'], tot['clk'], 1, 1)), None, True),
        ])

        has_conv = tot['jin'] > 0
        if has_conv:
            kpi_row([
                ("進件數",  fmt_num(tot['jin']), None),
                ("完開數",  fmt_num(tot['wan']), None),
                ("CPL",   fmt_money(sdiv(tot['spend'], tot['jin'], 1, 0)), None, True),
                ("完開率%", f"{sdiv(tot['wan'], tot['jin'], 100):.1f}%", None),
            ])
        else:
            st.info("💡 尚未填入進件數/完開數")

        # 每日趨勢
        if not pm_daily.empty:
            st.markdown("---")
            st.markdown("#### 每日點擊 & 花費趨勢")
            fig = go.Figure()
            fig.add_trace(go.Bar(name='點擊', x=pm_daily['date_str'], y=pm_daily['clk'],
                                 marker_color='#86EFAC', yaxis='y'))
            fig.add_trace(go.Scatter(name='花費', x=pm_daily['date_str'], y=pm_daily['spend'],
                                     mode='lines+markers', line=dict(color=COLORS['pmax'], width=2),
                                     yaxis='y2'))
            fig.update_layout(
                height=300, margin=dict(t=10, b=30),
                yaxis=dict(title='點擊'),
                yaxis2=dict(title='花費 (NT$)', overlaying='y', side='right',
                            showgrid=False),
                legend=dict(orientation='h', y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

        # 明細表
        st.markdown("---")
        st.markdown("#### 廣告活動明細")
        disp = pm_camp[['廣告活動','spend','imp','clk','CTR%','CPC','jin','wan','CPL','完開率%']].copy()
        disp.columns = ['廣告活動','花費','曝光','點擊','CTR%','CPC','進件數','完開數','CPL','完開率%']
        disp['花費'] = disp['花費'].apply(lambda x: f"NT${x:,.0f}")
        disp['CPC']  = disp['CPC'].apply(lambda x: f"NT${x:,.1f}")
        disp['CPL']  = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
        st.dataframe(disp, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════
# META Tab
# ════════════════════════════════════════════════════
with t_meta:
    st.subheader("📘 Facebook / Meta")
    if meta_camp.empty:
        st.warning("尚無 META 資料")
    else:
        tot = meta_camp[['spend','imp','clk','jin','wan']].sum()
        kpi_row([
            ("花費",   fmt_money(tot['spend']), None),
            ("曝光",   fmt_num(tot['imp']),    None),
            ("點擊",   fmt_num(tot['clk']),    None),
            ("CTR%",  f"{sdiv(tot['clk'], tot['imp'], 100):.2f}%", None),
            ("CPC",   fmt_money(sdiv(tot['spend'], tot['clk'], 1, 1)), None, True),
        ])

        has_conv = tot['jin'] > 0
        if has_conv:
            kpi_row([
                ("進件數",  fmt_num(tot['jin']), None),
                ("完開數",  fmt_num(tot['wan']), None),
                ("CPL",   fmt_money(sdiv(tot['spend'], tot['jin'], 1, 0)), None, True),
                ("進件率%", f"{sdiv(tot['jin'], tot['clk'], 100):.2f}%", None),
                ("完開率%", f"{sdiv(tot['wan'], tot['jin'], 100):.1f}%", None),
            ])
        else:
            st.info("💡 尚未填入進件數/完開數")

        st.markdown("---")
        st.markdown("#### 廣告活動明細（Top 20）")
        disp = meta_camp[['camp','spend','imp','clk','CTR%','CPC','jin','wan','CPL','進件率%']].head(20).copy()
        disp.columns = ['廣告活動','花費','曝光','點擊','CTR%','CPC','進件數','完開數','CPL','進件率%']
        disp['花費'] = disp['花費'].apply(lambda x: f"NT${x:,.0f}")
        disp['CPC']  = disp['CPC'].apply(lambda x: f"NT${x:,.1f}")
        disp['CPL']  = disp['CPL'].apply(lambda x: f"NT${x:,.0f}" if x > 0 else '–')
        st.dataframe(disp, use_container_width=True, hide_index=True)

        if not meta_daily.empty:
            st.markdown("---")
            st.markdown("#### 每日花費趨勢")
            fig = px.bar(meta_daily, x='date_str', y='spend',
                         color_discrete_sequence=[COLORS['meta']])
            fig.update_layout(height=240, margin=dict(t=10, b=30),
                              xaxis_title='', yaxis_title='花費 (NT$)')
            st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════
# 預算進度
# ════════════════════════════════════════════════════
with t_budget:
    st.subheader("💰 預算進度追蹤")

    google_actual = sum(budget_actual.get(k, 0) for k in ['SEM 品牌字','SEM 廣字','SEM 投資入門','PMAX'])
    asa_actual    = sum(budget_actual.get(k, 0) for k in ['ASA 台股字','ASA 美股字'])
    total_actual  = google_actual + asa_actual
    total_budget  = sum(BUDGET.values())

    # 總覽卡
    col1, col2, col3 = st.columns(3)
    for col, (lbl, act, bud) in zip([col1, col2, col3], [
        ('Google 合計', google_actual, 900000),
        ('ASA 合計',    asa_actual,    350000),
        ('全渠道合計',  total_actual,  total_budget),
    ]):
        pct = act / bud * 100 if bud else 0
        color = '#DC2626' if pct > 100 else '#D97706' if pct > 85 else '#16A34A'
        col.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-label">{lbl}</div>
          <div class="kpi-value">NT${act:,}</div>
          <div style="font-size:12px;color:#64748B">預算 NT${bud:,}</div>
          <div style="font-size:18px;font-weight:700;color:{color}">{pct:.1f}%{'  ⚠️' if pct>100 else ''}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 各項目進度條")

    for k, bud in BUDGET.items():
        act = budget_actual.get(k, 0)
        pct = min(act / bud * 100, 100) if bud else 0
        over = act > bud
        bar_color = '#DC2626' if over else '#2563EB'
        warn = ' ⚠️ 超預算' if over else ''
        st.markdown(f"""
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
            <span style="font-weight:500">{k}</span>
            <span style="color:#64748B">NT${act:,} / NT${bud:,} &nbsp;
              <span style="color:{'#DC2626' if over else '#0F172A'};font-weight:600">{pct:.1f}%{warn}</span>
            </span>
          </div>
          <div style="background:#E2E8F0;border-radius:99px;height:8px;overflow:hidden">
            <div style="background:{bar_color};width:{pct:.1f}%;height:100%;border-radius:99px;transition:width .3s"></div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    # 總進度
    total_pct = total_actual / total_budget * 100 if total_budget else 0
    st.markdown(f"""
    <div style="background:#F1F5F9;border-radius:12px;padding:16px 20px">
      <div style="font-weight:600;font-size:14px;margin-bottom:8px">全渠道總進度</div>
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
        <span>NT${total_actual:,}</span>
        <span style="color:#64748B">/ NT${total_budget:,}</span>
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
    st.subheader("🔄 跨平台轉換分析")
    st.caption("⚠️ 轉換指標僅在「進件數完開數」分頁有資料時才有效，廣告活動層級才可 join")

    # 轉換資料預覽
    if not conv_raw.empty and conv_raw['jin'].sum() > 0:
        st.markdown("#### 轉換資料預覽")
        st.dataframe(conv_raw[['date_str','platform','campaign','jin','wan']].head(20),
                     use_container_width=True, hide_index=True)
    else:
        st.info("💡 「進件數完開數」分頁目前尚無有效資料。請填入後重新上傳，系統將自動 join 至對應廣告活動。")

    st.markdown("---")
    st.markdown("#### 各平台 CPL 比較（廣告活動層級）")

    cpl_rows = []
    for lbl, camp_df in [('ASA', asa_camp), ('Google KW', kw_camp),
                          ('PMax', pm_camp), ('META', meta_camp)]:
        if camp_df.empty or 'jin' not in camp_df.columns:
            continue
        for _, row in camp_df.iterrows():
            jin = row.get('jin', 0)
            wan = row.get('wan', 0)
            spend = row.get('spend', 0)
            if jin > 0:
                cpl = sdiv(spend, jin, 1, 0)
                cpl_rows.append({
                    '平台': lbl,
                    '廣告活動': row.get('廣告活動', row.get('camp', row.get('camp_short', '–'))),
                    '花費': f"NT${spend:,.0f}",
                    '進件數': int(jin),
                    '完開數': int(wan),
                    'CPL': f"NT${cpl:,.0f}",
                    '進件率%': f"{sdiv(jin, row.get('clk', row.get('dl', 1)), 100):.2f}%",
                    '完開率%': f"{sdiv(wan, jin, 100):.1f}%",
                })

    if cpl_rows:
        cpl_df = pd.DataFrame(cpl_rows)
        st.dataframe(cpl_df, use_container_width=True, hide_index=True)
    else:
        st.info("填入轉換資料後，這裡將顯示各平台 CPL 比較。")

    # 漏斗圖
    st.markdown("---")
    st.markdown("#### 轉換漏斗（全平台合計）")
    all_camp = pd.concat([
        asa_camp[['spend','clk','dl','jin','wan']].rename(columns={'dl':'mid'}) if not asa_camp.empty else pd.DataFrame(),
        kw_camp[['spend','clk','jin','wan']].assign(mid=0) if not kw_camp.empty else pd.DataFrame(),
        pm_camp[['spend','clk','jin','wan']].assign(mid=0) if not pm_camp.empty else pd.DataFrame(),
        meta_camp[['spend','clk','jin','wan']].assign(mid=0) if not meta_camp.empty else pd.DataFrame(),
    ], ignore_index=True)

    if not all_camp.empty:
        funnel_data = {
            '點擊': all_camp['clk'].sum() if 'clk' in all_camp.columns else 0,
            '進件': all_camp['jin'].sum() if 'jin' in all_camp.columns else 0,
            '完開': all_camp['wan'].sum() if 'wan' in all_camp.columns else 0,
        }
        funnel_df = pd.DataFrame({'階段': list(funnel_data.keys()), '人數': list(funnel_data.values())})
        if funnel_df['人數'].sum() > 0:
            fig_f = go.Figure(go.Funnel(
                y=funnel_df['階段'],
                x=funnel_df['人數'],
                textinfo='value+percent initial',
                marker_color=[COLORS['asa'], COLORS['kw'], COLORS['pmax']],
            ))
            fig_f.update_layout(height=280, margin=dict(t=10, b=10))
            st.plotly_chart(fig_f, use_container_width=True)
        else:
            st.caption("填入轉換資料後漏斗圖將自動更新")
