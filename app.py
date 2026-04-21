import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面配置 ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告儀表板", initial_sidebar_state="expanded")

# --- 2. 終極 CSS 覆蓋 (強制消除深色模式干擾，還原 HTML 視覺) ---
st.markdown("""
    <style>
    /* 全局變數定義 - 嚴格遵守 HTML 檔案中的設計規範 */
    :root {
        --bg: #f5f7fa;
        --panel: #ffffff;
        --border: #e5e7eb;
        --text: #111827;
        --muted: #6b7280;
        --asa: #8b5cf6;
        --gkw: #2563eb;
        --pmax: #10b981;
    }

    /* 解決「背景一黑一白」的核心：強制覆蓋所有背景相關標籤 */
    [data-testid="stAppViewContainer"], 
    [data-testid="stHeader"], 
    [data-testid="stToolbar"],
    .main {
        background-color: var(--bg) !important;
    }

    /* 側邊欄強制鎖定白色，消除深色模式半截黑的情況 */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarNav"] {
        background-color: var(--panel) !important;
        border-right: 1px solid var(--border) !important;
    }

    /* 強制所有文字顏色，避免深色模式下文字變白看不見 */
    h1, h2, h3, p, span, label, div {
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    /* 導覽標籤 Tab 樣式極致還原 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background-color: transparent;
        border-bottom: 2px solid var(--border);
        padding: 0;
        margin-bottom: 30px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 52px;
        background-color: transparent;
        border: none;
        border-bottom: 4px solid transparent;
        padding: 0 32px;
        font-weight: 700;
        color: var(--muted) !important;
        font-size: 16px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--gkw) !important;
        border-bottom: 4px solid var(--gkw) !important;
    }

    /* 指標卡片 (圖卡) 樣式 - 像素級雕刻 */
    [data-testid="stMetric"] {
        background-color: var(--panel) !important;
        padding: 24px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
        border: 1px solid var(--border) !important;
        transition: transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
    }
    
    /* 指標數值文字 */
    [data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: var(--text) !important;
        font-size: 32px !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted) !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }

    /* 渠道專屬卡片左側色標 */
    .metric-asa [data-testid="stMetric"] { border-left: 8px solid var(--asa) !important; }
    .metric-gkw [data-testid="stMetric"] { border-left: 8px solid var(--gkw) !important; }
    .metric-pmax [data-testid="stMetric"] { border-left: 8px solid var(--pmax) !important; }

    /* 進度條自定義 */
    .stProgress > div > div > div > div {
        background-color: var(--gkw) !important;
        height: 10px;
        border-radius: 5px;
    }

    /* 表格容器精緻化 */
    [data-testid="stDataFrame"] {
        background-color: var(--panel);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.04);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 側邊欄控制與參數設定 ---
with st.sidebar:
    st.markdown("<h2 style='margin-bottom: 20px; font-weight: 800;'>Pocket BI</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 上傳數據 (raw-2.xlsx)", type=["xlsx"])
    
    st.markdown("<div style='margin: 24px 0; border-top: 1px solid #e5e7eb;'></div>", unsafe_allow_html=True)
    st.markdown("### 🎯 渠道預算目標")
    b_asa = st.number_input("ASA 目標", value=150000, step=5000)
    b_gkw = st.number_input("GKW 目標", value=500000, step=10000)
    b_pmax = st.number_input("Pmax 目標", value=200000, step=5000)
    
    st.markdown("<div style='margin: 24px 0; border-top: 1px solid #e5e7eb;'></div>", unsafe_allow_html=True)
    st.markdown("### 📅 波段對比 (WOW)")
    c_s = st.date_input("本週開始", datetime(2026, 4, 13))
    c_e = st.date_input("本週結束", datetime(2026, 4, 19))
    p_s = st.date_input("上週開始", datetime(2026, 4, 6))
    p_e = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 4. 數據處理引擎 (細緻度升級：精準對齊所有廣告指標) ---
@st.cache_data
def process_data(file):
    if not file: return None
    xls = pd.ExcelFile(file)
    
    configs = {
        'ASA': {'tag': 'ASA', 'cost_col': '花費（台幣）'},
        'Google KW': {'tag': 'KW', 'cost_col': '花費'},
        'Google Pmax': {'tag': 'PMAX', 'cost_col': '花費'}
    }
    
    all_data = []
    for ch_name, cfg in configs.items():
        sheet = next((s for s in xls.sheet_names if cfg['tag'].upper() in s.upper()), None)
        if sheet:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # 指標標準化
            df['Channel'] = ch_name
            df['Cost'] = df[cfg['cost_col']].fillna(0) if cfg['cost_col'] in df.columns else 0
            df['Impr'] = df['曝光'].fillna(0) if '曝光' in df.columns else 0
            df['Click'] = df['點擊'].fillna(0) if '點擊' in df.columns else 0
            df['Inquiry'] = df['進件數'].fillna(0) if '進件數' in df.columns else 0
            df['Open'] = df['完開數'].fillna(0) if '完開數' in df.columns else 0
            
            # 維度擴展 (確保渠道分析細緻度)
            df['Campaign'] = df['廣告活動'].fillna('未命名活動')
            df['Group'] = df['廣告群組'].fillna('-') if '廣告群組' in df.columns else '-'
            df['Keyword'] = df['廣告關鍵字'].fillna('-') if '廣告關鍵字' in df.columns else '-'
            
            all_data.append(df)
            
    return pd.concat(all_data, ignore_index=True) if all_data else None

# --- 5. 版位渲染 ---
if uploaded_file:
    df_raw = process_data(uploaded_file)
    if df_raw is not None:
        tab_main, tab_asa, tab_gkw, tab_pmax = st.tabs(["🏠 總覽儀表板", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- [總覽] ---
        with tab_main:
            st.markdown("<h2 style='font-weight: 800; margin-bottom: 24px;'>投放執行概況</h2>", unsafe_allow_html=True)
            
            cols = st.columns(3)
            budgets = [("ASA", b_asa, cols[0]), ("Google KW", b_gkw, cols[1]), ("Google Pmax", b_pmax, cols[2])]
            
            for name, target, col in budgets:
                spent = df_raw[df_raw['Channel'] == name]['Cost'].sum()
                rate = min(spent/target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"**{name} 預算進度**")
                    st.progress(rate)
                    st.markdown(f"<p style='font-size: 14px; color: #6b7280;'>已花費 ${spent:,.0f} / 目標 ${target:,.0f} ({rate:.1%})</p>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)
            st.markdown("### 投放金額趨勢")
            
            trend_fig = go.Figure()
            colors = {"ASA": "#8b5cf6", "Google KW": "#2563eb", "Google Pmax": "#10b981"}
            for ch, color in colors.items():
                d = df_raw[df_raw['Channel'] == ch].groupby('Date')['Cost'].sum().reset_index()
                trend_fig.add_trace(go.Scatter(x=d['Date'], y=d['Cost'], name=ch, line=dict(color=color, width=4, shape='spline')))
            
            trend_fig.update_layout(
                template="plotly_white", margin=dict(l=0, r=0, t=10, b=0), height=400,
                hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(trend_fig, use_container_width=True)

        # --- [渠道分析] ---
        def render_channel_detail(ch_name, css_class):
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            
            # 數據過濾
            c_df = df_raw[(df_raw['Channel'] == ch_name) & (df_raw['Date'] >= pd.Timestamp(c_s)) & (df_raw['Date'] <= pd.Timestamp(c_e))]
            p_df = df_raw[(df_raw['Channel'] == ch_name) & (df_raw['Date'] >= pd.Timestamp(p_s)) & (df_raw['Date'] <= pd.Timestamp(p_e))]
            
            # 核心指標計算
            c_cost, c_inq, c_clk = c_df['Cost'].sum(), c_df['Inquiry'].sum(), c_df['Click'].sum()
            p_cost, p_inq = p_df['Cost'].sum(), p_df['Inquiry'].sum()
            c_cpa = c_cost / c_inq if c_inq > 0 else 0
            p_cpa = p_cost / p_inq if p_inq > 0 else 0
            c_cvr = c_inq / c_clk if c_clk > 0 else 0
            
            def get_wow(cur, pre): return f"{(cur-pre)/pre:+.1%}" if pre > 0 else "0.0%"

            # 四大指標卡片
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("進件數", f"{c_inq:,.0f}", get_wow(c_inq, p_inq))
            m2.metric("CPA (成本/進件)", f"${c_cpa:,.0f}", get_wow(c_cpa, p_cpa), delta_color="inverse")
            m3.metric("本波段花費", f"${c_cost:,.0f}", get_wow(c_cost, p_cost), delta_color="inverse")
            m4.metric("CVR (點擊轉化)", f"{c_cvr:.2%}")
            
            st.markdown("<div style='margin: 40px 0; border-top: 2px dashed #e5e7eb;'></div>", unsafe_allow_html=True)
            st.markdown("### 廣告活動與關鍵字細節")
            
            # 細緻的資料聚合，展現完整行銷漏斗
            detail = c_df.groupby(['Campaign', 'Group', 'Keyword']).agg({
                'Impr': 'sum', 'Click': 'sum', 'Cost': 'sum', 'Inquiry': 'sum', 'Open': 'sum'
            }).reset_index()
            
            # 計算衍生指標
            detail['CTR'] = detail['Click'] / detail['Impr']
            detail['CPA'] = detail['Cost'] / detail['Inquiry']
            detail.loc[detail['Inquiry'] == 0, 'CPA'] = 0
            
            detail = detail.rename(columns={
                'Campaign': '活動名稱', 'Group': '群組', 'Keyword': '關鍵字',
                'Impr': '曝光', 'Click': '點擊', 'Cost': '花費', 'Inquiry': '進件', 'Open': '完開'
            }).sort_values('花費', ascending=False)
            
            # 格式化表格輸出
            st.dataframe(
                detail, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "花費": st.column_config.NumberColumn("花費", format="$%d"),
                    "曝光": st.column_config.NumberColumn("曝光", format="%d"),
                    "點擊": st.column_config.NumberColumn("點擊", format="%d"),
                    "CTR": st.column_config.ProgressColumn("點擊率", format="%.2f", min_value=0, max_value=0.2),
                    "CPA": st.column_config.NumberColumn("CPA", format="$%.0f")
                }
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with tab_asa: render_channel_detail("ASA", "metric-asa")
        with tab_gkw: render_channel_detail("Google KW", "metric-gkw")
        with tab_pmax: render_channel_detail("Google Pmax", "metric-pmax")
else:
    st.info("👋 請在左側上傳 raw-2.xlsx 檔案以開始分析。")
