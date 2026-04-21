"""
廣告資料處理模組

【架構說明】
xlsx 包含 4 個分頁：
  1. ASA           - Apple Search Ads（無進件數/完開數）
  2. Google KW     - Google 關鍵字廣告（無進件數/完開數）
  3. Google Pmax   - Google PMax（無進件數/完開數）
  4. 進件數完開數   - 獨立轉換表，欄位：Date, 平台, 廣告活動, 進件數, 完開數

時間維度：由 app.py 的手動日期選擇器控制
"""
import pandas as pd
import numpy as np
from datetime import datetime


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


def fix_asa_dates(series):
    """ASA 日期：字串用 MM/DD/YYYY，datetime 物件需 swap month/day"""
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
                return pd.Timestamp(year=d.year, month=d.day, day=d.month)
            except:
                try:
                    return pd.Timestamp(d)
                except:
                    return pd.NaT
    return series.apply(fix_one)


def sdiv(a, b, scale=1, dec=2):
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
    try:
        if prev and float(prev) != 0:
            return (float(cur) - float(prev)) / float(prev) * 100
    except:
        pass
    return None


def shorten_camp(n):
    n = str(n)
    if '品牌字' in n: return '品牌字'
    if '郵局字' in n: return '郵局字'
    if '投資入門' in n: return '投資入門'
    if 'PMAX' in n.upper() or 'Pmax' in n: return 'PMax'
    return n[:16]


def load_data(file):
    """讀取 xlsx，回傳全量資料字典（不做時間切割，由 UI 的日期選擇器控制）"""
    sheets = pd.read_excel(file, sheet_name=None)
    out = {}
    conv_df = _load_conv(sheets.get('進件數完開數', pd.DataFrame()))
    out['conv_raw'] = conv_df
    out.update(_load_asa(sheets.get('ASA', pd.DataFrame()), conv_df))
    out.update(_load_kw(sheets.get('Google KW', pd.DataFrame()), conv_df))
    out.update(_load_pmax(sheets.get('Google Pmax', pd.DataFrame()), conv_df))
    out['meta'] = _build_meta(out)
    return out


def _load_conv(df):
    if df.empty:
        return pd.DataFrame(columns=['date_str', 'platform', 'campaign', 'jin', 'wan'])
    df = df.copy()
    df.columns = ['date_raw', 'platform', 'campaign', 'jin', 'wan']
    df['date'] = df['date_raw'].apply(parse_date)
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['jin'] = pd.to_numeric(df['jin'], errors='coerce').fillna(0)
    df['wan'] = pd.to_numeric(df['wan'], errors='coerce').fillna(0)
    return df


def _get_conv(conv_df, platform):
    if conv_df.empty:
        return pd.DataFrame(columns=['date_str', 'campaign', 'jin', 'wan'])
    plat_col = conv_df['platform'].astype(str)
    if platform:
        mask = plat_col.str.contains(platform, na=False, case=False)
    else:
        mask = pd.Series([True] * len(conv_df), index=conv_df.index)
    return conv_df[mask][['date_str', 'campaign', 'jin', 'wan']]


def _load_asa(df, conv_df):
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

    daily = df.groupby('date_str').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()

    camp = df.groupby('廣告活動').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()

    conv = _get_conv(conv_df, 'ASA')
    if not conv.empty:
        cg = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(cg, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0
    camp = camp.fillna(0)
    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPI']    = camp.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    camp['CPL']    = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['dl'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    kw = df.groupby(['廣告活動', '廣告群組', '廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPI']  = kw.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'asa_daily': daily, 'asa_camp': camp, 'asa_kw': kw, 'asa_raw': df}


def _load_kw(df, conv_df):
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

    daily = df.groupby('date_str').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    camp = df.groupby(['廣告活動', 'camp_short']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    conv = _get_conv(conv_df, 'Google')
    if not conv.empty:
        cg = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(cg, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0
    camp = camp.fillna(0)
    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']    = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']    = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['clk'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    kw = df.groupby(['camp_short', '廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPC']  = kw.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'kw_daily': daily, 'kw_camp': camp, 'kw_kw': kw, 'kw_raw': df}


def _load_pmax(df, conv_df):
    if df.empty:
        return {k: pd.DataFrame() for k in ['pm_daily', 'pm_camp', 'pm_raw']}
    df = df.copy()
    df['date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['spend'] = pd.to_numeric(df['花費'], errors='coerce').fillna(0)
    df['imp']   = pd.to_numeric(df['曝光'], errors='coerce').fillna(0)
    df['clk']   = pd.to_numeric(df['點擊'], errors='coerce').fillna(0)

    daily = df.groupby('date_str').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    camp = df.groupby('廣告活動').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    conv = _get_conv(conv_df, 'Google')
    if not conv.empty:
        cg = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
        camp = camp.merge(cg, left_on='廣告活動', right_on='campaign', how='left')
    else:
        camp['jin'] = 0; camp['wan'] = 0
    camp = camp.fillna(0)
    camp['CTR%']  = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']   = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']   = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    return {'pm_daily': daily, 'pm_camp': camp, 'pm_raw': df}


def _build_meta(out):
    all_dates = []
    for key in ['asa_daily', 'kw_daily', 'pm_daily']:
        df = out.get(key, pd.DataFrame())
        if not df.empty and 'date_str' in df.columns:
            all_dates += df['date_str'].dropna().tolist()
    all_dates = sorted(set(all_dates))
    if not all_dates:
        return {}
    return {
        'min_date':  all_dates[0],
        'max_date':  all_dates[-1],
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'all_dates': all_dates,
    }


def filter_by_dates(df, date_col, start, end):
    """依手動選擇的日期範圍篩選"""
    if df.empty or not start or not end:
        return df
    return df[(df[date_col] >= start) & (df[date_col] <= end)].copy()


def reagg_camp_from_raw(raw_df, group_col, agg_cols, conv_df=None, platform=None, camp_key='廣告活動'):
    """
    從已篩選日期的 raw_df 重新彙總廣告活動層級，確保日期篩選有效
    agg_cols: list of raw column names to sum
    """
    if raw_df.empty:
        return pd.DataFrame()
    camp = raw_df.groupby(group_col)[agg_cols].sum().reset_index()
    if conv_df is not None and platform is not None:
        conv = _get_conv(conv_df, platform)
        if not conv.empty:
            cg = conv.groupby('campaign').agg(jin=('jin','sum'), wan=('wan','sum')).reset_index()
            camp = camp.merge(cg, left_on=camp_key, right_on='campaign', how='left')
        else:
            camp['jin'] = 0; camp['wan'] = 0
    camp = camp.fillna(0)
    return camp
