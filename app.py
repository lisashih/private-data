import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 頁面配置 ---
st.set_page_config(layout="wide", page_title="廣告投放自動化儀表板")

# --- 樣式自定義 ---
st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e6e9ef; }
    .status-bad { color: #ef4444; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. 配置預算 (根據圖片內容設定) ---
# 假設圖片中 Google 總預算為 400,000，ASA 為 100,000 (請依實際圖片數值修改)
CHANNEL_BUDGETS = {
    "Google Search": 475958,
    "Google Pmax": 300000,
    "ASA": 474042
}

# --- 2. 側邊欄：檔案上傳與日期控制 ---
st.sidebar.header("📂 數據上傳與設定")
uploaded_file = st.sidebar.file_uploader("上傳廣告 Raw Data (Excel)", type=["xlsx"])

# 設定分析週區間
st.sidebar.subheader("📅 WOW 週對比設定")
curr_start = st.sidebar.date_input("本週開始", datetime(2026, 4, 13))
curr_end = st.sidebar.date_input("本週結束", datetime(2026, 4, 19))
prev_start = st.sidebar.date_input("上週開始", datetime(2026, 4, 6))
prev_end = st.sidebar.date_input("上週結束", datetime(2026, 4, 12))

def load_data(file):
    # 讀取三個 Sheet
    df_kw = pd.read_excel(file, sheet_name="Google KW")
    df_pmax = pd.read_excel(file, sheet_name="Google Pmax")
    df_asa = pd.read_excel(file, sheet_name="ASA")
    
    # 轉換日期格式
    df_kw['Date'] = pd.to_datetime(df_kw['Date'])
    df_pmax['Date'] = pd.to_datetime(df_pmax['Date'])
    df_asa['Date'] = pd.to_datetime(df_asa['Date'])
    
    # 欄位標準化 (統一計算花費、進件、完開)
    df_kw['Channel'] = 'Google Search'
    df_pmax['Channel'] = 'Google Pmax'
    df_asa['Channel'] = 'ASA'
    # ASA 使用台幣欄位
    df_asa['花費'] = df_asa['花費（台幣）']
    
    # 合併數據 (排除 META)
    common_cols = ['Date', 'Channel', '廣告活動', '廣告關鍵字', '曝光', '點擊', '花費', '進件數', '完開數']
    # Pmax 沒有關鍵字欄位，補空值
    df_pmax['廣告關鍵字'] = 'Pmax_Campaign'
    
    full_df = pd.concat([
        df_kw[common_cols], 
        df_pmax[common_cols], 
        df_asa[common_cols]
    ], ignore_index=True)
    
    return full_df

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- 3. 數據運算邏輯 ---
    def get_period_stats(data, start, end):
        mask = (data['Date'] >= pd.Timestamp(start)) & (data['Date'] <= pd.Timestamp(end))
        subset = data.loc[mask]
        stats = subset.groupby('Channel').agg({
            '花費': 'sum',
            '進件數': 'sum',
            '完開數': 'sum',
            '點擊': 'sum'
        }).reset_index()
        return stats

    curr_stats = get_period_stats(df, curr_start, curr_end)
    prev_stats = get_period_stats(df, prev_start, prev_end)

    # --- 4. 儀表板視覺化 ---
    st.title("🚀 廣告渠道成效自動化儀表板")
    
    # A. 預算進度條
    st.header("📊 預算執行進度 (月度累計)")
    cols = st.columns(len(CHANNEL_BUDGETS))
    for i, (ch, budget) in enumerate(CHANNEL_BUDGETS.items()):
        actual = df[df['Channel'] == ch]['花費'].sum()
        percent = min(actual / budget, 1.0)
        with cols[i]:
            st.metric(ch, f"${actual:,.0f}", f"預算: ${budget:,.0f}")
            st.progress(percent)
            st.caption(f"執行進度: {percent:.1%}")

    # B. WOW 分析
    st.header(f"📈 WOW 週成長分析 ({curr_start} vs {prev_start})")
    wow_df = curr_stats.merge(prev_stats, on='Channel', suffixes=('_curr', '_prev'))
    
    for _, row in wow_df.iterrows():
        expander = st.expander(f"渠道詳情: {row['Channel']}")
        c1, c2, c3, c4 = expander.columns(4)
        
        def delta_str(curr, prev):
            if prev == 0: return "N/A"
            diff = (curr - prev) / prev
            return f"{diff:+.1%}"

        c1.metric("進件數", int(row['進件數_curr']), delta_str(row['進件數_curr'], row['進件數_prev']))
        c2.metric("花費", f"${row['花費_curr']:,.0f}", delta_str(row['花費_curr'], row['花費_prev']), delta_color="inverse")
        
        # CPA 分析
        cpa_curr = row['花費_curr'] / row['進件數_curr'] if row['進件數_curr'] > 0 else 0
        cpa_prev = row['花費_prev'] / row['進件數_prev'] if row['進件數_prev'] > 0 else 0
        c3.metric("進件 CPA", f"${cpa_curr:.0f}", delta_str(cpa_curr, cpa_prev), delta_color="inverse")
        
        # CVR 分析
        cvr_curr = row['進件數_curr'] / row['點擊_curr'] if row['點擊_curr'] > 0 else 0
        c4.metric("轉換率 (CVR)", f"{cvr_curr:.2%}")

    # C. 低效關鍵字分析
    st.header("🔍 關鍵字黑名單 (低效率/無轉換)")
    # 邏輯：在本週區間內，花費大於平均 CPA 且 0 轉換的詞
    waste_mask = (df['Date'] >= pd.Timestamp(curr_start)) & (df['進件數'] == 0) & (df['花費'] > 200) # 200 為門檻可調
    waste_keywords = df[waste_mask].sort_values(by='花費', ascending=False)
    
    if not waste_keywords.empty:
        st.warning("以下關鍵字在本週有顯著花費但無進件：")
        st.dataframe(waste_keywords[['Channel', '廣告活動', '廣告關鍵字', '花費', '點擊']])
    else:
        st.success("暫無顯著低效關鍵字。")

    # D. 渠道轉換成本對比圖
    st.header("📊 各渠道成本結構對比")
    fig = px.bar(curr_stats, x='Channel', y='花費', text_auto='.2s', title="本週各渠道總花費")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👋 請在左側上傳 Excel 檔案以開始分析。")
