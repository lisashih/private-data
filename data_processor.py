"""
廣告資料處理模組

【2026/04 最新架構】
xlsx 包含：
  1. ASA           - 欄位：Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 下載數, 花費（美金）, 花費（台幣）
  2. Google KW     - 欄位：Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 花費
  3. Google Pmax   - 欄位：Date, 廣告活動, 曝光, 點擊, 花費
  4. 工作表1（進件明細）- 欄位：date, week, 平台, 廣告, 開戶狀態, 人數
     進件數 = 某天某廣告所有開戶狀態人數總和（開戶已完成 + 開戶未完成）
     開戶數 = 某天某廣告「開戶已完成」人數總和
     開戶率 = 開戶數 / 進件數
     花費   = 該廣告所屬平台（01-Google廣告→KW+PMax，03-APP廣告→ASA）的花費加總

【輸出】
  conv_day  - 天維度：date_str, 平台, 廣告, 曝光, 點擊, 花費, 進件數, 開戶數, 進件成本, 開戶成本, 開戶率%
  conv_week - 週維度：week, 平台, 廣告, 曝光, 點擊, 花費, 進件數, 開戶數, 進件成本, 開戶成本, 開戶率%
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
    格式 MMDD，年份預設 2026
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


# ── 輔助工具 ──────────────────────────────────────────
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
    if '廣字' in n: return '廣字'
    if '投資入門' in n: return '投資入門'
    if 'PMAX' in n.upper() or 'Pmax' in n: return 'PMax'
    return n[:16]


# ══════════════════════════════════════════════════════
# 主要資料載入
# ══════════════════════════════════════════════════════
def load_data(file) -> dict:
    """讀取 xlsx，回傳全量資料字典（不做時間切割）"""
    sheets = pd.read_excel(file, sheet_name=None)
    out = {}

    # 先載入廣告平台原始資料
    out.update(_load_asa(sheets.get('ASA', pd.DataFrame())))
    out.update(_load_kw(sheets.get('Google KW', pd.DataFrame())))
    out.update(_load_pmax(sheets.get('Google Pmax', pd.DataFrame())))

    # 載入進件明細（新格式：工作表1；舊格式：進件數完開數）
    detail_sheet = sheets.get('工作表1', sheets.get('進件數完開數', pd.DataFrame()))
    conv_day, conv_week = _load_conv_detail(
        detail_sheet,
        asa_raw=out.get('asa_raw', pd.DataFrame()),
        kw_raw=out.get('kw_raw', pd.DataFrame()),
        pm_raw=out.get('pm_raw', pd.DataFrame()),
    )
    out['conv_day']  = conv_day
    out['conv_week'] = conv_week
    # 向後相容舊的 conv_raw key
    out['conv_raw']  = conv_week

    out['meta'] = _build_meta(out)
    return out


# ── 進件明細處理（新格式：工作表1）─────────────────────
def _load_conv_detail(df: pd.DataFrame, asa_raw: pd.DataFrame,
                      kw_raw: pd.DataFrame, pm_raw: pd.DataFrame):
    """
    從工作表1明細計算天/週維度的進件/開戶報表，並 join 廣告花費。

    平台對應規則：
      01-Google廣告 → 花費 = KW + PMax（按各廣告名稱比例分配）
      03-APP廣告    → 花費 = ASA

    廣告名稱對應（conv 廣告 → 媒體廣告活動）：
      手動定義 mapping，找不到的廣告花費設為 0
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # 判斷是新格式（工作表1）還是舊格式
    if '開戶狀態' in df.columns and '人數' in df.columns:
        return _process_new_conv(df, asa_raw, kw_raw, pm_raw)
    else:
        return _process_old_conv(df)


