import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面配置與精細 UI 雕刻 ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告投放儀表板", page_icon="📊")

# 注入 CSS：完全還原截圖中的現代化 BI 介面
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        background-color: #f8fafc;
    }

    /* 頂部 Tab 導覽列還原 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #ffffff;
        padding: 12px 24px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        margin-bottom: 24px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 54px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        background-color: #ffffff;
        padding: 0 28px;
        font-weight: 600;
        color: #64748b;
        transition: all 0.2s ease-in-out;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border-color: #2563eb !important;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.25);
    }

    /* 指標卡片設計還原 (Metrics Cards) */
    [data-testid="stMetric"] {
        background: white;
        padding: 24px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04) !important;
        border: 1px solid #f1f5f9 !important;
        transition: transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-4px);
    }
    
    /* 數值樣式加粗 */
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: #1e293b !important;
        letter-spacing: -0.02em;
    }

    /* 預算執行條配色 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        border-radius: 10px;
    }

    /* 側邊欄優化 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #f1f5f9;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：BI 參數設定 ---
with st.sidebar:
    st.markdown("<h2 style='color:#1e293b;'>⚙️ BI 控制中心</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("請上傳原始數據 (xlsx)", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 月度預算指標")
    val_asa = st.number_input("ASA 目標", value=150000, step=5000)
    val_gkw = st.number_input("Google KW 目標", value=500000, step=5000)
    val_pmax = st.number_input("Google Pmax 目標", value=200000, step=5000)
    
    st.divider()
    st.subheader("📅 WOW 分析波段")
    c_s = st.date_input("本週起", datetime(2026, 4, 13))
    c_e = st.date_input("本週迄", datetime(2026, 4, 19))
    p_s = st.date_input("上週起", datetime(2026, 4, 6))
    p_e = st.date_input("上週迄", datetime(2026, 4, 12))

# --- 3. 數據雕刻邏輯 ---
@st.cache_data
def load_bi_data(file):
    if file is None: return None
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names
    
    all_dfs = []
    # 渠道與 Excel 標題匹配定義
    ch_configs = [
        {'id': 'ASA', 'tag': 'ASA', 'cost': '花費（台幣）', 'color': '#8b5cf6'},
        {'id': 'GKW', 'tag': 'KW', 'cost': '花費', 'color': '#2563eb'},
        {'id': 'PMAX', 'tag': 'PMAX', 'cost': '花費', 'color': '#10b981'}
    ]
    
    for cfg in ch_configs:
        sheet_match = next((s for s in sheets if cfg['tag'].upper() in s.upper()), None)
        if sheet_match:
            df = pd.read_excel(file, sheet_name=sheet_match)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
            df['Channel'] = cfg['id']
            df['Metric_Cost'] = df[cfg['cost']] if cfg['cost'] in df.columns else 0
            df['Metric_Conv'] = df['進件數'] if '進件數' in df.columns else 0
            df['Metric_Click'] = df['點擊'] if '點擊' in df.columns else 0
            if '廣告關鍵字' not in df.columns: df['廣告關鍵字'] = '-'
            all_dfs.append(df)
            
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

# --- 4. BI 畫面渲染 ---
if uploaded_file:
    bi_df = load_bi_data(uploaded_file)
    
    if bi_df is not None:
        # 分頁功能還原 (完全對應截圖中的四張頁面)
        tab1, tab2, tab3, tab4 = st.tabs(["🏠 數據總覽", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- Tab 1: 總覽 (對應 廣告投放儀表板.jpg) ---
        with tab1:
            st.markdown("<h2 style='color:#1e293b;'>全渠道投放執行度</h2>", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            budgets = [("ASA", val_asa, c1), ("GKW", val_gkw, c2), ("PMAX", val_pmax, c3)]
            
            for cid, target, col in budgets:
                spent = bi_df[bi_df['Channel'] == cid]['Metric_Cost'].sum()
                rate = min(spent/target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"**{cid} 執行進度**")
                    st.progress(rate)
                    st.markdown(f"<span style='font-size:0.9rem; color:#64748b;'>已花費: ${spent:,.0f} / 目標: ${target:,.0f} ({rate:.1%})</span>", unsafe_allow_html=True)

            st.divider()
            st.subheader("📈 每日花費趨勢")
            fig = go.Figure()
            colors = {"ASA": "#8b5cf6", "GKW": "#2563eb", "PMAX": "#10b981"}
            for cid, color in colors.items():
                d_group = bi_df[bi_df['Channel'] == cid].groupby('Date')['Metric_Cost'].sum().reset_index()
                fig.add_trace(go.Scatter(x=d_group['Date'], y=d_group['Metric_Cost'], name=cid, line=dict(color=color, width=4, shape='spline')))
            
            fig.update_layout(template="simple_white", hovermode="x", height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # --- Tab 2/3/4: 渠道詳情還原 ---
        def draw_channel_page(cid, title, theme_color):
            st.markdown(f"<h2 style='color:{theme_color};'>{title}</h2>", unsafe_allow_html=True)
            
            # 數據切片
            curr = bi_df[(bi_df['Date'] >= pd.Timestamp(c_s)) & (bi_df['Date'] <= pd.Timestamp(c_e)) & (bi_df['Channel'] == cid)]
            prev = bi_df[(bi_df['Date'] >= pd.Timestamp(p_s)) & (bi_df['Date'] <= pd.Timestamp(p_e)) & (bi_df['Channel'] == cid)]
            
            # 指標匯總
            c_vals = {'cost': curr['Metric_Cost'].sum(), 'conv': curr['Metric_Conv'].sum(), 'clk': curr['Metric_Click'].sum()}
            p_vals = {'cost': prev['Metric_Cost'].sum(), 'conv': prev['Metric_Conv'].sum(), 'clk': prev['Metric_Click'].sum()}
            
            def get_delta(c, p): return f"{(c-p)/p:+.1%}" if p > 0 else "N/A"

            # 四格指標還原
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("本週進件數", f"{c_vals['conv']:,.0f}", get_delta(c_vals['conv'], p_vals['conv']))
            
            cur_cpa = c_vals['cost']/c_vals['conv'] if c_vals['conv'] > 0 else 0
            pre_cpa = p_vals['cost']/p_vals['conv'] if p_vals['conv'] > 0 else 0
            k2.metric("CPA (進件成本)", f"${cur_cpa:,.0f}", get_delta(cur_cpa, pre_cpa), delta_color="inverse")
            
            k3.metric("本週花費", f"${c_vals['cost']:,.0f}", get_delta(c_vals['cost'], p_vals['cost']), delta_color="inverse")
            
            cvr = c_vals['conv']/c_vals['clk'] if c_vals['clk'] > 0 else 0
            k4.metric("轉化率 (CVR)", f"{cvr:.2%}")

            st.divider()
            st.write("📋 詳細數據清單 (本週區間)")
            # 表格還原
            table_out = curr.groupby(['廣告活動', '廣告關鍵字']).agg({
                'Metric_Cost': 'sum', 'Metric_Conv': 'sum', 'Metric_Click': 'sum'
            }).reset_index().rename(columns={'Metric_Cost': '花費', 'Metric_Conv': '進件', 'Metric_Click': '點擊'}).sort_values('花費', ascending=False)
            st.dataframe(table_out, use_container_width=True, height=450)

        with tab2: draw_channel_page("ASA", "ASA 深度分析", "#8b5cf6")
        with tab3: draw_channel_page("GKW", "Google KW 分析", "#2563eb")
        with tab4: draw_channel_page("PMAX", "Pmax 成效監控", "#10b981")

else:
    # 待機引導介面
    st.markdown("""
        <div style="text-align: center; padding: 120px 20px;">
            <h1 style="color: #1e293b; font-size: 2.8rem;">Pocket BI 廣告投放儀表板</h1>
            <p style="color: #64748b; font-size: 1.2rem;">請於左側側邊欄上傳 <b>廣告raw-2.xlsx</b> 以完整呈現四路監控分頁。</p>
            <div style="margin-top: 50px;">
                <span style="background:#e2e8f0; padding:8px 16px; border-radius:20px; color:#475569; margin:5px; display:inline-block;">✓ 預算執行度</span>
                <span style="background:#e2e8f0; padding:8px 16px; border-radius:20px; color:#475569; margin:5px; display:inline-block;">✓ WOW 週成長</span>
                <span style="background:#e2e8f0; padding:8px 16px; border-radius:20px; color:#475569; margin:5px; display:inline-block;">✓ 渠道深度分析</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
