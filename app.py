import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 頁面配置 ---
st.set_page_config(layout="wide", page_title="Pocket BI 廣告儀表板", initial_sidebar_state="expanded")

# --- 2. 核心 CSS 樣式 (極致還原圖片視覺) ---
st.markdown("""
    <style>
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

    /* 全局背景與文字 */
    .main { background-color: var(--bg) !important; }
    h1, h2, h3, p, span, label, div { color: var(--text) !important; font-family: sans-serif; }

    /* 頂部 Tab 樣式修正 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 2px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 4px;
        font-weight: 600;
        color: var(--muted) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--gkw) !important;
        border-bottom: 3px solid var(--gkw) !important;
    }

    /* 指標卡片與進度條樣式 */
    .progress-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .progress-title { font-weight: 700; font-size: 16px; }
    .progress-percent { font-weight: 800; font-size: 18px; }
    
    .bar-bg { background: #f0f2f5; height: 10px; border-radius: 5px; width: 100%; position: relative; }
    .bar-fill { height: 10px; border-radius: 5px; transition: width 0.5s ease; }

    /* 表格美化 */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 側邊欄控制項 ---
with st.sidebar:
    st.markdown("<h1 style='font-size: 24px; margin-bottom: 20px;'>Pocket BI</h1>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 上傳廣告數據 (raw-2.xlsx)", type=["xlsx"])
    
    st.divider()
    st.markdown("### 🎯 預算目標設定")
    b_asa = st.number_input("ASA 月預算 (TWD)", value=150000)
    b_gkw = st.number_input("GKW 月預算 (TWD)", value=500000)
    b_pmax = st.number_input("Pmax 月預算 (TWD)", value=200000)
    
    st.divider()
    st.markdown("### 📅 時間範圍篩選")
    c_s = st.date_input("本波段開始", datetime(2026, 4, 13))
    c_e = st.date_input("本波段結束", datetime(2026, 4, 19))
    p_s = st.date_input("上波段開始", datetime(2026, 4, 6))
    p_e = st.date_input("上波段結束", datetime(2026, 4, 12))

# --- 4. 強化版數據處理引擎 (ASA 邏輯修正) ---
@st.cache_data
def process_data(file):
    if not file: return None
    xls = pd.ExcelFile(file)
    
    # 嚴格定義渠道配置，確保與 Sheet 內容對應
    configs = {
        'ASA': {'tag': 'ASA', 'cost_col': '花費（台幣）', 'download_col': '下載數'},
        'Google KW': {'tag': 'KW', 'cost_col': '花費', 'download_col': None},
        'Google Pmax': {'tag': 'PMAX', 'cost_col': '花費', 'download_col': None}
    }
    
    all_data = []
    for ch_name, cfg in configs.items():
        sheet = next((s for s in xls.sheet_names if cfg['tag'].upper() in s.upper()), None)
        if sheet:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            
            # 日期清理
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # 指標標準化
            df['Channel'] = ch_name
            df['Cost'] = pd.to_numeric(df[cfg['cost_col']], errors='coerce').fillna(0) if cfg['cost_col'] in df.columns else 0
            df['Impr'] = pd.to_numeric(df['曝光'], errors='coerce').fillna(0) if '曝光' in df.columns else 0
            df['Click'] = pd.to_numeric(df['點擊'], errors='coerce').fillna(0) if '點擊' in df.columns else 0
            
            # ASA 特有的下載數抓取
            if ch_name == 'ASA':
                df['Download'] = pd.to_numeric(df['下載數'], errors='coerce').fillna(0)
            else:
                df['Download'] = 0
                
            df['Inquiry'] = pd.to_numeric(df['進件數'], errors='coerce').fillna(0) if '進件數' in df.columns else 0
            df['Open'] = pd.to_numeric(df['完開數'], errors='coerce').fillna(0) if '完開數' in df.columns else 0
            
            # 維度補完 (確保明細層級完整)
            df['Campaign'] = df['廣告活動'].fillna('未命名活動')
            df['Group'] = df['廣告群組'].fillna('預設群組') if '廣告群組' in df.columns else '預設群組'
            df['Keyword'] = df['廣告關鍵字'].fillna('-') if '廣告關鍵字' in df.columns else '-'
            
            all_data.append(df)
            
    return pd.concat(all_data, ignore_index=True) if all_data else None

# --- 5. 介面渲染 ---
if uploaded_file:
    df_all = process_data(uploaded_file)
    if df_all is not None:
        tab_main, tab_asa, tab_gkw, tab_pmax = st.tabs(["🏠 總覽儀表板", "🟣 ASA 分析", "🔵 Google KW", "🟢 Pmax 監控"])
        
        # --- [總覽頁面：預算進度條] ---
        with tab_main:
            st.markdown("<h2 style='font-weight: 800; margin-bottom: 20px;'>廣告投放執行概況</h2>", unsafe_allow_html=True)
            
            cols = st.columns(3)
            budgets = [
                ("Apple Search Ads (ASA)", b_asa, cols[0], "#8b5cf6"),
                ("Google 關鍵字 (KW)", b_gkw, cols[1], "#2563eb"),
                ("Google Pmax", b_pmax, cols[2], "#10b981")
            ]
            
            for title, target, col, color in budgets:
                # 計算該渠道總花費
                short_name = "ASA" if "ASA" in title else ("KW" if "KW" in title else "Pmax")
                ch_total = df_all[df_all['Channel'].str.contains(short_name)]['Cost'].sum()
                rate = (ch_total / target) if target > 0 else 0
                
                with col:
                    st.markdown(f"""
                    <div class="progress-card">
                        <div class="progress-header">
                            <span class="progress-title">{title}</span>
                            <span class="progress-percent" style="color:{color};">{rate:.1%}</span>
                        </div>
                        <div class="bar-bg">
                            <div class="bar-fill" style="width:{min(rate*100, 100)}%; background:{color};"></div>
                        </div>
                        <div style="margin-top:12px; font-size:13px; color:#6b7280; display:flex; justify-content:space-between;">
                            <span>已花費 <b>${ch_total:,.0f}</b></span>
                            <span>目標 ${target:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>### 投放趨勢分析", unsafe_allow_html=True)
            trend_df = df_all.groupby(['Date', 'Channel'])['Cost'].sum().unstack().fillna(0)
            fig = go.Figure()
            colors = {"ASA": "#8b5cf6", "Google KW": "#2563eb", "Google Pmax": "#10b981"}
            for ch in trend_df.columns:
                fig.add_trace(go.Scatter(x=trend_df.index, y=trend_df[ch], name=ch, line=dict(color=colors.get(ch, "#333"), width=3), mode='lines+markers'))
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), height=380, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

        # --- [渠道細分頁面渲染函數] ---
        def render_channel_tab(ch_name):
            # 波段篩選
            curr_df = df_all[(df_all['Channel'] == ch_name) & (df_all['Date'] >= pd.Timestamp(c_s)) & (df_all['Date'] <= pd.Timestamp(c_e))]
            prev_df = df_all[(df_all['Channel'] == ch_name) & (df_all['Date'] >= pd.Timestamp(p_s)) & (df_all['Date'] <= pd.Timestamp(p_e))]
            
            # 核心指標 (Top Bar)
            c_cost, p_cost = curr_df['Cost'].sum(), prev_df['Cost'].sum()
            c_inq, p_inq = curr_df['Inquiry'].sum(), prev_df['Inquiry'].sum()
            c_clk, p_clk = curr_df['Click'].sum(), prev_df['Click'].sum()
            c_cpa = c_cost / c_inq if c_inq > 0 else 0
            p_cpa = p_cost / p_inq if p_inq > 0 else 0
            
            m1, m2, m3, m4 = st.columns(4)
            def get_delta(c, p): return f"{(c-p)/p:+.1%}" if p > 0 else "0.0%"
            
            m1.metric("進件數 (現/前)", f"{c_inq:,.0f}", get_delta(c_inq, p_inq))
            m2.metric("CPA (進件成本)", f"${c_cpa:,.0f}", get_delta(c_cpa, p_cpa), delta_color="inverse")
            m3.metric("本波段花費", f"${c_cost:,.0f}", get_delta(c_cost, p_cost), delta_color="inverse")
            m4.metric("點擊數", f"{c_clk:,.0f}", get_delta(c_clk, p_clk))

            st.markdown("---")
            
            # --- 重點：廣告活動與群組細分列表 ---
            st.markdown(f"#### {ch_name} 廣告活動/群組 成效明細")
            
            group_keys = ['Campaign', 'Group']
            if ch_name != 'Google Pmax': group_keys.append('Keyword')
            
            detail = curr_df.groupby(group_keys).agg({
                'Impr': 'sum', 'Click': 'sum', 'Download': 'sum',
                'Cost': 'sum', 'Inquiry': 'sum', 'Open': 'sum'
            }).reset_index()
            
            # 計算衍生率
            detail['CTR'] = (detail['Click'] / detail['Impr'])
            detail['CVR'] = (detail['Inquiry'] / detail['Click'])
            detail['CPA'] = (detail['Cost'] / detail['Inquiry'])
            detail = detail.replace([float('inf'), -float('inf')], 0).fillna(0)
            
            # 依花費排序
            detail = detail.sort_values('Cost', ascending=False)
            
            # 欄位重新命名還原圖片樣式
            renames = {
                'Campaign': '廣告活動', 'Group': '廣告群組', 'Keyword': '關鍵字',
                'Impr': '曝光', 'Click': '點擊', 'Download': '下載', 
                'Cost': '花費', 'Inquiry': '進件', 'Open': '完開',
                'CTR': '點擊率', 'CVR': '轉化率'
            }
            detail = detail.rename(columns=renames)
            
            # 表格配置
            st.dataframe(
                detail,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "花費": st.column_config.NumberColumn("花費", format="$%d"),
                    "點擊率": st.column_config.NumberColumn("點擊率", format="%.2f%%"),
                    "轉化率": st.column_config.ProgressColumn("轉化率", format="%.2f", min_value=0, max_value=0.5),
                    "CPA": st.column_config.NumberColumn("CPA", format="$%.0f"),
                    "曝光": st.column_config.NumberColumn("曝光", format="%d"),
                    "點擊": st.column_config.NumberColumn("點擊", format="%d")
                }
            )

        with tab_asa: render_channel_tab("ASA")
        with tab_gkw: render_channel_tab("Google KW")
        with tab_pmax: render_channel_tab("Google Pmax")

else:
    st.info("請於側邊欄上傳廣告原始數據檔案以開啟監控。")
