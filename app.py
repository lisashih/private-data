import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面配置與精細 UI 雕刻 (Pixel Perfect) ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告投放儀表板", page_icon="📊")

# 注入 CSS：完全還原截圖中的現代化 BI 介面與配色
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        background-color: #f8fafc;
    }

    /* 頂部 Tab 導覽列還原 (與截圖元件一模一樣) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #ffffff;
        padding: 10px 20px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        background-color: #ffffff;
        padding: 0 30px;
        font-weight: 600;
        color: #64748b;
        transition: all 0.2s ease;
    }

    /* 選中狀態：與渠道色彩連動 */
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border-color: #2563eb !important;
        box-shadow: 0 8px 15px -3px rgba(37, 99, 235, 0.3);
    }

    /* 指標卡片設計還原 (Metrics Cards with Dynamic Left Border) */
    [data-testid="stMetric"] {
        background: white;
        padding: 24px !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04) !important;
        border: 1px solid #f1f5f9 !important;
        border-left: 6px solid #2563eb !important; /* 預設藍色 */
    }
    
    /* 不同渠道頁面的卡片邊框色雕刻 */
    .asa-theme [data-testid="stMetric"] { border-left-color: #8b5cf6 !important; }
    .gkw-theme [data-testid="stMetric"] { border-left-color: #2563eb !important; }
    .pmax-theme [data-testid="stMetric"] { border-left-color: #10b981 !important; }
    
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: #1e293b !important;
        font-size: 1.8rem !important;
    }

    /* 進度條樣式優化 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        border-radius: 10px;
    }

    /* 側邊欄與表格微調 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #f1f5f9;
    }
    .dataframe {
        font-size: 13px !important;
        border-radius: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：控制中心 ---
with st.sidebar:
    st.markdown("<h2 style='color:#1e293b;'>⚙️ BI 控制中心</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 上傳數據 (廣告raw-2.xlsx)", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 月度預算指標")
    val_asa = st.number_input("ASA 目標", value=150000, step=10000)
    val_gkw = st.number_input("Google KW 目標", value=500000, step=10000)
    val_pmax = st.number_input("Google Pmax 目標", value=200000, step=10000)
    
    st.divider()
    st.subheader("📅 對比區間 (WOW)")
    c_s = st.date_input("本週起", datetime(2026, 4, 13))
    c_e = st.date_input("本週迄", datetime(2026, 4, 19))
    p_s = st.date_input("上週起", datetime(2026, 4, 6))
    p_e = st.date_input("上週迄", datetime(2026, 4, 12))

# --- 3. 數據處理引擎 ---
@st.cache_data
def load_and_clean_data(file):
    if file is None: return None
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names
    
    all_data = []
    configs = [
        {'id': 'ASA', 'tag': 'ASA', 'cost_col': '花費（台幣）', 'color': '#8b5cf6'},
        {'id': 'Google KW', 'tag': 'KW', 'cost_col': '花費', 'color': '#2563eb'},
        {'id': 'Google Pmax', 'tag': 'PMAX', 'cost_col': '花費', 'color': '#10b981'}
    ]
    
    for cfg in configs:
        sheet_name = next((s for s in sheets if cfg['tag'].upper() in s.upper()), None)
        if sheet_name:
            df = pd.read_excel(file, sheet_name=sheet_name)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
            
            df['Channel'] = cfg['id']
            df['Metric_Cost'] = df[cfg['cost_col']] if cfg['cost_col'] in df.columns else 0
            df['Metric_Conv'] = df['進件數'] if '進件數' in df.columns else 0
            df['Metric_Click'] = df['點擊'] if '點擊' in df.columns else 0
            df['Metric_Impr'] = df['曝光'] if '曝光' in df.columns else 0
            
            if '廣告關鍵字' not in df.columns: df['廣告關鍵字'] = '-'
            if '廣告活動' not in df.columns: df['廣告活動'] = '-'
            
            all_data.append(df)
            
    return pd.concat(all_data, ignore_index=True) if all_data else None

# --- 4. BI 元件渲染 (與截圖一模一樣) ---
if uploaded_file:
    df_raw = load_and_clean_data(uploaded_file)
    
    if df_raw is not None:
        tab1, tab2, tab3, tab4 = st.tabs(["🏠 總覽數據", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- Tab 1: 總覽 ---
        with tab1:
            st.markdown("<h2 style='color:#1e293b;'>全渠道投放執行度</h2>", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            budgets = [("ASA", val_asa, c1, "#8b5cf6"), ("Google KW", val_gkw, c2, "#2563eb"), ("Google Pmax", val_pmax, c3, "#10b981")]
            
            for name, target, col, color in budgets:
                actual = df_raw[df_raw['Channel'] == name]['Metric_Cost'].sum()
                percent = min(actual / target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"<b style='color:#475569;'>{name}</b>", unsafe_allow_html=True)
                    st.progress(percent)
                    st.markdown(f"<span style='color:#64748b; font-size:13px;'>已花費: ${actual:,.0f} / 目標: ${target:,.0f} ({percent:.1%})</span>", unsafe_allow_html=True)

            st.divider()
            st.subheader("📈 每日投放金額走勢")
            fig = go.Figure()
            for name, target, col, color in budgets:
                daily = df_raw[df_raw['Channel'] == name].groupby('Date')['Metric_Cost'].sum().reset_index()
                fig.add_trace(go.Scatter(x=daily['Date'], y=daily['Metric_Cost'], name=name, line=dict(color=color, width=4, shape='spline')))
            
            fig.update_layout(template="simple_white", hovermode="x unified", height=420, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # --- Tab 2, 3, 4: 渠道詳情 (深度還原) ---
        def render_channel_page(cid, title, color, theme_class):
            # 透過 div wrapper 套用主題 class
            st.markdown(f"<div class='{theme_class}'>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='color:{color};'>{title}</h2>", unsafe_allow_html=True)
            
            curr = df_raw[(df_raw['Date'] >= pd.Timestamp(c_s)) & (df_raw['Date'] <= pd.Timestamp(c_e)) & (df_raw['Channel'] == cid)]
            prev = df_raw[(df_raw['Date'] >= pd.Timestamp(p_s)) & (df_raw['Date'] <= pd.Timestamp(p_e)) & (df_raw['Channel'] == cid)]
            
            c_vals = {'cost': curr['Metric_Cost'].sum(), 'conv': curr['Metric_Conv'].sum(), 'clk': curr['Metric_Click'].sum()}
            p_vals = {'cost': prev['Metric_Cost'].sum(), 'conv': prev['Metric_Conv'].sum(), 'clk': prev['Metric_Click'].sum()}
            
            def get_delta(c, p): return f"{(c-p)/p:+.1%}" if p > 0 else "N/A"

            # 四格圖卡與邊框色彩
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("本週進件數", f"{c_vals['conv']:,.0f}", get_delta(c_vals['conv'], p_vals['conv']))
            
            cur_cpa = c_vals['cost']/c_vals['conv'] if c_vals['conv'] > 0 else 0
            pre_cpa = p_vals['cost']/p_vals['conv'] if p_vals['conv'] > 0 else 0
            k2.metric("CPA (進件成本)", f"${cur_cpa:,.0f}", get_delta(cur_cpa, pre_cpa), delta_color="inverse")
            
            k3.metric("本週總花費", f"${c_vals['cost']:,.0f}", get_delta(c_vals['cost'], p_vals['cost']), delta_color="inverse")
            
            cvr = c_vals['conv']/c_vals['clk'] if c_vals['clk'] > 0 else 0
            k4.metric("轉化率 (CVR)", f"{cvr:.2%}")

            st.divider()
            st.write("📋 廣告數據明細清單")
            table_data = curr.groupby(['廣告活動', '廣告關鍵字']).agg({
                'Metric_Cost': 'sum', 'Metric_Conv': 'sum', 'Metric_Click': 'sum', 'Metric_Impr': 'sum'
            }).reset_index().rename(columns={'Metric_Cost': '花費', 'Metric_Conv': '進件', 'Metric_Click': '點擊', 'Metric_Impr': '曝光'}).sort_values('花費', ascending=False)
            st.dataframe(table_data, use_container_width=True, height=450)
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2: render_channel_page("ASA", "ASA 深度分析", "#8b5cf6", "asa-theme")
        with tab3: render_channel_page("Google KW", "Google KW 成效監控", "#2563eb", "gkw-theme")
        with tab4: render_channel_page("Google Pmax", "Pmax 投放成效", "#10b981", "pmax-theme")

else:
    st.markdown("""
        <div style="text-align: center; padding: 120px 20px; background: white; border-radius: 24px; border: 2px dashed #e2e8f0; margin-top: 40px;">
            <h1 style="color: #1e293b; font-size: 2.5rem;">廣告投放監控系統</h1>
            <p style="color: #64748b; font-size: 1.1rem;">請上傳 Excel 檔案以呈現全渠道 BI 儀表板</p>
            <div style="margin-top: 40px;">
                <span style="background: #f1f5f9; padding: 10px 20px; border-radius: 12px; color: #475569; font-weight: 500;">✓ 自動分類渠道</span>
                <span style="background: #f1f5f9; padding: 10px 20px; border-radius: 12px; color: #475569; font-weight: 500; margin-left: 10px;">✓ 即時預算監控</span>
                <span style="background: #f1f5f9; padding: 10px 20px; border-radius: 12px; color: #475569; font-weight: 500; margin-left: 10px;">✓ WOW 週對比</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
