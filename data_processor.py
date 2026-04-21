"""
廣告資料處理模組

【2026/04 最新架構】
xlsx 包含：
  1. ASA           - 欄位：Date, week, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 下載數, 花費（美金）, 花費（台幣）
  2. Google KW     - 欄位：Date, week, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 花費
  3. Google Pmax   - 欄位：Date, week, 廣告活動, 曝光, 點擊, 花費
  4. 進件數完開數   - 欄位：Week, 平台, 廣告活動, 花費, 進件數, 進件成本, 完開數, 完開成本, 完開率, 實動, 實動率
                     週為單位，平台 = Google廣告 / ASA廣告 / Pmax廣告
                     廣告活動 = 品牌字 / ASA廣告 / Pmax廣告 等

【進件/完開 join 邏輯】
  - 以「週」為單位，週範圍解析自 Week15_0406~0412 格式（月日）
  - 每筆廣告日資料依日期判斷落在哪個週，再對應進件數完開數
  - 平台對應：ASA → ASA廣告, Google KW → Google廣告品牌字, PMax → Pmax廣告
"""
import pandas as pd
import numpy as np
import re
from datetime import datetime


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
    """ASA 日期：字串用 MM/DD/YYYY，datetime 物件需 swap month/day（Excel 誤判）"""
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


def parse_week_range(week_str: str, year: int = 2026):
    """
    解析 'Week15_0406~0412' → (start_date, end_date)
    月日格式 MMDD，補上年份
    """
    try:
        m = re.match(r'Week\d+_(\d{2})(\d{2})~(\d{2})(\d{2})', week_str)
        if m:
            sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            start = pd.Timestamp(year=year, month=sm, day=sd)
            end   = pd.Timestamp(year=year, month=em, day=ed)
            return start, end
    except:
        pass
    return None, None


# ── 數值工具 ──────────────────────────────────────────
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
    """讀取 xlsx，回傳全量資料字典（不做時間切割）"""
    sheets = pd.read_excel(file, sheet_name=None)
    out = {}

    # 讀取進件數完開數（週為單位）
    conv_df = _load_conv(sheets.get('進件數完開數', pd.DataFrame()))
    out['conv_raw'] = conv_df

    out.update(_load_asa(sheets.get('ASA', pd.DataFrame()), conv_df))
    out.update(_load_kw(sheets.get('Google KW', pd.DataFrame()), conv_df))
    out.update(_load_pmax(sheets.get('Google Pmax', pd.DataFrame()), conv_df))

    out['meta'] = _build_meta(out)
    return out


# ── 進件數完開數（週單位）────────────────────────────
def _load_conv(df: pd.DataFrame) -> pd.DataFrame:
    """
    解析週轉換資料，回傳包含 start/end 日期範圍的表
    欄位：week_str, platform, campaign, start_date, end_date,
          jin, wan, shidong, jin_cost, wan_cost, wan_rate
    """
    if df.empty:
        return pd.DataFrame()
    df = df.copy().dropna(subset=['Week', '平台'])
    df.columns = [c.strip() for c in df.columns]
    records = []
    for _, row in df.iterrows():
        ws = str(row.get('Week', ''))
        start, end = parse_week_range(ws)
        if start is None:
            continue
        records.append({
            'week_str':   ws,
            'platform':   str(row.get('平台', '')),
            'campaign':   str(row.get('廣告活動', '')),
            'start_date': start,
            'end_date':   end,
            'jin':        pd.to_numeric(row.get('進件數', 0), errors='coerce') or 0,
            'wan':        pd.to_numeric(row.get('完開數', 0), errors='coerce') or 0,
            'shidong':    pd.to_numeric(row.get('實動', 0), errors='coerce') or 0,
            'jin_cost':   pd.to_numeric(row.get('進件成本', 0), errors='coerce') or 0,
            'wan_cost':   pd.to_numeric(row.get('完開成本', 0), errors='coerce') or 0,
            'wan_rate':   pd.to_numeric(row.get('完開率', 0), errors='coerce') or 0,
            'spend':      pd.to_numeric(row.get('花費', 0), errors='coerce') or 0,
        })
    return pd.DataFrame(records) if records else pd.DataFrame()


def _get_conv_for_platform(conv_df: pd.DataFrame, platform_kw: str) -> pd.DataFrame:
    """取出特定平台的週轉換資料"""
    if conv_df.empty:
        return pd.DataFrame()
    mask = conv_df['platform'].str.contains(platform_kw, case=False, na=False)
    return conv_df[mask].copy()


