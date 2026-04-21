import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面配置與精細 UI 雕刻 (Pixel Perfect) ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告投放儀表板", page_icon="📊")

# 注入 CSS：完全還原截圖與 HTML 中的現代化 BI 介面
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        background-color: #f5f7fa;
    }

    /* 頂部 Tab 導覽列還原 (對應 HTML 樣式) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #ffffff;
        padding: 12px 24px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        margin-bottom: 24px;
        border-bottom: 1px solid #e5e7eb;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
        padding: 0 24px;
        font-weight: 500;
        color: #6b7280;
        transition: all 0.2s;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border-color: #2563eb !important;
    }

    /* 指標卡片設計還原 (Metrics Cards) */
    [data-testid="stMetric"] {
        background: white;
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        border-left: 5px solid #2563eb;
    }
    
    /* 針對不同渠道設定邊框顏色 */
    div[data-testid="stVerticalBlock"] > div:nth-child(1) [data-testid="stMetric"] { border-left-color: #8b5cf6; } /* ASA */
    
    /* 數值樣式 */
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: #111827 !important;
    }

    /* 側邊欄與進度條自定義 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
    }
    .stProgress > div > div > div > div {
        background-color: #2563eb;
    }
    
    /* 表格字體縮小以符合 BI 樣式 */
    .dataframe {
        font-size: 12px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：BI 參數設定與資料上傳 ---
with st.sidebar:
    st.markdown("<h2 style='color:#111827;'>📊 BI 控制中心</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 上傳數據 (廣告raw-2.xlsx)", type=["xlsx"])
    
    st.divider()
    st.subheader("💰 預算目標 (月度)")
    val_asa = st.number_input("ASA 目標", value=150000, step=10000)
    val_gkw = st.number_input("Google KW 目標", value=500000, step=10000)
    val_pmax = st.number_input("Google Pmax 目標", value=200000, step=10000)
    
    st.divider()
    st.subheader("📅 對比波段 (WOW)")
    # 預設為截圖中的典型區間
    c_s = st.date_input("本週起", datetime(2026, 4, 13))
    c_e = st.date_input("本週迄", datetime(2026, 4, 19))
    p_s = st.date_input("上週起", datetime(2026, 4, 6))
    p_e = st.date_input("上週迄", datetime(2026, 4, 12))

# --- 3. 核心數據處理引擎 (與 HTML 邏輯同步) ---
@st.cache_data
def load_and_clean_data(file):
    if file is None: return None
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names
    
    all_data = []
    # 渠道配置映射 (依照 HTML 中的定義)
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
            # 處理日期格式 (兼容多種格式)
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

# --- 4. BI 畫面渲染 (與規劃一模一樣) ---
if uploaded_file:
    df_raw = load_and_clean_data(uploaded_file)
    
    if df_raw is not None:
        # 導覽分頁
        tab_sum, tab_asa, tab_gkw, tab_pmax = st.tabs([
            "🏠 總覽數據", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"
        ])
        
        # --- 頁面 1: 數據總覽 (Dashboard) ---
        with tab_sum:
            st.markdown("<h2 style='color:#1e293b;'>投放執行度總覽</h2>", unsafe_allow_html=True)
            
            # 執行率進度條區域
            col1, col2, col3 = st.columns(3)
            channels_list = [
                ("ASA", val_asa, col1, "#8b5cf6"),
                ("Google KW", val_gkw, col2, "#2563eb"),
                ("Google Pmax", val_pmax, col3, "#10b981")
            ]
            
            for name, target, col, color in channels_list:
                actual = df_raw[df_raw['Channel'] == name]['Metric_Cost'].sum()
                percent = min(actual / target, 1.0) if target > 0 else 0
                with col:
                    st.markdown(f"**{name}**")
                    st.progress(percent)
                    st.markdown(f"<span style='color:#6b7280; font-size:12px;'>已花費: ${actual:,.0f} / 目標: ${target:,.0f} ({percent:.1%})</span>", unsafe_allow_html=True)

            st.divider()
            
            # 花費趨勢圖 (與 HTML/截圖風格一致)
            st.subheader("📊 每日投放花費趨勢")
            fig = go.Figure()
            for name, target, col, color in channels_list:
                daily = df_raw[df_raw['Channel'] == name].groupby('Date')['Metric_Cost'].sum().reset_index()
                fig.add_trace(go.Scatter(
                    x=daily['Date'], y=daily['Metric_Cost'], 
                    name=name, line=dict(color=color, width=3, shape='spline')
                ))
            
            fig.update_layout(
                template="plotly_white", 
                hovermode="x unified",
                margin=dict(l=10, r=10, t=20, b=10),
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- 頁面 2/3/4: 渠道深度分析 ---
        def render_channel_bi(channel_name, theme_color):
            st.markdown(f"<h2 style='color:{theme_color};'>{channel_name} 數據詳情</h2>", unsafe_allow_html=True)
            
            # 時間段切片
            curr_df = df_raw[(df_raw['Date'] >= pd.Timestamp(c_s)) & (df_raw['Date'] <= pd.Timestamp(c_e)) & (df_raw['Channel'] == channel_name)]
            prev_df = df_raw[(df_raw['Date'] >= pd.Timestamp(p_s)) & (df_raw['Date'] <= pd.Timestamp(p_e)) & (df_raw['Channel'] == channel_name)]
            
            # 指標計算
            c_cost, c_conv, c_click = curr_df['Metric_Cost'].sum(), curr_df['Metric_Conv'].sum(), curr_df['Metric_Click'].sum()
            p_cost, p_conv, p_click = prev_df['Metric_Cost'].sum(), prev_df['Metric_Conv'].sum(), prev_df['Metric_Click'].sum()
            
            def wow(c, p):
                if p == 0: return "N/A"
                return f"{(c-p)/p:+.1%}"

            # 頂部四格核心指標
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("本週進件數", f"{c_conv:,.0f}", wow(c_conv, p_conv))
            with m2:
                c_cpa = c_cost / c_conv if c_conv > 0 else 0
                p_cpa = p_cost / p_conv if p_conv > 0 else 0
                st.metric("CPA (進件成本)", f"${c_cpa:,.0f}", wow(c_cpa, p_cpa), delta_color="inverse")
            with m3:
                st.metric("本週總花費", f"${c_cost:,.0f}", wow(c_cost, p_cost), delta_color="inverse")
            with m4:
                cvr = c_conv / c_click if c_click > 0 else 0
                st.metric("轉化率 (CVR)", f"{cvr:.2%}")

            st.divider()
            
            # 下方明細表格 (與 HTML Table 規劃一致)
            st.write("📋 廣告活動與關鍵字明細")
            details = curr_df.groupby(['廣告活動', '廣告關鍵字']).agg({
                'Metric_Cost': 'sum',
                'Metric_Conv': 'sum',
                'Metric_Click': 'sum',
                'Metric_Impr': 'sum'
            }).reset_index().rename(columns={
                'Metric_Cost': '花費', 'Metric_Conv': '進件', 'Metric_Click': '點擊', 'Metric_Impr': '曝光'
            }).sort_values('花費', ascending=False)
            
            st.dataframe(details, use_container_width=True, height=450)

        with tab_asa: render_channel_bi("ASA", "#8b5cf6")
        with tab_gkw: render_channel_bi("Google KW", "#2563eb")
        with tab_pmax: render_channel_bi("Google Pmax", "#10b981")

else:
    # 待機畫面 (空狀態規劃)
    st.markdown("""
        <div style="text-align: center; padding: 100px 20px; border: 2px dashed #e5e7eb; border-radius: 20px; background: white;">
            <h2 style="color: #4b5563;">歡迎使用 Pocket BI 廣告監控系統</h2>
            <p style="color: #9ca3af;">請在左側側邊欄上傳您的原始數據檔案 (.xlsx) 以開始分析</p>
            <div style="margin-top: 20px;">
                <span style="background: #f3f4f6; padding: 8px 16px; border-radius: 100px; color: #6b7280; font-size: 14px;">自動支援 ASA / Google KW / Pmax</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