def _process_new_conv(df: pd.DataFrame, asa_raw: pd.DataFrame,
                      kw_raw: pd.DataFrame, pm_raw: pd.DataFrame):
    """處理新格式（工作表1）進件明細"""
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    df['人數'] = pd.to_numeric(df['人數'], errors='coerce').fillna(0)

    # 建立天維度進件/開戶
    grp_cols = ['date_str', 'date', 'week', '平台', '廣告']

    # 進件數 = 所有狀態人數總和
    jin_day = df.groupby(grp_cols)['人數'].sum().rename('進件數').reset_index()

    # 開戶數 = 開戶已完成人數
    wan_mask = df['開戶狀態'] == '開戶已完成'
    wan_day = df[wan_mask].groupby(grp_cols)['人數'].sum().rename('開戶數').reset_index()

    day = jin_day.merge(wan_day, on=grp_cols, how='left').fillna({'開戶數': 0})
    day['開戶率%'] = day.apply(lambda r: sdiv(r['開戶數'], r['進件數'], 100, 1), axis=1)

    # 建立天維度花費（從廣告 raw 資料按平台+日期彙總）
    spend_day = _build_spend_by_ad_day(asa_raw, kw_raw, pm_raw)
    if not spend_day.empty:
        day = day.merge(spend_day, on=['date_str', '廣告'], how='left').fillna(
            {'spend': 0, 'imp': 0, 'clk': 0})
    else:
        day['spend'] = 0; day['imp'] = 0; day['clk'] = 0

    day['進件成本'] = day.apply(lambda r: sdiv(r['spend'], r['進件數'], 1, 0), axis=1)
    day['開戶成本'] = day.apply(lambda r: sdiv(r['spend'], r['開戶數'], 1, 0), axis=1)
    day = day.sort_values(['date_str', '平台', '廣告'])

    # 週維度：從天資料彙總
    week_grp = ['week', '平台', '廣告']
    week = day.groupby(week_grp).agg(
        進件數=('進件數', 'sum'),
        開戶數=('開戶數', 'sum'),
        spend=('spend', 'sum'),
        imp=('imp', 'sum'),
        clk=('clk', 'sum'),
    ).reset_index()
    week['開戶率%'] = week.apply(lambda r: sdiv(r['開戶數'], r['進件數'], 100, 1), axis=1)
    week['進件成本'] = week.apply(lambda r: sdiv(r['spend'], r['進件數'], 1, 0), axis=1)
    week['開戶成本'] = week.apply(lambda r: sdiv(r['spend'], r['開戶數'], 1, 0), axis=1)
    # 加上週起訖日期
    week['start_date'] = week['week'].apply(lambda w: parse_week_range(w)[0])
    week['end_date']   = week['week'].apply(lambda w: parse_week_range(w)[1])
    week = week.sort_values(['week', '平台', '廣告'])

    return day, week


