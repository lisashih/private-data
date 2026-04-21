"""
口袋證券廣告成效儀表板 - 修復版
修正內容：動態基準日期、Session State 連動、空值防護
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

# 自定義 CSS
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
.kpi-value { font-size: 22px; font-weight: 700; color: #0F172A; margin: 4px 0; }
.kpi-delta { font-size: 12px; font-weight: 600; }
.delta-up { color: #059669; }
.delta-down { color: #DC2626; }
</style>
""", unsafe_allow_html=True)

# 快捷求和函數
def sc(df, col):
    return df[col].sum() if not df.empty and col in df.columns else 0

# ══════════════════════════════════════════════════════
# 資料載入與側邊欄控制
# ══════════════════════════════════════════════════════
st.sidebar.title("📊 數據篩選")
uploaded_file = st.sidebar.file_uploader("上傳廣告數據 (xlsx)", type="xlsx")

if uploaded_file:
    with st.spinner("資料處理中..."):
        all_data = load_data(uploaded_file)
        st.session_state.all_data = all_data

    # --- 重要：取得資料中的最新日期作為計算基準 ---
    max_dt_str = all_data.get('meta', {}).get('max_date')
    if max_dt_str:
        # 假設格式為 YYYY-MM-DD
        base_date = pd.to_datetime(max_dt_str).date()
    else:
        base_date = date.today()

    # 初始化 Session State 日期
    if "start_date" not in st.session_state:
        st.session_state.start_date = base_date - timedelta(days=7)
    if "end_date" not in st.session_state:
        st.session_state.end_date = base_date

    # 快捷選擇按鈕
    st.sidebar.write("快速區間選擇：")
    c1, c2, c3 = st.sidebar.columns(3)
    if c1.button("最近 7 天"):
        st.session_state.start_date = base_date - timedelta(days=7)
        st.session_state.end_date = base_date
    if c2.button("最近 14 天"):
        st.session_state.start_date = base_date - timedelta(days=14)
        st.session_state.end_date = base_date
    if c3.button("全量數據"):
        st.session_state.start_date = pd.to_datetime(all_data['meta']['min_date']).date()
        st.session_state.end_date = base_date

    # 手動日期輸入 (連動 session_state)
    sd = st.sidebar.date_input("開始日期", value=st.session_state.start_date, key="sd_input")
    ed = st.sidebar.date_input("結束日期", value=st.session_state.end_date, key="ed_input")
    
    # 同步回 session_state
    st.session_state.start_date = sd
    st.session_state.end_date = ed

    # ══════════════════════════════════════════════════════
    # 核心邏輯：資料篩選
    # ══════════════════════════════════════════════════════
    # 1. 基礎篩選 (Daily)
    asa_d = filter_by_dates(all_data['asa_daily'], 'date', sd, ed)
    kw_d  = filter_by_dates(all_data['kw_daily'],  'date', sd, ed)
    pm_d  = filter_by_dates(all_data['pm_daily'],  'date', sd, ed)

    # 2. 彙總廣告活動 (Camp) - 確保從 raw 重新篩選以保證準確
    asa_c = reagg_camp_from_raw(all_data['asa_raw'], '廣告活動', ['曝光','點擊','下載數','花費（台幣）'], all_data['conv'], 'ASA', sd, ed)
    kw_c  = reagg_camp_from_raw(all_data['kw_raw'],  '廣告活動', ['曝光','點擊','花費'], all_data['conv'], 'KW', sd, ed)
    pm_c  = reagg_camp_from_raw(all_data['pm_raw'],  '廣告活動', ['曝光','點擊','花費'], all_data['conv'], 'PM', sd, ed)

    # ══════════════════════════════════════════════════════
    # 儀表板主視圖
    # ══════════════════════════════════════════════════════
    st.title("廣告成效總覽")
    st.caption(f"數據範圍：{sd} 至 {ed} | 資料最後更新：{all_data['meta'].get('generated','--')}")

    # --- KPI Row ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    # 綜合花費
    total_spend = sc(asa_d, 'spend') + sc(kw_d, 'spend') + sc(pm_d, 'spend')
    with kpi1:
        st.markdown(f'<div class="kpi"><div class="kpi-label">總花費 (TWD)</div><div class="kpi-value">${total_spend:,.0f}</div></div>', unsafe_allow_html=True)

    # 總點擊
    total_clicks = sc(asa_d, 'clk') + sc(kw_d, 'clk') + sc(pm_d, 'clk')
    with kpi2:
        st.markdown(f'<div class="kpi"><div class="kpi-label">總點擊次數</div><div class="kpi-value">{total_clicks:,.0f}</div></div>', unsafe_allow_html=True)

    # 總進件 (從轉換表加總)
    conv_filtered = filter_by_dates(all_data['conv'], 'date', sd, ed)
    total_jin = sc(conv_filtered, '進件數')
    with kpi3:
        st.markdown(f'<div class="kpi"><div class="kpi-label">總進件數</div><div class="kpi-value">{total_jin:,.0f}</div></div>', unsafe_allow_html=True)

    # 平均 CPL
    avg_cpl = sdiv(total_spend, total_jin)
    with kpi4:
        st.markdown(f'<div class="kpi"><div class="kpi-label">平均進件成本 (CPL)</div><div class="kpi-value">${avg_cpl:,.0f}</div></div>', unsafe_allow_html=True)

    # --- 圖表區：趨勢圖 ---
    st.subheader("平台花費趨勢")
    trend_data = []
    # 整合各平台 Daily 資料供繪圖
    for df, label in [(asa_d, 'ASA'), (kw_d, 'Google KW'), (pm_d, 'Google PMax')]:
        if not df.empty:
            tmp = df[['date', 'spend']].copy()
            tmp['平台'] = label
            trend_data.append(tmp)
    
    if trend_data:
        full_trend = pd.concat(trend_data)
        fig_line = px.line(full_trend, x='date', y='spend', color='平台', markers=True, 
                           template="plotly_white", color_discrete_sequence=["#2563EB", "#10B981", "#F59E0B"])
        fig_line.update_layout(hovermode="x unified", margin=dict(t=20, b=20))
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("該區間暫無趨勢數據可顯示。")

    # --- 平台明細表格 ---
    st.subheader("各平台成效明細")
    tabs = st.tabs(["Apple ASA", "Google KW", "Google PMax"])
    
    with tabs[0]:
        if not asa_c.empty:
            st.dataframe(asa_c, use_container_width=True, hide_index=True)
        else:
            st.write("無 ASA 資料")
            
    with tabs[1]:
        if not kw_c.empty:
            st.dataframe(kw_c, use_container_width=True, hide_index=True)
        else:
            st.write("無 Google KW 資料")

    with tabs[2]:
        if not pm_c.empty:
            st.dataframe(pm_c, use_container_width=True, hide_index=True)
        else:
            st.write("無 Google PMax 資料")

    # --- 轉換漏斗圖 ---
    st.markdown("---")
    st.subheader("轉換漏斗（全平台合計）")
    
    # 整合三方數據的漏斗指標
    all_metrics = pd.concat([
        asa_c[['clk','jin','wan']] if not asa_c.empty else pd.DataFrame(),
        kw_c[['clk','jin','wan']] if not kw_c.empty else pd.DataFrame(),
        pm_c[['clk','jin','wan']] if not pm_c.empty else pd.DataFrame()
    ])

    if not all_metrics.empty:
        f_clk = sc(all_metrics, 'clk')
        f_jin = sc(all_metrics, 'jin')
        f_wan = sc(all_metrics, 'wan')
        
        fig_funnel = go.Figure(go.Funnel(
            y = ["點擊次數", "進件數", "完開數"],
            x = [f_clk, f_jin, f_wan],
            textinfo = "value+percent initial",
            marker = {"color": ["#93C5FD", "#60A5FA", "#2563EB"]}
        ))
        fig_funnel.update_layout(margin=dict(l=200, r=200, t=50, b=50))
        st.plotly_chart(fig_funnel, use_container_width=True)
    else:
        st.warning("選取區間內無足夠的點擊或轉換資料來生成漏斗圖。")

else:
    st.info("👋 請在左側上傳 Excel 廣告數據檔案以開始分析。")
