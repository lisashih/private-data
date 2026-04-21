import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 頁面還原設定 ---
st.set_page_config(layout="wide", page_title="廣告投放監控儀表板")

# 自定義 CSS：還原圖片中的圓角、陰影與渠道專屬顏色
st.markdown("""
    <style>
    :root {
        --asa-color: #8b5cf6;
        --gkw-color: #2563eb;
        --pmax-color: #10b981;
    }
    .main { background-color: #f8fafc; }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-top: 4px solid #e2e8f0;
    }
    .asa-border { border-top-color: var(--asa-color); }
    .gkw-border { border-top-color: var(--gkw-color); }
    .pmax-border { border-top-color: var(--pmax-color); }
    .delta-positive { color: #10b981; font-size: 0.85em; }
    .delta-negative { color: #ef4444; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# --- 側邊欄：檔案與預算設定 ---
with st.sidebar:
    st.header("📂 數據中心")
    uploaded_file = st.file_uploader("請上傳廣告 Raw Data (Excel)", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 月預算變更")
    budget_asa = st.number_input("ASA 預算", value=150000)
    budget_gkw = st.number_input("Google KW 預算", value=500000)
    budget_pmax = st.number_input("Google Pmax 預算", value=200000)
    
    st.divider()
    st.subheader("📅 WOW 比對區間")
    # 預設為你圖片中的日期
    c_s = st.date_input("本週開始", datetime(2026, 4, 13))
    c_e = st.date_input("本週結束", datetime(2026, 4, 19))
    p_s = st.date_input("上週開始", datetime(2026, 4, 6))
    p_e = st.date_input("上週結束", datetime(2026, 4, 12))

# --- 數據處理核心 ---
def load_data(file):
    sheets = pd.read_excel(file, sheet_name=None)
    combined = []
    
    # 1. ASA
    if 'ASA' in sheets:
        df = sheets['ASA']
        df['Date'] = pd.to_datetime(df['Date'])
        df['Channel'] = 'ASA'
        df['Cost'] = df['花費（台幣）']
        combined.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊']])
        
    # 2. Google KW
    if 'Google KW' in sheets:
        df = sheets['Google KW']
        df['Date'] = pd.to_datetime(df['Date'])
        df['Channel'] = 'Google KW'
        df['Cost'] = df['花費']
        combined.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊']])

    # 3. Google Pmax
    if 'Google Pmax' in sheets:
        df = sheets['Google Pmax']
        df['Date'] = pd.to_datetime(df['Date'])
        df['Channel'] = 'Google Pmax'
        df['Cost'] = df['花費']
        df['廣告關鍵字'] = 'Pmax'
        combined.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊']])
        
    return pd.concat(combined)

if uploaded_file:
    full_df = load_data(uploaded_file)
    
    # --- 畫面頂部：預算進度條 ---
    st.title("📊 廣告投放即時監控儀表板")
    
    col1, col2, col3 = st.columns(3)
    metrics_list = [
        ("ASA", budget_asa, "#8b5cf6", col1),
        ("Google KW", budget_gkw, "#2563eb", col2),
        ("Google Pmax", budget_pmax, "#10b981", col3)
    ]
    
    for ch_name, b_val, color, column in metrics_list:
        spent = full_df[full_df['Channel'] == ch_name]['Cost'].sum()
        ratio = min(spent / b_val, 1.0)
        with column:
            st.markdown(f"**{ch_name} 執行進度**")
            st.progress(ratio)
            st.write(f"已花費: ${spent:,.0f} / 目標: ${b_val:,.0f} ({ratio:.1%})")

    # --- 中間層：WOW 數據卡片 (核心還原) ---
    st.divider()
    st.header(f"📈 週成長分析 (WOW)")
    st.caption(f"對比區間：{c_s}~{c_e} vs {p_s}~{p_e}")

    def get_stats(data, start, end, channel):
        mask = (data['Date'] >= pd.Timestamp(start)) & (data['Date'] <= pd.Timestamp(end)) & (data['Channel'] == channel)
        sub = data[mask]
        return {
            'cost': sub['Cost'].sum(),
            'conv': sub['進件數'].sum(),
            'clicks': sub['點擊'].sum()
        }

    for ch_name, _, color, _ in metrics_list:
        curr = get_stats(full_df, c_s, c_e, ch_name)
        prev = get_stats(full_df, p_s, p_e, ch_name)
        
        # 計算指標
        c_cpa = curr['cost'] / curr['conv'] if curr['conv'] > 0 else 0
        p_cpa = prev['cost'] / prev['conv'] if prev['conv'] > 0 else 0
        c_cvr = curr['conv'] / curr['clicks'] if curr['clicks'] > 0 else 0
        
        def get_delta(c, p, inv=False):
            if p == 0: return "N/A"
            d = (c - p) / p
            return f"{d:+.1%}"

        # 顯示渠道標頭與卡片
        st.markdown(f"#### <span style='color:{color}'>●</span> {ch_name}", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("進件數", f"{curr['conv']:,.0f}", get_delta(curr['conv'], prev['conv']))
        m2.metric("CPA (進件成本)", f"${c_cpa:,.0f}", get_delta(c_cpa, p_cpa), delta_color="inverse")
        m3.metric("轉化率 (CVR)", f"{c_cvr:.2%}")
        m4.metric("本週花費", f"${curr['cost']:,.0f}", get_delta(curr['cost'], prev['cost']), delta_color="inverse")

    # --- 下層：低效關鍵字診斷 ---
    st.divider()
    st.header("🔍 低效關鍵字與無效詞診斷")
    
    # 篩選本週：花費 > 500 且 0 轉化
    bad_df = full_df[
        (full_df['Date'] >= pd.Timestamp(c_s)) & 
        (full_df['Date'] <= pd.Timestamp(c_e)) & 
        (full_df['進件數'] == 0) & 
        (full_df['Cost'] > 500)
    ].sort_values('Cost', ascending=False)
    
    if not bad_df.empty:
        st.error("警告：以下關鍵字本週花費過高但無任何進件轉換")
        st.dataframe(bad_df[['Channel', '廣告活動', '廣告關鍵字', 'Cost', '點擊']], use_container_width=True)
    else:
        st.success("本週關鍵字表現健康，無明顯無效花費。")

    # --- 底部：每日趨勢圖 ---
    st.divider()
    daily_df = full_df.groupby(['Date', 'Channel'])['Cost'].sum().reset_index()
    fig = go.Figure()
    for ch_name, _, color, _ in metrics_list:
        ch_data = daily_df[daily_df['Channel'] == ch_name]
        fig.add_trace(go.Scatter(x=ch_data['Date'], y=ch_data['Cost'], name=ch_name, line=dict(color=color, width=3)))
    
    fig.update_layout(title="每日投放花費趨勢", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👋 請上傳廣告 Excel 檔案（Raw Data）以生成儀表板。")
