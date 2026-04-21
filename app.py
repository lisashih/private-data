import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面配置與精雕細琢的 CSS 注入 ---
st.set_page_config(layout="wide", page_title="Pocket 廣告投放儀表板")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        background-color: #f4f7fa;
    }

    /* 頂部導覽 Tab 樣式調整 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #ffffff;
        padding: 8px 16px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 8px;
        border: 1px solid #edf2f7;
        background-color: #f8fafc;
        padding: 0 24px;
        font-weight: 500;
        transition: all 0.3s;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
        border: none !important;
    }

    /* 卡片通用樣式 */
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-top: 5px solid #2563eb;
        margin-bottom: 20px;
    }
    
    .asa-header { border-top-color: #8b5cf6 !important; }
    .gkw-header { border-top-color: #2563eb !important; }
    .pmax-header { border-top-color: #10b981 !important; }
    
    /* 進度條自定義 */
    .stProgress > div > div > div > div {
        background-color: #2563eb;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：控制與數據注入 ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dashboard.png", width=60)
    st.title("系統控制台")
    
    uploaded_file = st.file_uploader("📂 上傳廣告資料 (Excel)", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 預算目標變更")
    target_asa = st.number_input("ASA 月預算", value=150000, step=10000)
    target_gkw = st.number_input("Google KW 月預算", value=500000, step=10000)
    target_pmax = st.number_input("Google Pmax 月預算", value=200000, step=10000)
    
    st.divider()
    st.subheader("📅 WOW 比較區間")
    # 預設為截圖中的日期區間
    curr_start = st.date_input("本週開始", datetime(2026, 4, 13))
    curr_end = st.date_input("本週結束", datetime(2026, 4, 19))
    prev_start = st.date_input("上週開始", datetime(2026, 4, 6))
    prev_end = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 3. 數據雕刻邏輯：自動適應與過濾 ---
@st.cache_data
def get_clean_data(file):
    if file is None: return None
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names
    combined_list = []
    
    # 渠道配置
    configs = [
        {'key': 'ASA', 'cost_col': '花費（台幣）', 'label': 'ASA'},
        {'key': 'KW', 'cost_col': '花費', 'label': 'Google KW'},
        {'key': 'PMAX', 'cost_col': '花費', 'label': 'Google Pmax'}
    ]
    
    for cfg in configs:
        target_sheet = next((s for s in sheets if cfg['key'].upper() in s.upper()), None)
        if target_sheet:
            df = pd.read_excel(file, sheet_name=target_sheet)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'])
            df['Channel'] = cfg['label']
            df['Standard_Cost'] = df[cfg['cost_col']] if cfg['cost_col'] in df.columns else 0
            df['Standard_Conv'] = df['進件數'] if '進件數' in df.columns else 0
            df['Standard_Clicks'] = df['點擊'] if '點擊' in df.columns else 0
            df['Standard_Impr'] = df['曝光'] if '曝光' in df.columns else 0
            if '廣告關鍵字' not in df.columns: df['廣告關鍵字'] = '-'
            combined_list.append(df)
            
    return pd.concat(combined_list, ignore_index=True) if combined_list else None

# --- 4. 畫面渲染 (完全對照截圖佈局) ---
if uploaded_file:
    full_df = get_clean_data(uploaded_file)
    
    if full_df is not None:
        # 分頁導覽
        tab_total, tab_asa, tab_gkw, tab_pmax = st.tabs([
            "🏠 總覽數據", "🟣 ASA 詳細分析", "🔵 Google KW 分析", "🟢 Pmax 成效監控"
        ])
        
        # --- 頁面 1: 總覽數據 (還原第一張截圖) ---
        with tab_total:
            st.title("Pocket 廣告投放總覽")
            
            # 預算執行率卡片列
            cols = st.columns(3)
            budgets = [("ASA", target_asa, "#8b5cf6"), ("Google KW", target_gkw, "#2563eb"), ("Google Pmax", target_pmax, "#10b981")]
            
            for i, (name, target, color) in enumerate(budgets):
                spent = full_df[full_df['Channel'] == name]['Standard_Cost'].sum()
                ratio = min(spent / target, 1.0) if target > 0 else 0
                with cols[i]:
                    st.markdown(f"### {name}")
                    st.progress(ratio)
                    st.write(f"執行率: **{ratio:.1%}**")
                    st.caption(f"已花費: ${spent:,.0f} / 目標: ${target:,.0f}")

            st.divider()
            
            # 每日趨勢圖
            st.subheader("📊 每日投放趨勢")
            trend_fig = go.Figure()
            for name, target, color in budgets:
                d = full_df[full_df['Channel'] == name].groupby('Date')['Standard_Cost'].sum().reset_index()
                trend_fig.add_trace(go.Scatter(x=d['Date'], y=d['Standard_Cost'], name=name, line=dict(color=color, width=3)))
            trend_fig.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(trend_fig, use_container_width=True)

        # --- 頁面 2/3/4: 渠道詳細分析 ---
        def render_channel(channel_name, color):
            st.title(f"{channel_name} 成效深度分析")
            
            # 數據切片
            curr_df = full_df[(full_df['Date'] >= pd.Timestamp(curr_start)) & (full_df['Date'] <= pd.Timestamp(curr_end)) & (full_df['Channel'] == channel_name)]
            prev_df = full_df[(full_df['Date'] >= pd.Timestamp(prev_start)) & (full_df['Date'] <= pd.Timestamp(prev_end)) & (full_df['Channel'] == channel_name)]
            
            # 指標計算
            def get_sum(df_in):
                return {'cost': df_in['Standard_Cost'].sum(), 'conv': df_in['Standard_Conv'].sum(), 'clk': df_in['Standard_Clicks'].sum()}
            
            c = get_sum(curr_df)
            p = get_sum(prev_df)
            
            # 成長率計算
            def delta(curr, prev):
                if prev == 0: return "N/A"
                return f"{(curr - prev) / prev:+.1%}"

            # 核心卡片區域 (還原截圖的 4 Metric 卡片)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("進件數 (Conv)", f"{c['conv']:,.0f}", delta(c['conv'], p['conv']))
            
            c_cpa = c['cost']/c['conv'] if c['conv'] > 0 else 0
            p_cpa = p['cost']/p['conv'] if p['conv'] > 0 else 0
            m2.metric("CPA (進件成本)", f"${c_cpa:.0f}", delta(c_cpa, p_cpa), delta_color="inverse")
            
            m3.metric("本週花費", f"${c['cost']:,.0f}", delta(c['cost'], p['cost']), delta_color="inverse")
            
            cvr = c['conv']/c['clk'] if c['clk'] > 0 else 0
            m4.metric("點擊轉化率 (CVR)", f"{cvr:.2%}")

            st.divider()
            
            # 詳細清單 (還原截圖下方的表格)
            st.subheader("📋 詳細廣告數據清單")
            table = curr_df.groupby(['廣告活動', '廣告關鍵字']).agg({
                'Standard_Cost': 'sum',
                'Standard_Conv': 'sum',
                'Standard_Clicks': 'sum',
                'Standard_Impr': 'sum'
            }).reset_index().rename(columns={
                'Standard_Cost': '花費', 'Standard_Conv': '進件', 'Standard_Clicks': '點擊', 'Standard_Impr': '曝光'
            }).sort_values('花費', ascending=False)
            
            st.dataframe(table, use_container_width=True, height=400)

        with tab_asa: render_channel("ASA", "#8b5cf6")
        with tab_gkw: render_channel("Google KW", "#2563eb")
        with tab_pmax: render_channel("Google Pmax", "#10b981")

else:
    # 啟動引導畫面
    st.markdown("""
        <div style="text-align: center; padding: 100px;">
            <img src="https://img.icons8.com/clouds/200/analytics.png" width="150">
            <h2 style="color: #4a5568;">Pocket 廣告數據系統</h2>
            <p style="color: #718096;">請於左側側邊欄上傳廣告 Excel 檔案 (raw-2.xlsx) 以解鎖完整數據分析。</p>
        </div>
    """, unsafe_allow_html=True)
