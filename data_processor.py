"""
廣告資料處理模組

【2026/04 架構說明】
xlsx 包含 5 個分頁：
  1. META          - Facebook/Meta 廣告（廣告活動/廣告組合/廣告名稱層級）
  2. ASA           - Apple Search Ads 關鍵字層級（無進件數/完開數）
  3. Google KW     - Google 關鍵字廣告層級（無進件數/完開數）
  4. Google Pmax   - Google PMax 廣告活動層級（無進件數/完開數）
  5. 進件數完開數   - 獨立轉換表，欄位：Date, 平台, 廣告活動, 進件數, 完開數
                     由使用者手動填入，join 到各平台廣告活動層級
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ── 日期解析 ──────────────────────────────────────────
def parse_date(d):
    try:
        if isinstance(d, str):
            for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    return pd.to_datetime(d, format=fmt)
                except:
                    pass
        return pd.to_datetime(d)
    except:
        return pd.NaT


def fix_asa_dates(series: pd.Series) -> pd.Series:
    """
    ASA 日期特殊處理：
    - 字串格式 '04/16/2026' → 正常解析 MM/DD/YYYY
    - datetime 物件 → Excel 誤把 DD/MM 讀成 MM/DD，需要 swap month/day 修正
    """
    def fix_one(d):
        if isinstance(d, str):
            try:
                return pd.to_datetime(d, format="%m/%d/%Y")
            except:
                try:
                    return pd.to_datetime(d)
                except:
                    return pd.NaT
        else:
            try:
                # Excel datetime: month/day swapped, fix by swapping back
                return pd.Timestamp(year=d.year, month=d.day, day=d.month)
            except:
                try:
                    return pd.Timestamp(d)
                except:
                    return pd.NaT
    return series.apply(fix_one)


# ── 數值工具 ──────────────────────────────────────────
def sdiv(a, b, scale=1, dec=2):
    """安全除法"""
    try:
        if b and float(b) != 0:
            return round(float(a) / float(b) * scale, dec)
    except:
        pass
    return 0.0


def fmt_money(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "–"
    if abs(n) >= 10000:
        return f"NT${n/10000:.1f}萬"
    return f"NT${n:,.0f}"


def fmt_num(n, dec=0):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "–"
    if abs(n) >= 10000:
        return f"{n/10000:.1f}萬"
    if dec == 0:
        return f"{int(n):,}"
    return f"{n:,.{dec}f}"


def wow_pct(cur, prev):
    """回傳 WoW% 或 None"""
    try:
        if prev and float(prev) != 0:
            return (float(cur) - float(prev)) / float(prev) * 100
    except:
        pass
    return None


# ── 廣告活動名稱縮短 ──────────────────────────────────
def shorten_camp(n: str) -> str:
    n = str(n)
    if '品牌字' in n: return '品牌字'
    if '郵局字' in n: return '郵局字'
    if '投資入門' in n: return '投資入門'
    if 'PMAX' in n.upper() or 'Pmax' in n: return 'PMax'
    return n[:16]


# ══════════════════════════════════════════════════════
# 主要讀取函式
# ══════════════════════════════════════════════════════
def load_data(file) -> dict:
    """
    讀取 xlsx，回傳整理後的資料字典。
    所有進件數/完開數均從「進件數完開數」分頁 join 而來。
    """
    sheets = pd.read_excel(file, sheet_name=None)
    out = {}

    # ── 0. 讀取轉換資料（所有平台共用）──────────────────
    conv_df = _load_conv(sheets.get('進件數完開數', pd.DataFrame()))
    out['conv_raw'] = conv_df

    # ── 1. META ──────────────────────────────────────
    out.update(_load_meta(sheets.get('META', pd.DataFrame()), conv_df))

    # ── 2. ASA ───────────────────────────────────────
    out.update(_load_asa(sheets.get('ASA', pd.DataFrame()), conv_df))

    # ── 3. Google KW ─────────────────────────────────
    out.update(_load_kw(sheets.get('Google KW', pd.DataFrame()), conv_df))

    # ── 4. Google PMax ───────────────────────────────
    out.update(_load_pmax(sheets.get('Google Pmax', pd.DataFrame()), conv_df))

    # ── 5. 時間 meta ─────────────────────────────────
    out['meta'] = _build_meta(out)

    return out


# ── 轉換資料 ──────────────────────────────────────────
def _load_conv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['date', 'platform', 'campaign', 'jin', 'wan'])
    df = df.copy()
    df.columns = ['date_raw', 'platform', 'campaign', 'jin', 'wan']
    df['date'] = df['date_raw'].apply(parse_date)
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['jin'] = pd.to_numeric(df['jin'], errors='coerce').fillna(0)
    df['wan'] = pd.to_numeric(df['wan'], errors='coerce').fillna(0)
    return df


def _get_conv(conv_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """篩出特定平台的轉換資料"""
    if conv_df.empty:
        return pd.DataFrame(columns=['date_str', 'campaign', 'jin', 'wan'])
    plat_col = conv_df['platform'].astype(str)
    if platform:
        mask = plat_col.str.contains(platform, na=False, case=False)
    else:
        mask = pd.Series([True] * len(conv_df), index=conv_df.index)
    return conv_df[mask][['date_str', 'campaign', 'jin', 'wan']]


# ── META ──────────────────────────────────────────────
def _load_meta(df: pd.DataFrame, conv_df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: pd.DataFrame() for k in ['meta_daily', 'meta_camp', 'meta_raw']}

    df = df.copy()
    df['date'] = pd.to_datetime(df['天數'], errors='coerce')
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['spend'] = pd.to_numeric(df.get('花費金額 (TWD)', df.get('花費', 0)), errors='coerce').fillna(0)
    df['imp']   = pd.to_numeric(df.get('曝光次數', 0), errors='coerce').fillna(0)
    df['clk']   = pd.to_numeric(df.get('連結點擊次數', 0), errors='coerce').fillna(0)
    df['camp']  = df['行銷活動名稱'].astype(str)

    # 日層級
    daily = df.groupby('date_str').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()

    # 廣告活動層級
    camp = df.groupby('camp').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()

    # Join 轉換
    conv = _get_conv(conv_df, 'META')
    if not conv.empty:
        conv_camp = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(conv_camp, left_on='camp', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0

    camp = camp.fillna(0)
    camp['CTR%'] = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']  = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']  = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['clk'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    return {'meta_daily': daily, 'meta_camp': camp, 'meta_raw': df}


# ── ASA ───────────────────────────────────────────────
def _load_asa(df: pd.DataFrame, conv_df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: pd.DataFrame() for k in ['asa_daily', 'asa_camp', 'asa_kw', 'asa_raw']}

    df = df.copy()
    df['date'] = fix_asa_dates(df['Date'])
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['spend'] = pd.to_numeric(df.get('花費（台幣）', 0), errors='coerce').fillna(0)
    df['imp']   = pd.to_numeric(df['曝光'], errors='coerce').fillna(0)
    df['clk']   = pd.to_numeric(df['點擊'], errors='coerce').fillna(0)
    df['dl']    = pd.to_numeric(df['下載數'], errors='coerce').fillna(0)

    # 日層級
    daily = df.groupby('date_str').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()

    # 廣告活動層級
    camp = df.groupby('廣告活動').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()

    # Join 轉換
    conv = _get_conv(conv_df, 'ASA')
    if not conv.empty:
        conv_camp = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(conv_camp, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0

    camp = camp.fillna(0)
    camp['CTR%'] = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPI']  = camp.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    camp['CPL']  = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['dl'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    # 關鍵字層級（純流量指標，不含轉換）
    kw = df.groupby(['廣告活動', '廣告群組', '廣告關鍵字']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPI']  = kw.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'asa_daily': daily, 'asa_camp': camp, 'asa_kw': kw, 'asa_raw': df}


# ── Google KW ─────────────────────────────────────────
def _load_kw(df: pd.DataFrame, conv_df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: pd.DataFrame() for k in ['kw_daily', 'kw_camp', 'kw_kw', 'kw_raw']}

    df = df.copy()
    df['date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['spend'] = pd.to_numeric(df['花費'], errors='coerce').fillna(0)
    df['imp']   = pd.to_numeric(df['曝光'], errors='coerce').fillna(0)
    df['clk']   = pd.to_numeric(df['點擊'], errors='coerce').fillna(0)
    df['camp_short'] = df['廣告活動'].apply(shorten_camp)

    # 日層級
    daily = df.groupby('date_str').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()

    # 廣告活動層級
    camp = df.groupby(['廣告活動', 'camp_short']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()

    # Join 轉換
    conv = _get_conv(conv_df, 'Google')
    if not conv.empty:
        conv_camp = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(conv_camp, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0

    camp = camp.fillna(0)
    camp['CTR%'] = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']  = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']  = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['clk'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    # 關鍵字層級（純流量指標）
    kw = df.groupby(['camp_short', '廣告關鍵字']).agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPC']  = kw.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'kw_daily': daily, 'kw_camp': camp, 'kw_kw': kw, 'kw_raw': df}


# ── Google PMax ───────────────────────────────────────
def _load_pmax(df: pd.DataFrame, conv_df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: pd.DataFrame() for k in ['pm_daily', 'pm_camp', 'pm_raw']}

    df = df.copy()
    df['date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['spend'] = pd.to_numeric(df['花費'], errors='coerce').fillna(0)
    df['imp']   = pd.to_numeric(df['曝光'], errors='coerce').fillna(0)
    df['clk']   = pd.to_numeric(df['點擊'], errors='coerce').fillna(0)

    daily = df.groupby('date_str').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()
    camp  = df.groupby('廣告活動').agg(spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')).reset_index()

    # Join 轉換
    conv = _get_conv(conv_df, 'Google')
    if not conv.empty:
        conv_camp = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(conv_camp, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0

    camp = camp.fillna(0)
    camp['CTR%'] = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']  = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']  = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    return {'pm_daily': daily, 'pm_camp': camp, 'pm_raw': df}


# ── 時間 meta ─────────────────────────────────────────
def _build_meta(out: dict) -> dict:
    all_dates = []
    for key in ['asa_daily', 'kw_daily', 'pm_daily', 'meta_daily']:
        df = out.get(key, pd.DataFrame())
        if not df.empty and 'date_str' in df.columns:
            all_dates += df['date_str'].dropna().tolist()
    all_dates = sorted(set(all_dates))
    if not all_dates:
        return {}
    min_d = all_dates[0]
    max_d = all_dates[-1]
    max_dt = datetime.strptime(max_d, '%Y-%m-%d')
    return {
        'min_date':  min_d,
        'max_date':  max_d,
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'w2_start':  (max_dt - timedelta(days=6)).strftime('%Y-%m-%d'),
        'w2_end':    max_d,
        'w1_start':  (max_dt - timedelta(days=13)).strftime('%Y-%m-%d'),
        'w1_end':    (max_dt - timedelta(days=7)).strftime('%Y-%m-%d'),
    }


# ── 週期篩選工具 ──────────────────────────────────────
def period_slice(df: pd.DataFrame, date_col: str, meta: dict, period: str) -> pd.DataFrame:
    if df.empty or not meta:
        return df
    if period == 'week':
        return df[(df[date_col] >= meta['w2_start']) & (df[date_col] <= meta['w2_end'])]
    elif period == 'prev':
        return df[(df[date_col] >= meta['w1_start']) & (df[date_col] <= meta['w1_end'])]
    return df  # month = all