def _assign_week_conv(daily_df: pd.DataFrame, conv_platform: pd.DataFrame,
                      spend_col: str = 'spend') -> pd.DataFrame:
    """
    將週轉換資料依日期範圍 assign 到每天的資料上。
    同一平台同一週的進件數/完開數，按花費比例分配到各廣告活動。
    回傳加總後的廣告活動層級表（含 jin, wan）。
    """
    if daily_df.empty or conv_platform.empty:
        return pd.DataFrame()

    result = daily_df.copy()
    result['jin'] = 0.0
    result['wan'] = 0.0
    result['shidong'] = 0.0

    # 對每個週，找落在該週的日期，按花費比例分配
    for _, conv_row in conv_platform.iterrows():
        s = conv_row['start_date']
        e = conv_row['end_date']
        mask = (result['date'] >= s) & (result['date'] <= e)
        sub = result[mask]
        if sub.empty:
            continue
        total_spend = sub[spend_col].sum()
        if total_spend == 0:
            continue
        ratio = sub[spend_col] / total_spend
        result.loc[mask, 'jin']     += ratio * float(conv_row['jin'] or 0)
        result.loc[mask, 'wan']     += ratio * float(conv_row['wan'] or 0)
        result.loc[mask, 'shidong'] += ratio * float(conv_row['shidong'] or 0)

    return result


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

    # 日層級（用於日期篩選）
    daily = df.groupby(['date_str', 'date']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()

    # 廣告活動層級（不含轉換，轉換由週資料 join）
    camp = df.groupby('廣告活動').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()

    # 取 ASA 週轉換資料
    asa_conv = _get_conv_for_platform(conv_df, 'ASA')
    asa_conv_totals = _get_conv_totals(asa_conv)  # 全量 jin/wan

    camp['jin'] = asa_conv_totals.get('jin', 0)
    camp['wan'] = asa_conv_totals.get('wan', 0)
    camp['shidong'] = asa_conv_totals.get('shidong', 0)

    # 依花費比例分配到各廣告活動
    total_spend = camp['spend'].sum()
    if total_spend > 0 and (camp['jin'].sum() > 0 or camp['wan'].sum() > 0):
        for idx, row in camp.iterrows():
            ratio = row['spend'] / total_spend if total_spend > 0 else 0
            camp.at[idx, 'jin'] = asa_conv_totals.get('jin', 0) * ratio
            camp.at[idx, 'wan'] = asa_conv_totals.get('wan', 0) * ratio
            camp.at[idx, 'shidong'] = asa_conv_totals.get('shidong', 0) * ratio

    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPI']    = camp.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    camp['CPL']    = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['dl'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    # 關鍵字層級（純流量）
    kw = df.groupby(['廣告活動','廣告群組','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()
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

    daily = df.groupby(['date_str','date']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    camp = df.groupby(['廣告活動','camp_short']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    # Google KW → Google廣告 / 品牌字 等
    google_conv = _get_conv_for_platform(conv_df, 'Google')
    google_totals = _get_conv_totals(google_conv)

    # 依 camp_short 名稱精確對應（如 '品牌字' 對應 conv 的 '品牌字'）
    # 若找不到精確對應，按花費比例分配
    camp['jin'] = 0.0; camp['wan'] = 0.0; camp['shidong'] = 0.0
    for _, conv_row in google_conv.iterrows():
        camp_name = conv_row.get('campaign', '')
        exact = camp[camp['camp_short'] == camp_name]
        if not exact.empty:
            for idx in exact.index:
                camp.at[idx, 'jin'] += float(conv_row.get('jin', 0) or 0)
                camp.at[idx, 'wan'] += float(conv_row.get('wan', 0) or 0)
                camp.at[idx, 'shidong'] += float(conv_row.get('shidong', 0) or 0)

    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']    = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']    = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['進件率%'] = camp.apply(lambda r: sdiv(r['jin'], r['clk'], 100), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    kw = df.groupby(['camp_short','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()
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

    daily = df.groupby(['date_str','date']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    camp = df.groupby('廣告活動').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()

    pmax_conv = _get_conv_for_platform(conv_df, 'Pmax')
    pmax_totals = _get_conv_totals(pmax_conv)

    camp['jin'] = pmax_totals.get('jin', 0)
    camp['wan'] = pmax_totals.get('wan', 0)
    camp['shidong'] = pmax_totals.get('shidong', 0)

    camp['CTR%']  = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']   = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']   = camp.apply(lambda r: sdiv(r['spend'], r['jin'], 1, 0), axis=1)
    camp['完開率%'] = camp.apply(lambda r: sdiv(r['wan'], r['jin'], 100), axis=1)

    return {'pm_daily': daily, 'pm_camp': camp, 'pm_raw': df}


def _get_conv_totals(conv_df: pd.DataFrame) -> dict:
    """合計特定平台所有週的轉換數值"""
    if conv_df.empty:
        return {'jin': 0, 'wan': 0, 'shidong': 0}
    return {
        'jin':     conv_df['jin'].sum(),
        'wan':     conv_df['wan'].sum(),
        'shidong': conv_df['shidong'].sum(),
    }


# ── 時間 meta ─────────────────────────────────────────
def _build_meta(out: dict) -> dict:
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


# ── 日期範圍篩選 ──────────────────────────────────────
def filter_dates(df: pd.DataFrame, date_col: str, start: str, end: str) -> pd.DataFrame:
    """依手動選擇的日期範圍篩選"""
    if df.empty or not start or not end:
        return df
    return df[(df[date_col] >= start) & (df[date_col] <= end)].copy()
