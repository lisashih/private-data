import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面配置與高級 UI 雕刻 ---
st.set_page_config(layout="wide", page_title="Pocket 廣告監控系統", page_icon="📈")

# 注入 CSS 以還原截圖中的 Google Sans 字體與高級卡片感
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; background-color: #f0f2f5; }
    
    /* 分頁標籤樣式 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #ffffff; border-radius: 8px 8px 0px 0px;
        padding: 0px 30px; font-weight: 500; border: 1px solid #e5e7eb;
    }
    .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }
    
    /* 卡片設計 */
    .metric-card {
        background: white; padding: 24px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 6px solid #2563eb; margin-bottom: 20px;
    }
    .asa-card { border-left-color: #8b5cf6; }
    .gkw-card { border-left-color: #2563eb; }
    .pmax-card { border-left-color: #10b981; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：控制中心 ---
with st.sidebar:
    st.title("🎛️ 系統控制")
    uploaded_file = st.file_uploader("請上傳 Pocket 廣告 Raw Data", type=["xlsx"])
    
    st.divider()
    st.subheader("📌 預算變更")
    # 預設值參考截圖設定
    b_asa = st.number_input("ASA 月預算", value=150000, step=10000)
    b_gkw = st.number_input("Google KW 月預算", value=500000, step=10000)
    b_pmax = st.number_input("Google Pmax 月預算", value=200000, step=10000)
    
    st.divider()
    st.subheader("📅 WOW 比對日期")
    c_s = st.date_input("本週開始", datetime(2026, 4, 13))
    c_e = st.date_input("本週結束", datetime(2026, 4, 19))
    p_s = st.date_input("上週開始", datetime(2026, 4, 6))
    p_e = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 3. 數據核心運算與模擬測試邏輯 ---
def process_pocket_data(file):
    xls = pd.ExcelFile(file)
    combined = []
    
    # 標準化映射
    map_cfg = {
        'ASA': {'sheet': 'ASA', 'cost': '花費（台幣）', 'color': '#8b5cf6'},
        'Google KW': {'sheet': 'Google KW', 'cost': '花費', 'color': '#2563eb'},
        'Google Pmax': {'sheet': 'Google Pmax', 'cost': '花費', 'color': '#10b981'}
    }
    
    for ch, cfg in map_cfg.items():
        s_name = next((s for s in xls.sheet_names if cfg['sheet'].upper() in s.upper()), None)
        if s_name:
            df = pd.read_excel(file, sheet_name=s_name)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'])
            df['Channel'] = ch
            df['Cost'] = df[cfg['cost']] if cfg['cost'] in df.columns else 0
            df['Conv'] = df['進件數'] if '進件數' in df.columns else 0
            df['Clicks'] = df['點擊'] if '點擊' in df.columns else 0
            df['Impr'] = df['曝光'] if '曝光' in df.columns else 0
            if '廣告關鍵字' not in df.columns: df['廣告關鍵字'] = '-'
            combined.append(df)
            
    return pd.concat(combined, ignore_index=True) if combined else None

# --- 4. 渲染各個分頁 (與圖片一模一樣) ---
if uploaded_file:
    df = process_pocket_data(uploaded_file)
    
    if df is not None:
        # 分頁導覽 (完全對應四張圖片)
        tab_total, tab_asa, tab_gkw, tab_pmax = st.tabs(["🏠 總覽數據", "🟣 ASA 詳細分析", "🔵 Google KW 分析", "🟢 Pmax 成效監控"])
        
        # --- 頁面 1: 總覽 (還原第一張截圖) ---
        with tab_total:
            st.title("Pocket 廣告投放總覽")
            col1, col2, col3 = st.columns(3)
            budgets = [("ASA", b_asa, "#8b5cf6", col1), ("Google KW", b_gkw, "#2563eb", col2), ("Google Pmax", b_pmax, "#10b981", col3)]
            
            for ch, target, color, col in budgets:
                spent = df[df['Channel'] == ch]['Cost'].sum()
                prog = min(spent/target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"**{ch} 預算執行度**")
                    st.progress(prog)
                    st.write(f"已花費: ${spent:,.0f} / 目標: ${target:,.0f} ({prog:.1%})")
            
            st.divider()
            st.subheader("📊 每日花費趨勢")
            fig_total = go.Figure()
            for ch, _, color, _ in budgets:
                d_trend = df[df['Channel'] == ch].groupby('Date')['Cost'].sum().reset_index()
                fig_total.add_trace(go.Scatter(x=d_trend['Date'], y=d_trend['Cost'], name=ch, line=dict(color=color, width=3)))
            st.plotly_chart(fig_total, use_container_width=True)

        # --- 頁面 2, 3, 4: 渠道詳細 (還原 ASA/KW/Pmax 截圖) ---
        def render_detail_page(channel_name, theme_color):
            st.subheader(f"🔍 {channel_name} 指標深度分析")
            
            c_mask = (df['Date'] >= pd.Timestamp(c_s)) & (df['Date'] <= pd.Timestamp(c_e)) & (df['Channel'] == channel_name)
            p_mask = (df['Date'] >= pd.Timestamp(p_s)) & (df['Date'] <= pd.Timestamp(p_e)) & (df['Channel'] == channel_name)
            
            curr_data, prev_data = df[c_mask], df[p_mask]
            
            # 核心指標計算
            def calc(d):
                return {'cost': d['Cost'].sum(), 'conv': d['Conv'].sum(), 'clk': d['Clicks'].sum()}
            
            c_met, p_met = calc(curr_data), calc(prev_data)
            c_cpa = c_met['cost']/c_met['conv'] if c_met['conv'] > 0 else 0
            p_cpa = p_met['cost']/p_met['conv'] if p_met['conv'] > 0 else 0
            
            # 還原圖片中的四個 Metric 卡片
            m1, m2, m3, m4 = st.columns(4)
            def delta(c, p): return f"{(c-p)/p:+.1%}" if p > 0 else "N/A"
            
            m1.metric("進件數", f"{c_met['conv']:,.0f}", delta(c_met['conv'], p_met['conv']))
            m2.metric("CPA (成本)", f"${c_cpa:.0f}", delta(c_cpa, p_cpa), delta_color="inverse")
            m3.metric("本週總花費", f"${c_met['cost']:,.0f}", delta(c_met['cost'], p_met['cost']), delta_color="inverse")
            m4.metric("點擊轉化率", f"{c_met['conv']/c_met['clk']:.2%}" if c_met['clk']>0 else "0.00%")
            
            st.divider()
            st.write("📋 關鍵字/廣告活動成效清單 (本週)")
            # 還原截圖下方的表格數據
            table_df = curr_data.groupby(['廣告活動', '廣告關鍵字']).agg({
                'Cost': 'sum', 'Conv': 'sum', 'Clicks': 'sum', 'Impr': 'sum'
            }).reset_index().sort_values('Cost', ascending=False)
            st.dataframe(table_df, use_container_width=True)

        with tab_asa: render_detail_page("ASA", "#8b5cf6")
        with tab_gkw: render_detail_page("Google KW", "#2563eb")
        with tab_pmax: render_detail_page("Google Pmax", "#10b981")

else:
    st.info("👋 您好！請上傳廣告 Raw Data 以呈現完全還原截圖的 Pocket 廣告儀表板。")
    # 測試模擬說明
    with st.expander("🛠️ 測試模擬說明"):
        st.write("1. 程式會自動過濾 META 分頁，只抓取 ASA/KW/Pmax。")
        st.write("2. 已自動適應 '花費（台幣）' 與 '花費' 兩種欄位名稱。")
        st.write("3. 分頁功能採用 st.tabs 實現，保證與圖片頁面切換邏輯一致。")
