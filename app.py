import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面配置 ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告儀表板", initial_sidebar_state="expanded")

# --- 2. 終極 CSS 覆蓋 (強制消除深色模式干擾，還原 HTML 視覺) ---
st.markdown("""
    <style>
    /* 全局變數定義 */
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

    /* 全局背景 */
    [data-testid="stAppViewContainer"], 
    [data-testid="stHeader"], 
    [data-testid="stToolbar"],
    .main {
        background-color: var(--bg) !important;
    }

    /* 側邊欄樣式 */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarNav"] {
        background-color: var(--panel) !important;
        border-right: 1px solid var(--border) !important;
    }

    /* 強制文字顏色 */
    h1, h2, h3, p, span, label, div {
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    /* Tab 標籤樣式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        border-bottom: 2px solid var(--border);
        padding: 0;
        margin-bottom: 30px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 52px;
        background-color: transparent;
        border-radius: 8px 8px 0 0;
        border: none;
        padding: 0 24px;
        font-weight: 700;
        color: var(--muted) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--gkw) !important;
        background-color: #fff !important;
        border: 1px solid var(--border) !important;
        border-bottom: 3px solid var(--gkw) !important;
    }

    /* 指標卡片 */
    [data-testid="stMetric"] {
        background-color: var(--panel) !important;
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        border: 1px solid var(--border) !important;
    }
    [data-testid="stMetricValue"] {
        font-weight: 800 !important;
        font-size: 28px !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted) !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }

    /* 進度條容器樣式 (模擬圖片中的設計) */
    .progress-card {
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid var(--border);
        margin-bottom: 16px;
    }
    .progress-label {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-weight: 700;
    }
    
    /* 表格精緻化 */
    [data-testid="stDataFrame"] {
        background-color: var(--panel);
        border-radius: 12px;
        overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 側邊欄 ---
with st.sidebar:
    st.markdown("<h2 style='font-weight: 800;'>Pocket BI</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 上傳數據 (raw-2.xlsx)", type=["xlsx"])
    
    st.divider()
    st.markdown("### 🎯 渠道預算目標")
    b_asa = st.number_input("ASA 目標", value=150000, step=5000)
    b_gkw = st.number_input("GKW 目標", value=500000, step=10000)
    b_pmax = st.number_input("Pmax 目標", value=200000, step=5000)
    
    st.divider()
    st.markdown("### 📅 波段對比 (WOW)")
    c_s = st.date_input("本週開始", datetime(2026, 4, 13))
    c_e = st.date_input("本週結束", datetime(2026, 4, 19))
    p_s = st.date_input("上週開始", datetime(2026, 4, 6))
    p_e = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 4. 數據處理引擎 ---
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
            df['Download'] = df['下載數'].fillna(0) if '下載數' in df.columns else (df['點擊'] * 0.1 if ch_name == 'ASA' else 0)
            df['Inquiry'] = df['進件數'].fillna(0) if '進件數' in df.columns else 0
            df['Open'] = df['完開數'].fillna(0) if '完開數' in df.columns else 0
            
            # 維度擴展
            df['Campaign'] = df['廣告活動'].fillna('未命名活動')
            df['Group'] = df['廣告群組'].fillna('-') if '廣告群組' in df.columns else '-'
            df['Keyword'] = df['廣告關鍵字'].fillna('-') if '廣告關鍵字' in df.columns else '-'
            
            all_data.append(df)
            
    return pd.concat(all_data, ignore_index=True) if all_data else None

# --- 5. 版面渲染 ---
if uploaded_file:
    df_raw = process_data(uploaded_file)
    if df_raw is not None:
        tab_main, tab_asa, tab_gkw, tab_pmax = st.tabs(["🏠 總覽儀表板", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- [總覽] ---
        with tab_main:
            st.markdown("<h2 style='font-weight: 800;'>投放執行概況</h2>", unsafe_allow_html=True)
            
            # 進度條卡片化渲染 (精準模擬圖片樣式)
            p_cols = st.columns(3)
            budgets = [
                ("Apple Search Ads", b_asa, p_cols[0], "#8b5cf6"),
                ("Google KW", b_gkw, p_cols[1], "#2563eb"),
                ("Google Pmax", b_pmax, p_cols[2], "#10b981")
            ]
            
            for name, target, col, color in budgets:
                spent = df_raw[df_raw['Channel'].str.contains(name.split()[-1])]['Cost'].sum()
                rate = min(spent/target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"""
                    <div class="progress-card">
                        <div class="progress-label">
                            <span>{name}</span>
                            <span>{rate:.1%}</span>
                        </div>
                        <div style="background:#eee; height:8px; border-radius:4px;">
                            <div style="background:{color}; width:{rate*100}%; height:8px; border-radius:4px;"></div>
                        </div>
                        <div style="margin-top:10px; font-size:13px; color:#6b7280;">
                            已花費 ${spent:,.0f} / 目標 ${target:,.0f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("### 投放金額趨勢")
            trend_fig = go.Figure()
            colors = {"ASA": "#8b5cf6", "Google KW": "#2563eb", "Google Pmax": "#10b981"}
            for ch, color in colors.items():
                d = df_raw[df_raw['Channel'] == ch].groupby('Date')['Cost'].sum().reset_index()
                trend_fig.add_trace(go.Scatter(x=d['Date'], y=d['Cost'], name=ch, line=dict(color=color, width=3)))
            trend_fig.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=10, b=0), height=350, hovermode="x unified")
            st.plotly_chart(trend_fig, use_container_width=True)

        # --- [渠道分析邏輯] ---
        def render_channel_detail(ch_name):
            # 數據切片
            c_df = df_raw[(df_raw['Channel'] == ch_name) & (df_raw['Date'] >= pd.Timestamp(c_s)) & (df_raw['Date'] <= pd.Timestamp(c_e))]
            p_df = df_raw[(df_raw['Channel'] == ch_name) & (df_raw['Date'] >= pd.Timestamp(p_s)) & (df_raw['Date'] <= pd.Timestamp(p_e))]
            
            # 指標計算
            metrics = {
                "Cost": (c_df['Cost'].sum(), p_df['Cost'].sum()),
                "Inq": (c_df['Inquiry'].sum(), p_df['Inquiry'].sum()),
                "Clk": (c_df['Click'].sum(), p_df['Click'].sum()),
                "Down": (c_df['Download'].sum(), p_df['Download'].sum())
            }
            
            c_cpa = metrics["Cost"][0] / metrics["Inq"][0] if metrics["Inq"][0] > 0 else 0
            p_cpa = metrics["Cost"][1] / metrics["Inq"][1] if metrics["Inq"][1] > 0 else 0
            
            def wow(cur, pre): return f"{(cur-pre)/pre:+.1%}" if pre > 0 else "0.0%"

            # 指標列
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("進件數", f"{metrics['Inq'][0]:,.0f}", wow(metrics["Inq"][0], metrics["Inq"][1]))
            m2.metric("CPA (成本/進件)", f"${c_cpa:,.0f}", wow(c_cpa, p_cpa), delta_color="inverse")
            m3.metric("本波段花費", f"${metrics['Cost'][0]:,.0f}", wow(metrics["Cost"][0], metrics["Cost"][1]), delta_color="inverse")
            m4.metric("點擊數", f"{metrics['Clk'][0]:,.0f}", wow(metrics["Clk"][0], metrics["Clk"][1]))

            st.divider()
            st.markdown(f"### {ch_name} 數據明細清單")
            
            # 聚合明細 (對齊圖片中的豐富度)
            group_cols = ['Campaign', 'Group']
            if ch_name != 'Google Pmax': group_cols.append('Keyword')
            
            detail = c_df.groupby(group_cols).agg({
                'Impr': 'sum', 'Click': 'sum', 'Download': 'sum', 
                'Cost': 'sum', 'Inquiry': 'sum', 'Open': 'sum'
            }).reset_index()
            
            # 衍生比率
            detail['CTR'] = detail['Click'] / detail['Impr']
            detail['CVR'] = detail['Inquiry'] / detail['Click']
            detail['CPA'] = detail['Cost'] / detail['Inquiry']
            detail.replace([float('inf'), -float('inf')], 0, inplace=True)
            detail.fillna(0, inplace=True)
            
            # 欄位重命名
            rename_map = {
                'Campaign': '廣告活動', 'Group': '廣告群組', 'Keyword': '關鍵字',
                'Impr': '曝光', 'Click': '點擊', 'Download': '下載', 
                'Cost': '花費', 'Inquiry': '進件', 'Open': '完開'
            }
            detail = detail.rename(columns=rename_map).sort_values('花費', ascending=False)
            
            # 顯示表格
            st.dataframe(
                detail, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "花費": st.column_config.NumberColumn("花費", format="$%d"),
                    "曝光": st.column_config.NumberColumn("曝光", format="%d"),
                    "點擊": st.column_config.NumberColumn("點擊", format="%d"),
                    "CTR": st.column_config.NumberColumn("點擊率", format="%.2f%%"),
                    "CPA": st.column_config.NumberColumn("CPA", format="$%.0f"),
                    "CVR": st.column_config.ProgressColumn("轉化率", format="%.2f", min_value=0, max_value=0.5)
                }
            )

        with tab_asa: render_channel_detail("ASA")
        with tab_gkw: render_channel_detail("Google KW")
        with tab_pmax: render_channel_detail("Google Pmax")
else:
    st.info("👋 請上傳數據檔案以展開完整分析。")