def _build_spend_by_ad_day(asa_raw, kw_raw, pm_raw):
    """
    建立「廣告名稱」→「天花費/曝光/點擊」的對照表。
    KW 和 PMax 完全分開對應，ASA 依台股/美股分開。

    KW 廣告活動對應：
      MKUS01_關鍵字_0916_品牌字              → Google關鍵字_台美股_品牌字
      MKADCH CHBG12_關鍵字_1015_郵局字       → Google關鍵字_郵局_郵局字
      MKADGO CHBG01/02_關鍵字_1218_投資入門字 → Google關鍵字_投資入門_ETF/存股字
      其他含「品牌字」                         → Google關鍵字_台美股_品牌字

    PMax：
      全部 PMax 活動 → Google PMAX_台美股
      （Google PMAX_郵局 目前 raw 無對應，花費顯示 0）

    ASA：
      含「台股」 → ASA_台股APP iOS 登入頁 開戶按鈕
      其他       → ASA_美股APP iOS 登入頁 開戶按鈕
    """
    records = []

    # ---- Google KW（精確 mapping）----
    KW_MAP = {
        'MKUS01_關鍵字_0916_品牌字':               'Google關鍵字_台美股_品牌字',
        'MKADCH CHBG12_關鍵字_1015_郵局字':        'Google關鍵字_郵局_郵局字',
        'MKADGO CHBG01/02_關鍵字_1218_投資入門字': 'Google關鍵字_投資入門_ETF/存股字',
    }
    if not kw_raw.empty:
        kw = kw_raw.copy()
        def kw_ad_map(camp):
            # 精確 mapping 優先
            if camp in KW_MAP:
                return KW_MAP[camp]
            camp_u = str(camp).upper()
            if '郵局' in camp_u: return 'Google關鍵字_郵局_郵局字'
            if '投資入門' in camp_u: return 'Google關鍵字_投資入門_ETF/存股字'
            if '美股' in camp_u: return 'Google關鍵字_美股_品牌字'
            return 'Google關鍵字_台美股_品牌字'
        kw['廣告'] = kw['廣告活動'].apply(kw_ad_map)
        kw_spend = kw.groupby(['date_str', '廣告']).agg(
            spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
        ).reset_index()
        records.append(kw_spend)

    # ---- Google PMax（全部歸台美股，郵局 raw 無對應）----
    if not pm_raw.empty:
        pm = pm_raw.copy()
        pm['廣告'] = 'Google PMAX_台美股'
        pm_spend = pm.groupby(['date_str', '廣告']).agg(
            spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
        ).reset_index()
        records.append(pm_spend)

    # ---- ASA（台股/美股分開）----
    if not asa_raw.empty:
        asa = asa_raw.copy()
        def asa_ad_map(camp):
            camp_s = str(camp)
            if '台股' in camp_s or ('台' in camp_s and '美' not in camp_s):
                return 'ASA_台股APP iOS 登入頁 開戶按鈕'
            return 'ASA_美股APP iOS 登入頁 開戶按鈕'
        asa['廣告'] = asa['廣告活動'].apply(asa_ad_map)
        asa_spend = asa.groupby(['date_str', '廣告']).agg(
            spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
        ).reset_index()
        records.append(asa_spend)

    if not records:
        return pd.DataFrame()

    result = pd.concat(records, ignore_index=True)
    result = result.groupby(['date_str', '廣告']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()
    return result


def _process_old_conv(df: pd.DataFrame):
    """舊格式（進件數完開數）相容處理"""
    df = df.copy().dropna(subset=['Week', '平台'])
    records = []
    for _, row in df.iterrows():
        ws = str(row.get('Week', ''))
        start, end = parse_week_range(ws)
        if start is None:
            continue
        records.append({
            'week':      ws,
            '平台':       str(row.get('平台', '')),
            '廣告':       str(row.get('廣告活動', '')),
            'start_date': start,
            'end_date':   end,
            '進件數':     pd.to_numeric(row.get('進件數', 0), errors='coerce') or 0,
            '開戶數':     pd.to_numeric(row.get('完開數', 0), errors='coerce') or 0,
            'spend':     pd.to_numeric(row.get('花費', 0), errors='coerce') or 0,
            '進件成本':   pd.to_numeric(row.get('進件成本', 0), errors='coerce') or 0,
            '開戶成本':   pd.to_numeric(row.get('完開成本', 0), errors='coerce') or 0,
            '開戶率%':    pd.to_numeric(row.get('完開率', 0), errors='coerce') or 0,
            'imp': 0, 'clk': 0,
        })
    week = pd.DataFrame(records) if records else pd.DataFrame()
    return pd.DataFrame(), week  # 舊格式沒有天維度


# ── ASA ───────────────────────────────────────────────
def _load_asa(df: pd.DataFrame) -> dict:
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

    daily = df.groupby(['date_str', 'date']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()

    camp = df.groupby('廣告活動').agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()
    for col in ['jin','wan','shidong']:
        camp[col] = 0.0
    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPI']    = camp.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    camp['CPL']    = 0.0
    camp['進件率%'] = 0.0
    camp['完開率%'] = 0.0

    kw = df.groupby(['廣告活動','廣告群組','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum'), dl=('dl','sum')
    ).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPI']  = kw.apply(lambda r: sdiv(r['spend'], r['dl'], 1, 0), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'asa_daily': daily, 'asa_camp': camp, 'asa_kw': kw, 'asa_raw': df}


# ── Google KW ─────────────────────────────────────────
def _load_kw(df: pd.DataFrame) -> dict:
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
    for col in ['jin','wan','shidong']:
        camp[col] = 0.0
    camp['CTR%']   = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']    = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']    = 0.0
    camp['進件率%'] = 0.0
    camp['完開率%'] = 0.0

    kw = df.groupby(['camp_short','廣告關鍵字']).agg(
        spend=('spend','sum'), imp=('imp','sum'), clk=('clk','sum')
    ).reset_index()
    kw['CTR%'] = kw.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    kw['CPC']  = kw.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    kw = kw.sort_values('spend', ascending=False)

    return {'kw_daily': daily, 'kw_camp': camp, 'kw_kw': kw, 'kw_raw': df}


# ── Google PMax ───────────────────────────────────────
def _load_pmax(df: pd.DataFrame) -> dict:
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
    for col in ['jin','wan','shidong']:
        camp[col] = 0.0
    camp['CTR%']  = camp.apply(lambda r: sdiv(r['clk'], r['imp'], 100), axis=1)
    camp['CPC']   = camp.apply(lambda r: sdiv(r['spend'], r['clk'], 1, 1), axis=1)
    camp['CPL']   = 0.0
    camp['完開率%'] = 0.0

    return {'pm_daily': daily, 'pm_camp': camp, 'pm_raw': df}


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


# ── 週報表組合（PMax 合計行 + 子行）────────────────────
def build_conv_report(conv_week: pd.DataFrame, by: str = 'week') -> pd.DataFrame:
    """
    將 conv_week 整理成週報表格式：
    - PMax 新增「合計行」（曝光/點擊/花費加總，進件/開戶/開戶率加總）
    - PMax 各子廣告保留進件/開戶/開戶率，曝光/點擊/花費顯示空白
    - 其他廣告照原樣

    排序：PMax合計 → PMax子行 → KW各行 → ASA各行
    """
    if conv_week.empty:
        return pd.DataFrame()

    pmax_mask = conv_week['廣告'].str.startswith('Google PMAX', na=False)
    pmax_rows = conv_week[pmax_mask].copy()
    non_pmax  = conv_week[~pmax_mask].copy()

    grp_col = by  # 'week'
    results = []

    # PMax 合計行
    if not pmax_rows.empty:
        agg = pmax_rows.groupby(grp_col).agg(
            imp=('imp','sum'), clk=('clk','sum'), spend=('spend','sum'),
            進件數=('進件數','sum'), 開戶數=('開戶數','sum')
        ).reset_index()
        agg['廣告']   = 'Google PMax（合計）'
        agg['平台']   = '01-Google廣告'
        agg['開戶率%'] = agg.apply(lambda r: sdiv(r['開戶數'], r['進件數'], 100, 1), axis=1)
        agg['進件成本'] = agg.apply(lambda r: sdiv(r['spend'], r['進件數'], 1, 0), axis=1)
        agg['開戶成本'] = agg.apply(lambda r: sdiv(r['spend'], r['開戶數'], 1, 0), axis=1)
        agg['_sort'] = 0
        results.append(agg)

        # PMax 子行（曝光/點擊/花費空白，但進件成本/開戶成本用合計花費按進件比例分配）
        sub = pmax_rows.copy()
        sub['imp']   = None
        sub['clk']   = None
        sub['spend'] = None
        # 取各週 PMax 合計花費
        week_spend = agg.set_index(grp_col)['spend'].to_dict()
        def _cost(row, metric):
            total_spend = week_spend.get(row[grp_col], 0)
            val = row.get(metric, 0) or 0
            return sdiv(total_spend, val, 1, 0) if val > 0 else None
        sub['進件成本'] = sub.apply(lambda r: _cost(r, '進件數'), axis=1)
        sub['開戶成本'] = sub.apply(lambda r: _cost(r, '開戶數'), axis=1)
        sub['_sort'] = 1
        results.append(sub)

    # 非 PMax 行
    if not non_pmax.empty:
        non_pmax['_sort'] = 2
        results.append(non_pmax)

    df = pd.concat(results, ignore_index=True)
    df = df.sort_values([grp_col, '_sort', '廣告']).drop(columns=['_sort'])
    return df


def build_conv_report_day(conv_day: pd.DataFrame) -> pd.DataFrame:
    """天維度的同樣邏輯"""
    if conv_day.empty:
        return pd.DataFrame()

    pmax_mask = conv_day['廣告'].str.startswith('Google PMAX', na=False)
    pmax_rows = conv_day[pmax_mask].copy()
    non_pmax  = conv_day[~pmax_mask].copy()

    results = []
    if not pmax_rows.empty:
        agg = pmax_rows.groupby('date_str').agg(
            imp=('imp','sum'), clk=('clk','sum'), spend=('spend','sum'),
            進件數=('進件數','sum'), 開戶數=('開戶數','sum')
        ).reset_index()
        agg['廣告']   = 'Google PMax（合計）'
        agg['平台']   = '01-Google廣告'
        agg['開戶率%'] = agg.apply(lambda r: sdiv(r['開戶數'], r['進件數'], 100, 1), axis=1)
        agg['進件成本'] = agg.apply(lambda r: sdiv(r['spend'], r['進件數'], 1, 0), axis=1)
        agg['開戶成本'] = agg.apply(lambda r: sdiv(r['spend'], r['開戶數'], 1, 0), axis=1)
        agg['_sort'] = 0
        results.append(agg)

        sub = pmax_rows.copy()
        sub['imp'] = None; sub['clk'] = None; sub['spend'] = None
        # 天維度的 PMax 合計花費
        day_spend = agg.set_index('date_str')['spend'].to_dict()
        sub['進件成本'] = sub.apply(lambda r: sdiv(day_spend.get(r['date_str'], 0), r['進件數'], 1, 0) if (r.get('進件數') or 0) > 0 else None, axis=1)
        sub['開戶成本'] = sub.apply(lambda r: sdiv(day_spend.get(r['date_str'], 0), r['開戶數'], 1, 0) if (r.get('開戶數') or 0) > 0 else None, axis=1)
        sub['_sort'] = 1
        results.append(sub)

    if not non_pmax.empty:
        non_pmax['_sort'] = 2
        results.append(non_pmax)

    df = pd.concat(results, ignore_index=True)
    df = df.sort_values(['date_str', '_sort', '廣告']).drop(columns=['_sort'])
    return df


# ── 日期範圍篩選 ──────────────────────────────────────
def filter_dates(df: pd.DataFrame, date_col: str, start: str, end: str) -> pd.DataFrame:
    """依手動選擇的日期範圍篩選"""
    if df.empty or not start or not end:
        return df
    return df[(df[date_col] >= start) & (df[date_col] <= end)].copy()
