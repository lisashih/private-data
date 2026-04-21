import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面外觀還原 (CSS) ---
st.set_page_config(layout="wide", page_title="廣告投放整合儀表板")

st.markdown("""
    <style>
    .main { background-color: #f4f6f9; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }
    
    /* 模仿截圖中的數據卡片 */
    .metric-box {
        background: white; padding: 1.5rem; border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-top: 5px solid #2563eb;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄控制與預算變更 ---
with st.sidebar:
    st.header("📊 系統控制")
    uploaded_file = st.file_uploader("上傳原始資料 Excel", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 預算管理")
    b_asa = st.number_input("ASA 月預算", value=150000)
    b_gkw = st.number_input("Google KW 月預算", value=500000)
    b_pmax = st.number_input("Google Pmax 月預算", value=200000)
    
    st.divider()
    st.subheader("📅 WOW 比較區間")
    c_s = st.date_input("本週起", datetime(2026, 4, 13))
    c_e = st.date_input("本週迄", datetime(2026, 4, 19))
    p_s = st.date_input("上週起", datetime(2026, 4, 6))
    p_e = st.date_input("上週迄", datetime(2026, 4, 12))

# --- 3. 數據自動適應處理 ---
def load_and_standardize(file):
    try:
        xls = pd.ExcelFile(file)
        sheets = xls.sheet_names
        all_data = []
        
        # 欄位映射邏輯
        mapping = {
            'ASA': {'sheet': 'ASA', 'cost': '花費（台幣）', 'color': '#8b5cf6'},
            'Google KW': {'sheet': 'Google KW', 'cost': '花費', 'color': '#2563eb'},
            'Google Pmax': {'sheet': 'Google Pmax', 'cost': '花費', 'color': '#10b981'}
        }
        
        for ch, conf in mapping.items():
            s_name = next((s for s in sheets if conf['sheet'].upper() in s.upper()), None)
            if s_name:
                df = pd.read_excel(file, sheet_name=s_name)
                df.columns = df.columns.str.strip()
                df['Date'] = pd.to_datetime(df['Date'])
                df['Channel'] = ch
                df['Cost'] = df[conf['cost']] if conf['cost'] in df.columns else 0
                df['Conv'] = df['進件數'] if '進件數' in df.columns else 0
                df['Clicks'] = df['點擊'] if '點擊' in df.columns else 0
                if '廣告關鍵字' not in df.columns: df['廣告關鍵字'] = 'Pmax'
                all_data.append(df)
        
        return pd.concat(all_data, ignore_index=True) if all_data else None
    except Exception as e:
        st.error(f"讀取錯誤: {e}")
        return None

# --- 4. 儀表板主功能區域 ---
if uploaded_file:
    data = load_and_standardize(uploaded_file)
    
    if data is not None:
        # 分頁導覽功能 (對應你的四張截圖頁面)
        tab_main, tab_asa, tab_kw, tab_pmax = st.tabs(["🏠 總覽 (Overview)", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 分析"])
        
        # --- 頁面 1: 總覽 (對應 第一張圖) ---
        with tab_main:
            st.title("廣告投放總覽")
            
            # 預算進度條
            c1, c2, c3 = st.columns(3)
            for i, (name, b_val, color) in enumerate([("ASA", b_asa, "#8b5cf6"), ("Google KW", b_gkw, "#2563eb"), ("Google Pmax", b_pmax, "#10b981")]):
                spent = data[data['Channel'] == name]['Cost'].sum()
                pct = min(spent/b_val, 1.0) if b_val > 0 else 0
                with [c1, c2, c3][i]:
                    st.markdown(f"**{name} 預算進度**")
                    st.progress(pct)
                    st.caption(f"${spent:,.0f} / ${b_val:,.0f} ({pct:.1%})")
            
            st.divider()
            st.subheader("📈 WOW 週成長趨勢")
            # 每日花費趨勢圖
            fig = go.Figure()
            for name, color in [("ASA", "#8b5cf6"), ("Google KW", "#2563eb"), ("Google Pmax", "#10b981")]:
                d = data[data['Channel'] == name].groupby('Date')['Cost'].sum().reset_index()
                fig.add_trace(go.Scatter(x=d['Date'], y=d['Cost'], name=name, line=dict(color=color, width=3)))
            st.plotly_chart(fig, use_container_width=True)

        # --- 頁面 2/3/4: 各渠道詳細數據 (對應 ASA/KW/Pmax 截圖) ---
        def render_channel_page(ch_name, color):
            st.subheader(f"{ch_name} 詳細指標 (WOW 對比)")
            
            c_mask = (data['Date'] >= pd.Timestamp(c_s)) & (data['Date'] <= pd.Timestamp(c_e)) & (data['Channel'] == ch_name)
            p_mask = (data['Date'] >= pd.Timestamp(p_s)) & (data['Date'] <= pd.Timestamp(p_e)) & (data['Channel'] == ch_name)
            
            curr, prev = data[c_mask], data[p_mask]
            
            c1, c2, c3, c4 = st.columns(4)
            # 計算數據
            c_sum = {'cost': curr['Cost'].sum(), 'conv': curr['Conv'].sum(), 'clk': curr['Clicks'].sum()}
            p_sum = {'cost': prev['Cost'].sum(), 'conv': prev['Conv'].sum(), 'clk': prev['Clicks'].sum()}
            
            def delta_pct(c, p):
                return f"{(c-p)/p:+.1%}" if p > 0 else "N/A"

            c1.metric("進件數", f"{c_sum['conv']:,.0f}", delta_pct(c_sum['conv'], p_sum['conv']))
            cpa = c_sum['cost']/c_sum['conv'] if c_sum['conv'] > 0 else 0
            p_cpa = p_sum['cost']/p_sum['conv'] if p_sum['conv'] > 0 else 0
            c2.metric("CPA (進件成本)", f"${cpa:.0f}", delta_pct(cpa, p_cpa), delta_color="inverse")
            c3.metric("本週花費", f"${c_sum['cost']:,.0f}", delta_pct(c_sum['cost'], p_sum['cost']), delta_color="inverse")
            cvr = c_sum['conv']/c_sum['clk'] if c_sum['clk'] > 0 else 0
            c4.metric("點擊轉化率", f"{cvr:.2%}")

            # 關鍵字清單 (截圖下方的表格)
            st.markdown("---")
            st.write("📋 本週關鍵字表現詳情")
            st.dataframe(curr[['Date', '廣告活動', '廣告關鍵字', 'Cost', '進件數', 'Clicks']].sort_values('Cost', ascending=False), use_container_width=True)

        with tab_asa: render_channel_page("ASA", "#8b5cf6")
        with tab_kw: render_channel_page("Google KW", "#2563eb")
        with tab_pmax: render_channel_page("Google Pmax", "#10b981")

else:
    st.info("請於左側上傳 Excel 檔案以呈現四張頁面的數據分析。")
