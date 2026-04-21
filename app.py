import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 頁面風格還原 (CSS) ---
st.set_page_config(layout="wide", page_title="廣告投放儀表板")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Google Sans', sans-serif; background-color: #f5f7fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; }
    .asa-card { border-left-color: #8b5cf6 !important; }
    .gkw-card { border-left-color: #2563eb !important; }
    .pmax-card { border-left-color: #10b981 !important; }
    div[data-testid="stExpander"] { background: white; border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- 側邊欄：功能控制 ---
st.sidebar.header("⚙️ 控制面板")
uploaded_file = st.sidebar.file_uploader("1. 上傳 Raw Data (Excel)", type=["xlsx"])

# 預算變更區
st.sidebar.subheader("💰 預算設定")
budget_asa = st.sidebar.number_input("ASA 月預算", value=150000)
budget_gkw = st.sidebar.number_input("Google KW 月預算", value=500000)
budget_pmax = st.sidebar.number_input("Google Pmax 月預算", value=200000)

# 日期區間設定 (WOW)
st.sidebar.subheader("📅 WOW 區間設定")
c_start = st.sidebar.date_input("本週起", datetime(2026, 4, 13))
c_end = st.sidebar.date_input("本週迄", datetime(2026, 4, 19))
p_start = st.sidebar.date_input("上週起", datetime(2026, 4, 6))
p_end = st.sidebar.date_input("上週迄", datetime(2026, 4, 12))

def process_data(file):
    # 讀取 Sheet 並排除 META
    sheets = pd.read_excel(file, sheet_name=None)
    data_list = []
    
    if 'ASA' in sheets:
        df = sheets['ASA']
        df['Channel'] = 'ASA'
        df['Cost'] = df['花費（台幣）']
        df['Date'] = pd.to_datetime(df['Date'])
        data_list.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊', '曝光']])
        
    if 'Google KW' in sheets:
        df = sheets['Google KW']
        df['Channel'] = 'Google KW'
        df['Cost'] = df['花費']
        df['Date'] = pd.to_datetime(df['Date'])
        data_list.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊', '曝光']])

    if 'Google Pmax' in sheets:
        df = sheets['Google Pmax']
        df['Channel'] = 'Google Pmax'
        df['Cost'] = df['花費']
        df['Date'] = pd.to_datetime(df['Date'])
        df['廣告關鍵字'] = 'Pmax'
        data_list.append(df[['Date', 'Channel', '廣告關鍵字', 'Cost', '進件數', '點擊', '曝光']])
        
    return pd.concat(data_list, ignore_index=True)

if uploaded_file:
    all_df = process_data(uploaded_file)
    
    # 計算各期間數據
    curr_df = all_df[(all_df['Date'] >= pd.Timestamp(c_start)) & (all_df['Date'] <= pd.Timestamp(c_end))]
    prev_df = all_df[(all_df['Date'] >= pd.Timestamp(p_start)) & (all_df['Date'] <= pd.Timestamp(p_end))]
    
    # --- 儀表板頂部：預算進度 (Progress Bar) ---
    st.title("廣告投放監控儀表板")
    
    cols = st.columns(3)
    channels = [("ASA", budget_asa, "#8b5cf6"), ("Google KW", budget_gkw, "#2563eb"), ("Google Pmax", budget_pmax, "#10b981")]
    
    for i, (name, b_val, color) in enumerate(channels):
        spent = all_df[all_df['Channel'] == name]['Cost'].sum()
        pct = min(spent / b_val, 1.0)
        with cols[i]:
            st.markdown(f"**{name} 預算執行率**")
            st.progress(pct)
            st.write(f"已花費: ${spent:,.0f} / 目標: ${b_val:,.0f} ({pct:.1%})")

    # --- 中間層：WOW 核心指標 ---
    st.header("📈 週成效對比 (WOW)")
    
    def get_summary(df_subset):
        return df_subset.groupby('Channel').agg({'Cost':'sum','進件數':'sum','點擊':'sum'}).reset_index()

    c_sum = get_summary(curr_df)
    p_sum = get_summary(prev_df)
    
    for name, _, _ in channels:
        with st.expander(f"查看 {name} 詳細指標", expanded=True):
            m1, m2, m3, m4 = st.columns(4)
            c_val = c_sum[c_sum['Channel']==name].iloc[0] if name in c_sum['Channel'].values else None
            p_val = p_sum[p_sum['Channel']==name].iloc[0] if name in p_sum['Channel'].values else None
            
            if c_val is not None and p_val is not None:
                # 進件數
                m1.metric("進件數", f"{int(c_val['進件數'])}", f"{(c_val['進件數']-p_val['進件數'])/p_val['進件數']:.1%}" if p_val['進件數']>0 else "0%")
                # CPA
                c_cpa = c_val['Cost']/c_val['進件數'] if c_val['進件數']>0 else 0
                p_cpa = p_val['Cost']/p_val['進件數'] if p_val['進件數']>0 else 0
                m2.metric("CPA (進件成本)", f"${c_cpa:.0f}", f"{(c_cpa-p_cpa)/p_cpa:.1%}" if p_cpa>0 else "0%", delta_color="inverse")
                # 轉化率
                c_cvr = c_val['進件數']/c_val['點擊'] if c_val['點擊']>0 else 0
                m3.metric("CVR (轉換率)", f"{c_cvr:.2%}")
                # 花費
                m4.metric("本週花費", f"${c_val['Cost']:,.0f}")

    # --- 下層：關鍵字診斷 (參照模板功能) ---
    st.header("🔍 低效關鍵字診斷 (本週)")
    # 邏輯：花費 > 500 且 0 轉換
    bad_kw = curr_df[(curr_df['進件數'] == 0) & (curr_df['Cost'] > 500)].sort_values('Cost', ascending=False)
    
    if not bad_kw.empty:
        st.error("警告：以下關鍵字本週花費過高且無進件轉換")
        st.dataframe(bad_kw[['Channel', '廣告關鍵字', 'Cost', '點擊']], use_container_width=True)
    else:
        st.success("本週關鍵字表現優良，無明顯浪費花費。")

    # --- 圖表區 ---
    st.header("📊 趨勢分析")
    daily_cost = curr_df.groupby(['Date', 'Channel'])['Cost'].sum().reset_index()
    fig = go.Figure()
    for name, _, color in channels:
        ch_data = daily_cost[daily_cost['Channel'] == name]
        fig.add_trace(go.Scatter(x=ch_data['Date'], y=ch_data['Cost'], name=name, line=dict(color=color, width=3)))
    fig.update_layout(title="本週每日花費趨勢", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("💡 請在側邊欄上傳 Excel 檔案（Raw Data），系統將自動生成與模板一致的儀表板。")
