import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面配置 ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告儀表板", initial_sidebar_state="expanded")

# --- 2. 強制全局 CSS 覆蓋 (解決黑白半屏問題與細節排版) ---
st.markdown("""
    <style>
    /* 強制鎖定 Light Mode 配色，杜絕系統深色模式干擾 */
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

    /* 強制主背景與側邊欄顏色 */
    [data-testid="stAppViewContainer"] {
        background-color: var(--bg) !important;
    }
    [data-testid="stSidebar"] {
        background-color: var(--panel) !important;
        border-right: 1px solid var(--border) !important;
    }
    /* 隱藏預設頂部裝飾條 */
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }
    
    /* 側邊欄文字強制深色 */
    [data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    /* 頂部 Tab 導覽列極致還原 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background-color: transparent;
        border-bottom: 1px solid var(--border);
        padding: 0;
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: transparent;
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        padding: 0 24px;
        font-weight: 600;
        color: var(--muted);
        font-size: 15px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--text) !important;
        border-bottom: 3px solid var(--gkw) !important;
        background-color: transparent !important;
    }

    /* 指標卡片 (圖卡) 深度雕刻 */
    [data-testid="stMetric"] {
        background-color: var(--panel) !important;
        padding: 20px 24px !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* 卡片數值文字 */
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: var(--text) !important;
        font-size: 28px !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }

    /* 渠道專屬卡片邊框 */
    .metric-asa [data-testid="stMetric"] { border-left: 6px solid var(--asa) !important; }
    .metric-gkw [data-testid="stMetric"] { border-left: 6px solid var(--gkw) !important; }
    .metric-pmax [data-testid="stMetric"] { border-left: 6px solid var(--pmax) !important; }

    /* 進度條細節還原 */
    .stProgress > div > div > div > div {
        background-color: var(--gkw) !important;
        border-radius: 999px;
    }

    /* 表格容器白底與邊框 */
    [data-testid="stDataFrame"] {
        background-color: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 側邊欄控制與參數設定 ---
with st.sidebar:
    st.markdown("<h3 style='margin-bottom: 20px;'>⚙️ 系統設定</h3>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("上傳原始數據 (raw-2.xlsx)", type=["xlsx"])
    
    st.markdown("<hr style='margin: 20px 0; border-color: #e5e7eb;'>", unsafe_allow_html=True)
    st.markdown("#### 🎯 月度預算設定")
    b_asa = st.number_input("ASA 預算", value=150000, step=10000)
    b_gkw = st.number_input("Google KW 預算", value=500000, step=10000)
    b_pmax = st.number_input("Google Pmax 預算", value=200000, step=10000)
    
    st.markdown("<hr style='margin: 20px 0; border-color: #e5e7eb;'>", unsafe_allow_html=True)
    st.markdown("#### 📅 WOW 分析波段")
    c_s = st.date_input("本週開始", datetime(2026, 4, 13))
    c_e = st.date_input("本週結束", datetime(2026, 4, 19))
    p_s = st.date_input("上週開始", datetime(2026, 4, 6))
    p_e = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 4. 數據處理引擎 (細緻抓取曝光、點擊、完開) ---
@st.cache_data
def process_data(file):
    if not file: return None
    xls = pd.ExcelFile(file)
    
    configs = {
        'ASA': {'tag': 'ASA', 'cost': '花費（台幣）'},
        'Google KW': {'tag': 'KW', 'cost': '花費'},
        'Google Pmax': {'tag': 'PMAX', 'cost': '花費'}
    }
    
    combined = []
    for ch_name, cfg in configs.items():
        sheet = next((s for s in xls.sheet_names if cfg['tag'].upper() in s.upper()), None)
        if sheet:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # 標準化欄位，確保渠道分析細緻度
            df['Channel'] = ch_name
            df['Cost'] = df[cfg['cost']].fillna(0) if cfg['cost'] in df.columns else 0
            df['Impr'] = df['曝光'].fillna(0) if '曝光' in df.columns else 0
            df['Click'] = df['點擊'].fillna(0) if '點擊' in df.columns else 0
            df['Inq'] = df['進件數'].fillna(0) if '進件數' in df.columns else 0
            df['Open'] = df['完開數'].fillna(0) if '完開數' in df.columns else 0
            
            # 維度補全
            df['Campaign'] = df['廣告活動'] if '廣告活動' in df.columns else '未分類'
            df['Keyword'] = df['廣告關鍵字'] if '廣告關鍵字' in df.columns else '-'
            
            combined.append(df)
            
    return pd.concat(combined, ignore_index=True) if combined else None

# --- 5. 版位渲染 ---
if uploaded_file:
    df_all = process_data(uploaded_file)
    if df_all is not None:
        tab_sum, tab_asa, tab_gkw, tab_pmax = st.tabs(["📊 總覽儀表板", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- [頁面 1] 總覽儀表板 ---
        with tab_sum:
            st.markdown("<h2 style='color: #111827; margin-bottom: 24px;'>全渠道投放總覽</h2>", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            budgets = [("ASA", b_asa, c1), ("Google KW", b_gkw, c2), ("Google Pmax", b_pmax, c3)]
            
            for name, target, col in budgets:
                spent = df_all[df_all['Channel'] == name]['Cost'].sum()
                rate = min(spent/target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"<div style='font-size: 16px; font-weight: 600; color: #374151; margin-bottom: 8px;'>{name} 預算執行度</div>", unsafe_allow_html=True)
                    st.progress(rate)
                    st.markdown(f"<div style='font-size: 13px; color: #6b7280; margin-top: 4px;'>已花費 <b>${spent:,.0f}</b> / 目標 <b>${target:,.0f}</b> ({rate:.1%})</div>", unsafe_allow_html=True)
            
            st.markdown("<hr style='margin: 32px 0; border-color: #e5e7eb;'>", unsafe_allow_html=True)
            st.markdown("<h3 style='color: #111827; margin-bottom: 16px;'>每日投放花費趨勢</h3>", unsafe_allow_html=True)
            
            # 趨勢圖還原 (Plotly White 主題，精準配色)
            fig = go.Figure()
            color_map = {"ASA": "#8b5cf6", "Google KW": "#2563eb", "Google Pmax": "#10b981"}
            for ch, color in color_map.items():
                daily = df_all[df_all['Channel'] == ch].groupby('Date')['Cost'].sum().reset_index()
                fig.add_trace(go.Scatter(x=daily['Date'], y=daily['Cost'], name=ch, line=dict(color=color, width=3, shape='spline')))
            
            fig.update_layout(
                template="plotly_white", margin=dict(l=0, r=0, t=10, b=0), height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#f3f4f6")
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- [頁面 2, 3, 4] 渠道分析頁面 ---
        def render_channel(channel_name, css_class):
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            
            # 數據切片
            curr = df_all[(df_all['Channel'] == channel_name) & (df_all['Date'] >= pd.Timestamp(c_s)) & (df_all['Date'] <= pd.Timestamp(c_e))]
            prev = df_all[(df_all['Channel'] == channel_name) & (df_all['Date'] >= pd.Timestamp(p_s)) & (df_all['Date'] <= pd.Timestamp(p_e))]
            
            # 計算核心指標
            c_cost, c_inq, c_clk = curr['Cost'].sum(), curr['Inq'].sum(), curr['Click'].sum()
            p_cost, p_inq = prev['Cost'].sum(), prev['Inq'].sum()
            c_cpa = c_cost / c_inq if c_inq > 0 else 0
            p_cpa = p_cost / p_inq if p_inq > 0 else 0
            
            def format_wow(c, p): return f"{(c-p)/p:+.1%}" if p > 0 else "0.0%"

            # 圖卡佈局
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("本週進件數", f"{c_inq:,.0f}", format_wow(c_inq, p_inq))
            m2.metric("CPA (進件成本)", f"${c_cpa:,.0f}", format_wow(c_cpa, p_cpa), delta_color="inverse")
            m3.metric("本週花費", f"${c_cost:,.0f}", format_wow(c_cost, p_cost), delta_color="inverse")
            m4.metric("點擊轉化率 (CVR)", f"{c_inq/c_clk:.2%}" if c_clk > 0 else "0.00%")
            
            st.markdown("<hr style='margin: 32px 0; border-color: #e5e7eb;'>", unsafe_allow_html=True)
            st.markdown("<h3 style='color: #111827; margin-bottom: 16px;'>廣告活動明細清單</h3>", unsafe_allow_html=True)
            
            # 細緻的 DataFrame 排版，完全對齊廣告欄位
            detail_df = curr.groupby(['Campaign', 'Keyword']).agg({
                'Impr': 'sum', 'Click': 'sum', 'Cost': 'sum', 'Inq': 'sum', 'Open': 'sum'
            }).reset_index()
            
            detail_df = detail_df.rename(columns={
                'Campaign': '廣告活動', 'Keyword': '廣告關鍵字', 
                'Impr': '曝光', 'Click': '點擊', 'Cost': '花費', 
                'Inq': '進件數', 'Open': '完開數'
            }).sort_values('花費', ascending=False)
            
            # 使用 Streamlit 內建高階欄位設定，確保數字格式漂亮
            st.dataframe(
                detail_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "花費": st.column_config.NumberColumn("花費", format="$%d"),
                    "曝光": st.column_config.NumberColumn("曝光", format="%d"),
                    "點擊": st.column_config.NumberColumn("點擊", format="%d")
                }
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with tab_asa: render_channel("ASA", "metric-asa")
        with tab_gkw: render_channel("Google KW", "metric-gkw")
        with tab_pmax: render_channel("Google Pmax", "metric-pmax")
