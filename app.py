"""
K线相似度匹配系统 - 断板版 v1.7
改动：距D1重新分档、断板期中间涨停情况、加分封顶、量能三档扣分调整
"""

import os
import time
import warnings
import pickle
from datetime import datetime
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd
import akshare as ak

warnings.filterwarnings('ignore')

CONFIG = {
    'cache_dir': './stock_cache/',
    'zt_threshold': 0.098,
    'dt_threshold': -0.098,
    'volume_lookback': 3,
    'bad_board_volume_multiple': 3,
    'request_interval': 0.3,
    'max_retries': 3,
    'top_n': 50,

    'break_window_low': 10,
    'break_window_mid': 20,
    'break_window_high': 30,
    'cold_gap_max': 3,

    'combined_height_low': 0.40,
    'combined_height_high': 1.00,
    'combined_height_very_high': 2.00,

    'break_period_pct_high': 0.10,
    'break_period_pct_low': -0.10,

    'big_leg_threshold': 0.095,
    'dtb_amplitude_threshold': 0.16,

    'big_yang_threshold': 0.05,
    'big_yin_threshold': -0.05,
    'low_open_threshold': -0.03,
    'high_open_threshold': 0.03,
    'body_pct_threshold': 0.05,
    'long_shadow_threshold': 0.05,
    'small_body_threshold': 0.03,

    'low_open_high_walk_fix': -0.03,
    'high_open_low_walk_fix': 0.03,

    'small_yang_threshold': 0.02,
    'small_yin_threshold': -0.02,
    'cross_star_pct': 0.02,
    'cross_star_amplitude': 0.03,

    'downgrade_threshold': 30,
    'penalty_a_class': 10,

    'penalty_b_class': 5,
    'penalty_break_count': 20,
    'penalty_break_days': 10,
    'penalty_break_pct_1': 15,
    'penalty_break_pct_2': 25,
    'penalty_d2_emotion_mismatch': 8,
    'penalty_special_count_per': 3,

    'penalty_rise_cross_1': 20,
    'penalty_rise_cross_2': 30,

    'zt_seg_cap_short': 45,
    'zt_seg_cap_mid': 30,
    'zt_seg_cap_long': 15,

    'penalty_d3_mismatch': 10,
    'bonus_d3_exact': 5,
    'bonus_d3_both_none': 1,

    'bonus_d1_exact': 6,
    'bonus_d1_same_emotion': 3,
    'bonus_d2_exact': 5,
    'bonus_d2_same_emotion': 2,

    'bonus_touch_zt_match': 5,
    'bonus_touch_dt_match': 5,

    'bonus_micro_zt_exact': 5,
    'bonus_micro_zt_compat': 3,
    'bonus_micro_zt_both_none': 5,
    'bonus_micro_mid_special_exact': 5,
    'bonus_micro_mid_special_approx': 3,
    'bonus_micro_mid_both_none': 3,
    'penalty_micro_mid_mismatch': 10,
    'bonus_micro_pre_exact': 5,
    'bonus_micro_pre_cold': 3,
    'bonus_micro_pre_approx': 3,
    'penalty_micro_pre_mismatch': 15,
    'bonus_micro_cut_exact': 15,
    'bonus_micro_cut_approx': 3,
    'penalty_micro_cut_mismatch': 20,

    'bonus_micro_pre_prev_exact': 3,
    'bonus_micro_pre_prev_approx': 2,

    'penalty_wave_mismatch': 15,

    'severe_drawdown_threshold': 0.20,
    'severe_form_count': 3,
    'severe_pct_threshold': 0.20,

    'height_retracement_1': 0.10,
    'height_retracement_2': 0.25,

    'density_pct_threshold': 0.10,

    'max_rise_lookback': 30,

    'wave_significant_threshold': -0.15,

    'max_penalty_threshold': 999,
    'distance_multiplier': 10,
    'distance_top_n': 30,

    'upper_shadow_strong_threshold': 0.05,
    'lower_shadow_weak_threshold': -0.05,

    'bonus_cap': 40,

    'penalty_mid_zt_mismatch': 10,

    'penalty_d1_days_per': 5,
    'penalty_d1_days_cap': 15,

    'case_library_cache': './stock_cache/case_library_break_v17.pkl',
    'worker_count': max(1, cpu_count() - 1),
}

os.makedirs(CONFIG['cache_dir'], exist_ok=True)

EMOTION_STRONG_FORMS = {'一字板', 'T字板', '地天板', '大长腿涨停', '秒板', '普通涨停',
                        '大阳线', '低开高走'}
EMOTION_WEAK_FORMS = {'一字跌停', '倒T字跌停', '天地板', '大长腿跌停', '秒跌停', '普通跌停',
                      '大阴线', '高开低走'}
EMOTION_NEUTRAL_FORMS = {'十字星', '普通K线', '小阳线', '小阴线'}

SEVERE_BREAK_FORMS = {'一字跌停', '倒T字跌停', '天地板', '大长腿跌停', '秒跌停', '普通跌停',
                      '大阴线', '高开低走'}
COLD_FORMS = {'普通K线', '十字星', '小阳线', '小阴线'}

BIG_UP_FORMS = {'一字板', 'T字板', '地天板', '大长腿涨停', '秒板', '普通涨停',
                '大阳线', '低开高走', '长下影'}
BIG_DOWN_FORMS = {'一字跌停', '倒T字跌停', '天地板', '大长腿跌停', '秒跌停', '普通跌停',
                  '大阴线', '高开低走', '长上影'}


def get_emotion(form, pct=0.0):
    if form == '长上影':
        if pct > CONFIG['upper_shadow_strong_threshold']:
            return '强势'
        elif pct < 0:
            return '弱势'
        return '震荡'
    elif form == '长下影':
        if pct > 0:
            return '强势'
        elif pct < CONFIG['lower_shadow_weak_threshold']:
            return '弱势'
        return '震荡'
    elif form in EMOTION_STRONG_FORMS:
        return '强势'
    elif form in EMOTION_WEAK_FORMS:
        return '弱势'
    return '震荡'


def get_subdivision(form, volume=None, prev_volume=None, pct=0.0):
    is_shrink = (volume is not None and prev_volume is not None
                 and prev_volume > 0 and volume < prev_volume)
    if form == '一字板':
        return '一字涨停'
    if form in ('T字板', '秒板'):
        return '加速涨停' if is_shrink else '其他涨停'
    if form in ('地天板', '大长腿涨停', '普通涨停'):
        return '其他涨停'
    if form == '一字跌停':
        return '一字跌停'
    if form in ('倒T字跌停', '秒跌停'):
        return '加速跌停' if is_shrink else '其他跌停'
    if form in ('天地板', '大长腿跌停', '普通跌停'):
        return '其他跌停'
    if form in ('大阳线', '低开高走'):
        return '大阳线'
    if form in ('大阴线', '高开低走'):
        return '大阴线'
    if form == '小阳线':
        return '小阳线'
    if form == '小阴线':
        return '小阴线'
    if form == '长上影':
        if pct > CONFIG['upper_shadow_strong_threshold']:
            return '强势长上影'
        elif pct < 0:
            return '弱势长上影'
        return '震荡长上影'
    if form == '长下影':
        if pct > 0:
            return '强势长下影'
        elif pct < CONFIG['lower_shadow_weak_threshold']:
            return '弱势长下影'
        return '震荡长下影'
    return '震荡'


def get_approx_group(subdivision):
    if subdivision in ('一字涨停', '加速涨停', '其他涨停'):
        return '涨停类'
    if subdivision in ('一字跌停', '加速跌停', '其他跌停'):
        return '跌停类'
    if subdivision in ('大阳线', '小阳线', '强势长下影', '强势长上影'):
        return '阳线类'
    if subdivision in ('大阴线', '小阴线', '弱势长下影', '弱势长上影'):
        return '阴线类'
    if subdivision in ('震荡长上影', '震荡长下影'):
        return '影线类'
    return '震荡类'


def match_subdivision(sub1, sub2):
    return sub1 == sub2


def match_approx(sub1, sub2):
    return get_approx_group(sub1) == get_approx_group(sub2)


def match_emotion(emo1, emo2):
    if emo1 == emo2:
        return True
    if emo1 == '震荡' or emo2 == '震荡':
        return True
    return False


def get_simplified_form(form, volume=None, prev_volume=None, pct=0.0):
    return get_subdivision(form, volume, prev_volume, pct)


def get_main_board_stock_list():
    print("正在获取股票列表...")
    si = ak.stock_info_a_code_name()
    m = si['code'].str.match(r'^(600|601|603|000|001|002|003)')
    s = ~si['name'].str.contains('ST', case=False, na=False)
    r = si[m & s].reset_index(drop=True)
    print(f"筛选完成，共 {len(r)} 只主板非ST股票")
    return r


def code_to_tencent_symbol(code):
    return f"sh{code}" if code.startswith(('600', '601', '603')) else f"sz{code}"


def get_daily_data(stock_code, start_date, end_date, max_retries=3):
    cf = os.path.join(CONFIG['cache_dir'], f"daily_{stock_code}_{start_date}_{end_date}.pkl")
    if os.path.exists(cf):
        try:
            with open(cf, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    symbol = code_to_tencent_symbol(stock_code)
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date,
                                     end_date=end_date, adjust="")
            if df is not None and len(df) > 0:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                with open(cf, 'wb') as f:
                    pickle.dump(df, f)
                return df
            return None
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1 + attempt * 2)
    return None


def batch_download_daily_data(stock_list, start_date, end_date):
    all_data = {}
    total = len(stock_list)
    success = failed = from_cache = 0
    print(f"开始加载日K数据，共 {total} 只股票...")
    st = time.time()
    for i, row in stock_list.iterrows():
        code = row['code']
        cf = os.path.join(CONFIG['cache_dir'], f"daily_{code}_{start_date}_{end_date}.pkl")
        cached = os.path.exists(cf)
        df = get_daily_data(code, start_date, end_date, max_retries=CONFIG['max_retries'])
        if df is not None and len(df) > 0:
            all_data[code] = df
            success += 1
            if cached:
                from_cache += 1
        else:
            failed += 1
        if (i + 1) % 200 == 0 or (i + 1) == total:
            print(f"  {i + 1}/{total} ({(i + 1) / total * 100:.1f}%) | "
                  f"成功{success}(缓存{from_cache}) | 失败{failed} | {time.time() - st:.1f}秒")
        if not cached:
            time.sleep(CONFIG['request_interval'])
    print(f"\n加载完成，成功{success}（缓存{from_cache}）/ 失败{failed}")
    return all_data


def precompute_stock_data(daily_df):
    df = daily_df.copy()
    n = len(df)
    if n == 0:
        return []
    dates = df['date'].values
    opens = df['open'].values.astype(float)
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    volumes = df['volume'].values.astype(float)

    pre_closes = np.empty(n, dtype=float)
    pre_closes[0] = np.nan
    pre_closes[1:] = closes[:-1]

    with np.errstate(divide='ignore', invalid='ignore'):
        pcts = np.where(pre_closes > 0, (closes - pre_closes) / pre_closes, 0.0)
        open_pcts = np.where(pre_closes > 0, (opens - pre_closes) / pre_closes, 0.0)
        body_pcts = np.where(pre_closes > 0, (closes - opens) / pre_closes, 0.0)
        amplitudes = np.where(pre_closes > 0, (highs - lows) / pre_closes, 0.0)
        upper_shadows = np.where(pre_closes > 0,
                                 (highs - np.maximum(opens, closes)) / pre_closes, 0.0)
        lower_shadows = np.where(pre_closes > 0,
                                 (np.minimum(opens, closes) - lows) / pre_closes, 0.0)

    zt_prices = np.round(pre_closes * 1.1, 2)
    dt_prices = np.round(pre_closes * 0.9, 2)
    is_zt = pcts >= CONFIG['zt_threshold']
    is_dt = pcts <= CONFIG['dt_threshold']

    vl = CONFIG['volume_lookback']
    vol_labels = np.zeros(n, dtype=int)  # 0=放量, 1=平量, 2=缩量
    for i in range(vl, n):
        avg = volumes[i - vl:i].mean()
        if avg > 0:
            ratio = volumes[i] / avg
            if ratio < 0.8:
                vol_labels[i] = 2  # 缩量
            elif ratio <= 1.5:
                vol_labels[i] = 1  # 平量
            else:
                vol_labels[i] = 0  # 放量

    board_strengths = [''] * n
    for i in range(n):
        if not is_zt[i]:
            board_strengths[i] = '非涨停'
            continue
        if abs(opens[i] - zt_prices[i]) < 0.01 and abs(closes[i] - zt_prices[i]) < 0.01:
            board_strengths[i] = '一字'
            continue
        avg_v = volumes[i] if i < vl else volumes[i - vl:i].mean()
        if avg_v == 0:
            board_strengths[i] = '换手'
        else:
            ratio = volumes[i] / avg_v
            if ratio < 1.0:
                board_strengths[i] = '硬板'
            elif ratio < CONFIG['bad_board_volume_multiple']:
                board_strengths[i] = '换手'
            else:
                board_strengths[i] = '烂板'

    touched_zt = np.zeros(n, dtype=bool)
    touched_dt = np.zeros(n, dtype=bool)
    for i in range(n):
        if not is_zt[i] and not np.isnan(zt_prices[i]) and zt_prices[i] > 0:
            if highs[i] >= zt_prices[i] - 0.01:
                touched_zt[i] = True
        if not is_dt[i] and not np.isnan(dt_prices[i]) and dt_prices[i] > 0:
            if lows[i] <= dt_prices[i] + 0.01:
                touched_dt[i] = True

    forms = [''] * n
    for i in range(n):
        if np.isnan(pre_closes[i]) or pre_closes[i] == 0:
            forms[i] = '小阳线'
            continue
        if is_zt[i]:
            op, cl, lo, hi = opens[i], closes[i], lows[i], highs[i]
            zp, pc = zt_prices[i], pre_closes[i]
            if abs(op - zp) < 0.01 and abs(cl - zp) < 0.01 and abs(lo - zp) < 0.01:
                forms[i] = '一字板'
            elif (hi - lo) / pc > CONFIG['dtb_amplitude_threshold']:
                forms[i] = '地天板'
            elif (cl - op) / pc > CONFIG['big_leg_threshold']:
                forms[i] = '大长腿涨停'
            elif (op - pc) / pc >= 0.075 and (hi - lo) / pc > 0.098:
                forms[i] = '大长腿涨停'
            elif (abs(op - zp) < 0.01 and abs(cl - zp) < 0.01
                  and lo < zp - 0.01 and (hi - lo) / pc > 0.098):
                forms[i] = '大长腿涨停'
            elif abs(op - zp) < 0.01 and abs(cl - zp) < 0.01 and lo < zp - 0.01:
                forms[i] = 'T字板'
            elif (op - pc) / pc >= 0.075:
                forms[i] = '秒板'
            else:
                forms[i] = '普通涨停'
        elif is_dt[i]:
            op, cl, lo, hi = opens[i], closes[i], lows[i], highs[i]
            dp, pc = dt_prices[i], pre_closes[i]
            if abs(op - dp) < 0.01 and abs(cl - dp) < 0.01 and abs(hi - dp) < 0.01:
                forms[i] = '一字跌停'
            elif (hi - lo) / pc > CONFIG['dtb_amplitude_threshold']:
                forms[i] = '天地板'
            elif (op - cl) / pc > CONFIG['big_leg_threshold']:
                forms[i] = '大长腿跌停'
            elif (op - pc) / pc <= -0.075 and (hi - lo) / pc > 0.098:
                forms[i] = '大长腿跌停'
            elif (abs(op - dp) < 0.01 and abs(cl - dp) < 0.01
                  and hi > dp + 0.01 and (hi - lo) / pc > 0.098):
                forms[i] = '大长腿跌停'
            elif abs(op - dp) < 0.01 and abs(cl - dp) < 0.01 and hi > dp + 0.01:
                forms[i] = '倒T字跌停'
            elif (op - pc) / pc <= -0.075:
                forms[i] = '秒跌停'
            else:
                forms[i] = '普通跌停'
        else:
            p_i, op_i = pcts[i], open_pcts[i]
            bp_i, am_i = body_pcts[i], amplitudes[i]
            us_i, ls_i = upper_shadows[i], lower_shadows[i]
            if p_i > CONFIG['big_yang_threshold']:
                forms[i] = '大阳线'
            elif p_i < CONFIG['big_yin_threshold']:
                forms[i] = '大阴线'
            elif op_i < CONFIG['low_open_threshold'] and bp_i > CONFIG['body_pct_threshold']:
                if p_i < CONFIG['low_open_high_walk_fix']:
                    forms[i] = '小阴线'
                else:
                    forms[i] = '低开高走'
            elif op_i > CONFIG['high_open_threshold'] and bp_i < -CONFIG['body_pct_threshold']:
                if p_i > CONFIG['high_open_low_walk_fix']:
                    forms[i] = '小阳线'
                else:
                    forms[i] = '高开低走'
            elif us_i > CONFIG['long_shadow_threshold'] and abs(bp_i) < CONFIG['small_body_threshold']:
                forms[i] = '长上影'
            elif ls_i > CONFIG['long_shadow_threshold'] and abs(bp_i) < CONFIG['small_body_threshold']:
                forms[i] = '长下影'
            elif abs(p_i) < CONFIG['cross_star_pct'] and am_i < CONFIG['cross_star_amplitude']:
                forms[i] = '十字星'
            elif p_i >= CONFIG['small_yang_threshold'] or (p_i >= 0 and am_i >= CONFIG['cross_star_amplitude']):
                forms[i] = '小阳线'
            elif p_i <= CONFIG['small_yin_threshold'] or (p_i < 0 and am_i >= CONFIG['cross_star_amplitude']):
                forms[i] = '小阴线'
            else:
                forms[i] = '十字星'

    emotions = []
    subdivisions = []
    for i in range(n):
        emotions.append(get_emotion(forms[i], pcts[i]))
        prev_vol = volumes[i - 1] if i > 0 else None
        subdivisions.append(get_subdivision(forms[i], volumes[i], prev_vol, pcts[i]))

    rows = []
    for i in range(n):
        rows.append({
            'date': dates[i], 'open': opens[i], 'close': closes[i],
            'high': highs[i], 'low': lows[i], 'volume': volumes[i],
            'pre_close': pre_closes[i], 'pct': pcts[i], 'open_pct': open_pcts[i],
            'body_pct': body_pcts[i], 'amplitude': amplitudes[i],
            'zt_price': zt_prices[i], 'dt_price': dt_prices[i],
            'is_zt': is_zt[i], 'is_dt': is_dt[i],
            'vol_label': vol_labels[i], 'board_strength': board_strengths[i],
            'touched_zt': touched_zt[i], 'touched_dt': touched_dt[i],
            'form': forms[i], 'emotion': emotions[i],
            'subdivision': subdivisions[i],
        })
    return rows
def check_break_continuity(rows, bs, be, combined_height=0):
    if combined_height >= CONFIG['combined_height_very_high']:
        return True
    cgm = CONFIG['cold_gap_max']
    cold_streak = 0
    for k in range(bs, be + 1):
        if k < len(rows) and rows[k]['form'] in COLD_FORMS:
            cold_streak += 1
            if cold_streak > cgm:
                return False
        else:
            cold_streak = 0
    return True


def is_severe_break(rows, bp_start, bp_end, cut_idx):
    ae = min(bp_end, cut_idx)
    consecutive_dt = 0
    for k in range(bp_start, ae + 1):
        if k < len(rows) and rows[k]['is_dt']:
            consecutive_dt += 1
            if consecutive_dt >= 2:
                return True
        else:
            consecutive_dt = 0
    ph, mdd = 0, 0
    for k in range(bp_start, ae + 1):
        if k >= len(rows):
            break
        h, l = rows[k]['high'], rows[k]['low']
        if h > ph:
            ph = h
        if ph > 0:
            dd = (ph - l) / ph
            if dd > mdd:
                mdd = dd
    cond1 = mdd > CONFIG['severe_drawdown_threshold']
    sc = sum(1 for k in range(bp_start, ae + 1)
             if k < len(rows) and rows[k]['form'] in SEVERE_BREAK_FORMS)
    cond2 = sc >= CONFIG['severe_form_count']
    pc = rows[bp_start - 1]['close'] if bp_start > 0 else rows[bp_start]['close']
    mc = min((rows[k]['close'] for k in range(bp_start, ae + 1) if k < len(rows)), default=pc)
    cond3 = (pc - mc) / pc > CONFIG['severe_pct_threshold'] if pc > 0 else False
    return (cond1 or cond2) and cond3


def find_main_break(rows, break_periods, cut_idx):
    vbps = [(i, bp) for i, bp in enumerate(break_periods) if bp[0] <= cut_idx]
    if not vbps:
        return None, False
    for i, bp in reversed(vbps):
        if is_severe_break(rows, bp[0], bp[1], cut_idx):
            return i, True
    return vbps[-1][0], False


def find_break_sequences(rows):
    n = len(rows)
    if n < 3:
        return []
    results = []
    i = 0
    while i < n:
        if not rows[i]['is_zt']:
            i += 1
            continue
        fzs = i
        while i < n and rows[i]['is_zt']:
            i += 1
        fze = i - 1
        if fze - fzs + 1 < 2:
            continue
        fc = rows[fzs]['pre_close']
        if fc == 0 or np.isnan(fc):
            continue
        ce = fze
        segs = [(fzs, fze)]
        bps = []
        while ce < n - 1:
            cc = rows[ce]['close']
            ch = (cc - fc) / fc
            mw = CONFIG['break_window_high'] if ch >= CONFIG['combined_height_high'] else \
                CONFIG['break_window_mid'] if ch >= CONFIG['combined_height_low'] else \
                CONFIG['break_window_low']
            bs = ce + 1
            if bs >= n:
                break
            if rows[bs]['is_zt']:
                ss = bs
                while bs < n and rows[bs]['is_zt']:
                    bs += 1
                segs[-1] = (segs[-1][0], bs - 1)
                ce = bs - 1
                continue
            j, bdc = bs, 0
            while j < n and not rows[j]['is_zt']:
                bdc += 1
                j += 1
                if bdc > mw:
                    break
            if bdc > mw:
                bps.append((bs, min(bs + mw - 1, n - 1)))
                break
            if j >= n:
                bps.append((bs, n - 1))
                break
            if rows[j]['is_zt']:
                be = j - 1
                if not check_break_continuity(rows, bs, be, ch):
                    break
                bps.append((bs, be))
                nss = j
                while j < n and rows[j]['is_zt']:
                    j += 1
                segs.append((nss, j - 1))
                ce = j - 1
            else:
                break
        if bps:
            tz = sum(e - s + 1 for s, e in segs)
            hl = any((e - s + 1) >= 2 for s, e in segs)
            if tz >= 2 and hl:
                se = max(segs[-1][1], bps[-1][1])
                results.append({'seq_start': segs[0][0], 'seq_end': se,
                                'segments': segs, 'break_periods': bps, 'total_zt_days': tz})
    return results


def classify_break_period_days(days):
    if days <= 1:
        return '1天'
    elif days <= 3:
        return '2~3天'
    elif days <= 10:
        return '3~10天'
    return '超10天'


def classify_cut_to_d1(days):
    """距D1天数分档（v1.7新4档）"""
    if days <= 1:
        return '1天'
    elif days <= 3:
        return '2~3天'
    elif days <= 7:
        return '4~7天'
    return '>7天'


def get_weight_tier(cut_to_d1_cat):
    if cut_to_d1_cat in ('1天', '2~3天'):
        return 'short'
    elif cut_to_d1_cat == '4~7天':
        return 'mid'
    return 'long'


def get_weight_multiplier(tier, itype):
    m = {'short': {'zt_seg': 1.5, 'break_period': 0.5, 'd1': 1.5},
         'mid': {'zt_seg': 1.0, 'break_period': 1.0, 'd1': 1.0},
         'long': {'zt_seg': 1.0, 'break_period': 1.5, 'd1': 1.0}}
    return m.get(tier, {}).get(itype, 1.0)


def get_zt_seg_cap(tier):
    return CONFIG.get(f'zt_seg_cap_{tier}', CONFIG['zt_seg_cap_mid'])


def calc_special_count_penalty(ts, cs):
    at = set(list(ts.keys()) + list(cs.keys()))
    te = sum(max(0, abs(ts.get(t, 0) - cs.get(t, 0)) - 1) for t in at)
    if te == 0:
        return 0, ''
    p = te * CONFIG['penalty_special_count_per']
    return p, f"数量差异(超{te}个)-{p}"


def classify_density(bu, bd, break_pct=0.0, ztdt_count=0):
    if bu >= 2 and break_pct > CONFIG['density_pct_threshold']:
        return '大涨主导'
    if bd >= 2 and break_pct < -0.15:
        return '大跌主导'
    if break_pct > -0.15 and break_pct <= CONFIG['density_pct_threshold']:
        if (bu >= 3 and bd >= 3) or ztdt_count >= 2:
            return '极端博弈'
    return '冷淡'


def classify_dt_intensity(rows, bs, cut_idx):
    has_dt = False
    max_consecutive = 0
    current_streak = 0
    for k in range(bs, cut_idx):
        if k < len(rows) and rows[k]['is_dt']:
            has_dt = True
            current_streak += 1
            if current_streak > max_consecutive:
                max_consecutive = current_streak
        else:
            current_streak = 0
    if not has_dt:
        return '无跌停'
    elif max_consecutive >= 2:
        return '连跌停'
    else:
        return '单跌停'


DENSITY_MATRIX = {
    ('大涨主导', '大涨主导'): 10, ('大涨主导', '冷淡'): -10,
    ('大涨主导', '极端博弈'): -15, ('大涨主导', '大跌主导'): -20,
    ('冷淡', '大涨主导'): -10, ('冷淡', '冷淡'): 10,
    ('冷淡', '极端博弈'): -10, ('冷淡', '大跌主导'): -10,
    ('极端博弈', '大涨主导'): -15, ('极端博弈', '冷淡'): -10,
    ('极端博弈', '极端博弈'): 10, ('极端博弈', '大跌主导'): -15,
    ('大跌主导', '大涨主导'): -20, ('大跌主导', '冷淡'): -10,
    ('大跌主导', '极端博弈'): -15, ('大跌主导', '大跌主导'): 10,
}


def classify_height_retracement(r):
    if r <= CONFIG['height_retracement_1']:
        return '未回撤'
    elif r <= CONFIG['height_retracement_2']:
        return '小幅回撤'
    return '大幅回撤'


def classify_max_rise(mr):
    if mr >= CONFIG['combined_height_very_high']:
        return '超高位'
    elif mr >= CONFIG['combined_height_high']:
        return '高位'
    elif mr >= CONFIG['combined_height_low']:
        return '中位'
    return '低位'


def classify_mid_zt_type(rows, d1_idx, cut_idx):
    """断板期中间涨停情况（v1.7新增）"""
    if d1_idx is None or cut_idx <= d1_idx + 1:
        return '无涨停'
    zt_indices = []
    for k in range(d1_idx + 1, cut_idx):
        if k < len(rows) and rows[k]['is_zt']:
            zt_indices.append(k)
    if not zt_indices:
        return '无涨停'
    # 检查是否有连板（相邻两个涨停日index差1）
    for i in range(len(zt_indices) - 1):
        if zt_indices[i + 1] - zt_indices[i] == 1:
            return '连板'
    return '不连续涨停'


def build_micro_structure(rows, seq_start, segments, cut_idx):
    cut_form = rows[cut_idx]['form']
    cut_pct = rows[cut_idx]['pct']
    prev_vol = rows[cut_idx - 1]['volume'] if cut_idx > 0 else None
    cut_vol = rows[cut_idx]['volume']
    cut_subdivision = get_subdivision(cut_form, cut_vol, prev_vol, cut_pct)
    cut_emotion = rows[cut_idx]['emotion']

    zt_seg_indices = set()
    for s, e in segments:
        for k in range(s, e + 1):
            zt_seg_indices.add(k)

    nzi = None
    for k in range(cut_idx - 1, seq_start - 1, -1):
        if k >= 0 and rows[k]['is_zt'] and k not in zt_seg_indices:
            nzi = k
            break

    if nzi is not None:
        nzf = rows[nzi]['form']
        nz_prev_vol = rows[nzi - 1]['volume'] if nzi > 0 else None
        nz_subdivision = get_subdivision(nzf, rows[nzi]['volume'], nz_prev_vol, rows[nzi]['pct'])
    else:
        nzf = '无'
        nz_subdivision = '无'

    d1_idx = None
    for s, e in segments:
        if e < cut_idx:
            next_day = e + 1
            if next_day <= cut_idx and not rows[next_day]['is_zt']:
                d1_idx = next_day
    if d1_idx is None:
        last_seg_end = max(e for s, e in segments if e < cut_idx) if segments else seq_start
        if last_seg_end + 1 <= cut_idx:
            d1_idx = last_seg_end + 1

    mid_special_form = '无'
    mid_special_subdivision = '无'
    mid_special_emotion = '震荡'
    mid_type = '无'

    if d1_idx is not None:
        gap_days = cut_idx - d1_idx
    else:
        gap_days = 0

    if gap_days > 1 and d1_idx is not None:
        mid_start = d1_idx + 1
        mid_end = cut_idx - 1
        earliest = max(mid_start, cut_idx - 3)
        if earliest <= mid_end:
            for k in range(mid_end, earliest - 1, -1):
                if k < len(rows) and rows[k]['form'] not in COLD_FORMS:
                    mid_special_form = rows[k]['form']
                    p_v = rows[k - 1]['volume'] if k > 0 else None
                    mid_special_subdivision = get_subdivision(
                        rows[k]['form'], rows[k]['volume'], p_v, rows[k]['pct'])
                    mid_special_emotion = rows[k]['emotion']
                    break
            has_strong = has_weak = False
            for k in range(earliest, mid_end + 1):
                if k < len(rows):
                    emo = rows[k]['emotion']
                    if emo == '强势':
                        has_strong = True
                    elif emo == '弱势':
                        has_weak = True
            if has_strong and has_weak:
                mid_type = '混合型'
            elif has_strong:
                mid_type = '大涨型'
            elif has_weak:
                mid_type = '大跌型'
            else:
                mid_type = '冷淡型'

    ns_form = '无'
    ns_subdivision = '无'
    ns_emotion = '震荡'
    ns_idx = None
    search_start_idx = max(cut_idx - 3, seq_start)
    if d1_idx is not None:
        search_start_idx = max(search_start_idx, d1_idx)
    for k in range(cut_idx - 1, search_start_idx - 1, -1):
        if k < 0:
            break
        if rows[k]['form'] not in COLD_FORMS:
            ns_form = rows[k]['form']
            p_v = rows[k - 1]['volume'] if k > 0 else None
            ns_subdivision = get_subdivision(rows[k]['form'], rows[k]['volume'], p_v, rows[k]['pct'])
            ns_emotion = rows[k]['emotion']
            ns_idx = k
            break
    if ns_form == '无' and gap_days > 0:
        ns_form = '冷淡'
        ns_subdivision = '震荡'
        ns_emotion = '震荡'

    pre_prev_form = '无'
    pre_prev_subdivision = '无'
    pre_prev_emotion = '震荡'
    if ns_idx is not None and ns_idx - 1 >= search_start_idx and ns_idx - 1 >= 0:
        ppk = ns_idx - 1
        if rows[ppk]['form'] not in COLD_FORMS:
            pre_prev_form = rows[ppk]['form']
            pp_v = rows[ppk - 1]['volume'] if ppk > 0 else None
            pre_prev_subdivision = get_subdivision(
                rows[ppk]['form'], rows[ppk]['volume'], pp_v, rows[ppk]['pct'])
            pre_prev_emotion = rows[ppk]['emotion']

    return {
        'nearest_zt_form': nzf, 'nearest_zt_subdivision': nz_subdivision,
        'mid_type': mid_type,
        'mid_special_form': mid_special_form,
        'mid_special_subdivision': mid_special_subdivision,
        'mid_special_emotion': mid_special_emotion,
        'gap_days': gap_days,
        'nearest_special_before_cut': ns_form,
        'nearest_special_subdivision': ns_subdivision,
        'nearest_special_emotion': ns_emotion,
        'pre_prev_form': pre_prev_form,
        'pre_prev_subdivision': pre_prev_subdivision,
        'pre_prev_emotion': pre_prev_emotion,
        'cut_form': cut_form, 'cut_subdivision': cut_subdivision,
        'cut_emotion': cut_emotion,
    }


def build_break_case(stock_code, stock_name, rows, seq_info, cut_idx):
    seq_start = seq_info['seq_start']
    segments = seq_info['segments']
    break_periods = seq_info['break_periods']
    cut_row = rows[cut_idx]
    cut_date = cut_row['date']
    total_days = cut_idx - seq_start + 1

    zt_days = sum(1 for s, e in segments for idx in range(s, min(e, cut_idx) + 1)
                  if rows[idx]['is_zt'])
    zt_density = zt_days / total_days if total_days > 0 else 0

    first_close = rows[seq_start]['pre_close']
    if first_close == 0 or np.isnan(first_close):
        first_close = rows[seq_start]['open']

    mbpi, is_severe = find_main_break(rows, break_periods, cut_idx)
    mb = break_periods[mbpi] if mbpi is not None else None

    lb = CONFIG['max_rise_lookback']
    lookback_start = max(0, cut_idx - lb)
    first_zt_in_window = None
    for k in range(lookback_start, cut_idx + 1):
        if rows[k]['is_zt']:
            first_zt_in_window = k
            break
    if first_zt_in_window is not None:
        while first_zt_in_window > 0 and rows[first_zt_in_window - 1]['is_zt']:
            first_zt_in_window -= 1
        rise_base = rows[first_zt_in_window]['pre_close']
        if rise_base == 0 or np.isnan(rise_base):
            rise_base = rows[first_zt_in_window]['open']
    else:
        rise_base = rows[lookback_start]['close']
    max_close_30 = max((rows[k]['close'] for k in range(lookback_start, cut_idx + 1)),
                       default=rise_base)
    max_rise = (max_close_30 - rise_base) / rise_base if rise_base > 0 else 0
    max_rise_category = classify_max_rise(max_rise)

    cut_close = rows[cut_idx]['close']
    hr = (max_close_30 - cut_close) / max_close_30 if max_close_30 > 0 else 0
    hr_category = classify_height_retracement(hr)

    d1f, d1e = '无', '震荡'
    d1tz = d1td = False
    d2f, d2e = '无', '震荡'
    bpp = 0.0
    bpd = bad = 0
    d3sp = set()
    buc = bdc_count = 0
    d1_idx = None
    dt_int = '无跌停'
    ztdt_in_break = 0
    mid_zt_type = '无涨停'

    if mb is not None:
        bs, be = mb
        d1_idx = bs
        bad = min(be, cut_idx) - bs + 1
        bpd = cut_idx - bs + 1
        if bs < len(rows) and bs <= cut_idx:
            d1f = rows[bs]['form']
            d1e = rows[bs]['emotion']
            d1tz = rows[bs]['touched_zt']
            d1td = rows[bs]['touched_dt']
        if bs + 1 <= be and bs + 1 < len(rows) and bs + 1 < cut_idx:
            d2f = rows[bs + 1]['form']
            d2e = rows[bs + 1]['emotion']
        for k in range(bs + 2, cut_idx):
            if k < len(rows):
                f = rows[k]['form']
                if f not in COLD_FORMS and f not in ('普通涨停', '普通跌停'):
                    d3sp.add(f)
        zt_in_break = 0
        dt_in_break = 0
        for k in range(bs, cut_idx):
            if k < len(rows):
                f = rows[k]['form']
                if f in BIG_UP_FORMS:
                    buc += 1
                if f in BIG_DOWN_FORMS:
                    bdc_count += 1
                if rows[k]['is_zt']:
                    zt_in_break += 1
                if rows[k]['is_dt']:
                    dt_in_break += 1
        ztdt_in_break = zt_in_break + dt_in_break
        dt_int = classify_dt_intensity(rows, bs, cut_idx)
        pbc = rows[bs - 1]['close'] if bs > 0 else first_close
        bpp = (cut_close - pbc) / pbc if pbc > 0 else 0
        mid_zt_type = classify_mid_zt_type(rows, bs, cut_idx)

    bppc = '大涨' if bpp > CONFIG['break_period_pct_high'] else \
        '小涨' if bpp >= 0 else \
        '小跌' if bpp >= CONFIG['break_period_pct_low'] else '大跌'
    bdaysc = classify_break_period_days(bad)
    denc = classify_density(buc, bdc_count, bpp, ztdt_in_break)

    cut_to_d1 = cut_idx - d1_idx if d1_idx is not None else 0
    cut_to_d1_category = classify_cut_to_d1(cut_to_d1)

    bc = 0
    inz = False
    for idx in range(seq_start, cut_idx + 1):
        if rows[idx]['is_zt']:
            inz = True
        elif inz:
            bc += 1
            inz = False

    hs = {'一字板': 0, 'T字板': 0, '地天板': 0, '大长腿涨停': 0, '秒板': 0}
    sps = []
    for idx in range(seq_start, cut_idx + 1):
        f = rows[idx]['form']
        if rows[idx]['is_zt']:
            sps.append(f)
            if idx < cut_idx and f in hs:
                hs[f] += 1
        else:
            sps.append(f'[{f}]')
    hst = set(k for k, v in hs.items() if v > 0)

    micro = build_micro_structure(rows, seq_start, segments, cut_idx)

    ls = [rows[idx]['vol_label'] if rows[idx]['is_zt'] else 'X'
          for idx in range(seq_start, cut_idx + 1)]
    ma = streak = 0
    for lb_v in ls:
        if lb_v == 1:
            streak += 1
            ma = max(ma, streak)
        else:
            streak = 0

    wave_threshold = CONFIG['wave_significant_threshold']
    wave_count = 0
    for seg_idx, (s, e) in enumerate(segments):
        if e >= cut_idx:
            break
        seg_close = rows[e]['close']
        search_end = cut_idx
        for next_s, next_e in segments:
            if next_s > e:
                search_end = next_s
                break
        if e + 1 < len(rows) and e + 1 <= search_end:
            min_close = min((rows[k]['close'] for k in range(e + 1, min(search_end, len(rows)))
                            if k < len(rows)), default=seg_close)
            bp_pct = (min_close - seg_close) / seg_close if seg_close > 0 else 0
            if bp_pct < wave_threshold:
                wave_count += 1
    last_seg_end = max(e for s, e in segments if e <= cut_idx)
    if last_seg_end < cut_idx:
        seg_close = rows[last_seg_end]['close']
        min_close = min((rows[k]['close'] for k in range(last_seg_end + 1, cut_idx + 1)
                        if k < len(rows)), default=seg_close)
        bp_pct = (min_close - seg_close) / seg_close if seg_close > 0 else 0
        if bp_pct < wave_threshold:
            wave_count += 1
    wave_category = '单波' if wave_count <= 1 else '多波'

    np_, nz, no = None, None, None
    if cut_idx + 1 < len(rows):
        nr = rows[cut_idx + 1]
        npc = cut_row['close']
        if npc > 0:
            np_ = (nr['close'] - npc) / npc
            no = (nr['open'] - npc) / npc
            nz = np_ >= CONFIG['zt_threshold']

    return {
        'stock_code': stock_code, 'stock_name': stock_name, 'cut_date': cut_date,
        'seq_start_date': rows[seq_start]['date'],
        'total_days': total_days, 'zt_days': zt_days, 'zt_density': zt_density,
        'max_rise': max_rise, 'max_rise_category': max_rise_category,
        'height_retracement': hr, 'height_retracement_category': hr_category,
        'is_severe_break': is_severe,
        'break_d1_form': d1f, 'break_d1_emotion': d1e,
        'break_d1_touched_zt': d1tz, 'break_d1_touched_dt': d1td,
        'break_d2_form': d2f, 'break_d2_emotion': d2e,
        'break_period_days': bpd, 'break_actual_days': bad,
        'break_days_category': bdaysc,
        'cut_to_d1_days': cut_to_d1, 'cut_to_d1_category': cut_to_d1_category,
        'mid_zt_type': mid_zt_type,
        'break_period_pct': bpp, 'break_period_pct_category': bppc,
        'break_d3plus_special_forms': d3sp,
        'big_up_count': buc, 'big_down_count': bdc_count,
        'density_category': denc, 'dt_intensity': dt_int,
        'break_count': bc, 'break_count_category': '1次' if bc <= 1 else '多次',
        'history_special': hs, 'history_special_types': hst,
        'has_history_special': len(hst) > 0,
        'special_position_seq': sps,
        'cut_form': rows[cut_idx]['form'], 'cut_emotion': rows[cut_idx]['emotion'],
        'cut_is_zt': rows[cut_idx]['is_zt'], 'cut_board_strength': rows[cut_idx]['board_strength'],
        'cut_pct': rows[cut_idx]['pct'],
        'cut_volume_state': {0: '放量', 1: '平量', 2: '缩量'}.get(rows[cut_idx]['vol_label'], '放量'),
        'cut_touched_zt': rows[cut_idx]['touched_zt'], 'cut_touched_dt': rows[cut_idx]['touched_dt'],
        'micro': micro,
        'max_accel_duration': ma, 'max_accel_category': '长波' if ma >= 3 else '短波',
        'label_sequence': ls,
        'wave_count': wave_count, 'wave_category': wave_category,
        'next_day_pct': np_, 'next_day_is_zt': nz, 'next_day_open_pct': no,
    }
def _process_single_stock(args):
    code, name, daily_df = args
    cases = []
    try:
        rows = precompute_stock_data(daily_df)
        if len(rows) < 3:
            return cases
        for seq_info in find_break_sequences(rows):
            start = seq_info['break_periods'][0][0]
            end = seq_info['seq_end']
            for ci in range(start, min(end, len(rows) - 1) + 1):
                try:
                    case = build_break_case(code, name, rows, seq_info, ci)
                    if case is not None:
                        cases.append(case)
                except Exception:
                    continue
    except Exception:
        pass
    if len(cases) > 1:
        best = {}
        for c in cases:
            key = str(c['cut_date'])[:10]
            if key not in best or c['zt_days'] > best[key]['zt_days']:
                best[key] = c
        cases = list(best.values())
        cases.sort(key=lambda c: str(c['cut_date']))
        filtered = []
        prev_key = None
        for c in cases:
            cm = c['micro']
            cur_key = (
                str(c['seq_start_date'])[:10],
                cm['nearest_special_subdivision'],
                cm['mid_special_subdivision'],
                cm['cut_subdivision'],
            )
            if cur_key == prev_key:
                continue
            filtered.append(c)
            prev_key = cur_key
        cases = filtered
    return cases


def build_all_break_cases(all_daily_data, stock_info_df):
    cf = CONFIG.get('case_library_cache')
    if cf and os.path.exists(cf):
        try:
            print(f"\n从缓存加载断板案例库...")
            with open(cf, 'rb') as f:
                ac = pickle.load(f)
            print(f"断板案例库: {len(ac)} 个案例（缓存）")
            return ac
        except Exception:
            print(f"缓存失败，重新构建...")
    c2n = dict(zip(stock_info_df['code'], stock_info_df['name']))
    total = len(all_daily_data)
    wc = CONFIG.get('worker_count', 4)
    ta = [(code, c2n.get(code, '未知'), df) for code, df in all_daily_data.items()]
    print(f"\n构建断板案例库，共 {total} 只，{wc} 进程...")
    st = time.time()
    ac = []
    try:
        with Pool(processes=wc) as pool:
            for cl in pool.map(_process_single_stock, ta, chunksize=50):
                ac.extend(cl)
    except Exception as e:
        print(f"多进程失败({e})，单进程...")
        p = 0
        for a in ta:
            p += 1
            if p % 200 == 0 or p == total:
                print(f"  {p}/{total} | {len(ac)} 案例")
            ac.extend(_process_single_stock(a))
    print(f"案例库完成: {len(ac)} 个 | {time.time() - st:.1f}秒")
    if cf:
        try:
            with open(cf, 'wb') as f:
                pickle.dump(ac, f)
            print(f"已缓存: {cf}")
        except Exception:
            pass
    return ac


def hard_filter_with_downgrade(target_case, case_library):
    threshold = CONFIG['downgrade_threshold']
    tap = 0
    pa = CONFIG['penalty_a_class']
    current = [c for c in case_library if c['stock_code'] != target_case['stock_code']]
    print(f"  排除同股票：{len(current)}")

    # ===== 回撤比 =====
    f = [c for c in current
         if c['height_retracement_category'] == target_case['height_retracement_category']]
    if len(f) >= threshold:
        current = f
        print(f"  回撤比({target_case['height_retracement_category']})：{len(current)}")
    else:
        tap += pa
        print(f"  回撤比放开：{len(current)}（-{pa}）")

    # ===== 距D1档位（v1.7新4档） =====
    t_d1_cat = target_case['cut_to_d1_category']
    d1_cat_order = {'1天': 0, '2~3天': 1, '4~7天': 2, '>7天': 3}
    t_d1_ord = d1_cat_order.get(t_d1_cat, 1)

    f = [c for c in current if c['cut_to_d1_category'] == t_d1_cat]
    if len(f) >= threshold:
        current = f
        print(f"  距D1({t_d1_cat})：{len(current)}")
    else:
        # 降1档
        allowed_ords = {t_d1_ord - 1, t_d1_ord, t_d1_ord + 1}
        allowed_cats = [cat for cat, ord_v in d1_cat_order.items() if ord_v in allowed_ords]
        f = [c for c in current if c['cut_to_d1_category'] in allowed_cats]
        if len(f) >= threshold:
            current = f
            tap += 20
            print(f"  距D1降1档({allowed_cats})：{len(current)}（-20）")
        else:
            # 不够也只允许±1档
            if f:
                current = f
            tap += 20
            print(f"  距D1降1档(不足{len(f)})：{len(current)}（-20）")

    # ===== 断板期中间涨停情况（v1.7新增） =====
    t_mid_zt = target_case.get('mid_zt_type', '无涨停')
    mid_zt_order = {'无涨停': 0, '不连续涨停': 1, '连板': 2}
    t_mid_ord = mid_zt_order.get(t_mid_zt, 0)

    f = [c for c in current if c.get('mid_zt_type', '无涨停') == t_mid_zt]
    if len(f) >= threshold:
        current = f
        print(f"  中间涨停({t_mid_zt})：{len(current)}")
    else:
        allowed_ords = {t_mid_ord - 1, t_mid_ord, t_mid_ord + 1}
        allowed_types = [t for t, o in mid_zt_order.items() if o in allowed_ords]
        f = [c for c in current if c.get('mid_zt_type', '无涨停') in allowed_types]
        if len(f) >= threshold:
            current = f
            tap += CONFIG['penalty_mid_zt_mismatch']
            print(f"  中间涨停降1档({allowed_types})：{len(current)}（-{CONFIG['penalty_mid_zt_mismatch']}）")
        else:
            if f:
                current = f
            tap += CONFIG['penalty_mid_zt_mismatch']
            print(f"  中间涨停降1档(不足{len(f)})：{len(current)}（-{CONFIG['penalty_mid_zt_mismatch']}）")

    # ===== 微型结构 =====
    tm = target_case['micro']
    is_long_break = target_case['cut_to_d1_days'] > 7

    def _match_zt(c, level='细分'):
        cm = c['micro']
        ts = tm['nearest_zt_subdivision']
        cs = cm['nearest_zt_subdivision']
        if ts == '无' and cs == '无':
            return True
        if ts == '无' or cs == '无':
            return True
        if level == '细分':
            return match_subdivision(ts, cs)
        else:
            return match_approx(ts, cs)

    def _match_pre(c, level='细分'):
        cm = c['micro']
        ts = tm['nearest_special_subdivision']
        cs = cm['nearest_special_subdivision']
        if ts == '无' and cs == '无':
            return True
        if ts == '无' or cs == '无':
            return False
        if level == '细分':
            return match_subdivision(ts, cs)
        elif level == '近似':
            return match_approx(ts, cs)
        return True

    def _match_cut(c, level='细分'):
        cm = c['micro']
        if level == '细分':
            return match_subdivision(tm['cut_subdivision'], cm['cut_subdivision'])
        else:
            return match_approx(tm['cut_subdivision'], cm['cut_subdivision'])

    if is_long_break:
        levels = [
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '细分') and _match_cut(c, '细分'),
             "微型(全细分)", 0),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '近似') and _match_cut(c, '细分'),
             "微型(前置近似)", pa),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '放开') and _match_cut(c, '细分'),
             "微型(前置放开)", pa),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '放开') and _match_cut(c, '近似'),
             "微型(前置放开+切面近似)", pa),
            (lambda c: _match_zt(c, '近似') and _match_pre(c, '放开') and _match_cut(c, '近似'),
             "微型(涨停近似+前置放开+切面近似)", pa),
        ]
    else:
        levels = [
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '细分') and _match_cut(c, '细分'),
             "微型(全细分)", 0),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '细分') and _match_cut(c, '近似'),
             "微型(切面近似)", pa),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '放开') and _match_cut(c, '细分'),
             "微型(前置放开)", pa),
            (lambda c: _match_zt(c, '细分') and _match_pre(c, '放开') and _match_cut(c, '近似'),
             "微型(前置放开+切面近似)", pa),
            (lambda c: _match_zt(c, '近似') and _match_pre(c, '放开') and _match_cut(c, '近似'),
             "微型(涨停近似+前置放开+切面近似)", pa),
        ]

    matched = False
    cum_cost = 0
    for func, label, cost in levels:
        cum_cost += cost
        f = [c for c in current if func(c)]
        if len(f) >= threshold:
            current = f
            tap += cum_cost
            suffix = f"（-{tap}）" if tap > 0 else ""
            print(f"  {label}：{len(current)}{suffix}")
            matched = True
            break
    if not matched:
        tap += cum_cost
        print(f"  微型结构全放开：{len(current)}（-{tap}）")

    # ===== 密度硬匹配 =====
    td = target_case['density_category']
    f = [c for c in current if c['density_category'] == td]
    if len(f) >= threshold:
        current = f
        print(f"  密度({td})：{len(current)}")
    else:
        tap += pa
        print(f"  密度放开：{len(current)}（-{pa}）")

    # ===== D1 =====
    td1 = target_case['break_d1_form']
    f = [c for c in current if c['break_d1_form'] == td1]
    if len(f) >= threshold:
        current = f
        print(f"  D1精确({td1})：{len(current)}")
    else:
        te = target_case['break_d1_emotion']
        f = [c for c in current if c['break_d1_emotion'] == te]
        if len(f) >= threshold:
            current = f
            tap += pa
            print(f"  D1情绪({te})：{len(current)}（-{pa}）")
        else:
            tap += pa
            print(f"  D1全放开：{len(current)}（-{pa}）")

    return current, tap


def calc_b_penalty(tc, cc):
    p = b = 0
    d = []
    tier = get_weight_tier(tc['cut_to_d1_category'])
    wb = get_weight_multiplier(tier, 'break_period')
    wz = get_weight_multiplier(tier, 'zt_seg')
    wd = get_weight_multiplier(tier, 'd1')

    # 最大涨幅跨档
    rise_order = {'低位': 0, '中位': 1, '高位': 2, '超高位': 3}
    t_ro = rise_order.get(tc['max_rise_category'], 1)
    c_ro = rise_order.get(cc['max_rise_category'], 1)
    rg = abs(t_ro - c_ro)
    if rg == 1:
        p += CONFIG['penalty_rise_cross_1']
        d.append(f"涨幅跨1档-{CONFIG['penalty_rise_cross_1']}")
    elif rg >= 2:
        p += CONFIG['penalty_rise_cross_2']
        d.append(f"涨幅跨{rg}档-{CONFIG['penalty_rise_cross_2']}")

    # 断板次数
    if cc['break_count_category'] != tc['break_count_category']:
        v = round(CONFIG['penalty_break_count'] * wb)
        p += v
        d.append(f"断板次数-{v}")

    # D2情绪（断板实际天数>1才评估）
    if tc['break_actual_days'] > 1 and (tc['break_d2_form'] != '无' or cc['break_d2_form'] != '无'):
        if cc['break_d2_emotion'] != tc['break_d2_emotion']:
            v = round(CONFIG['penalty_d2_emotion_mismatch'] * wb)
            p += v
            d.append(f"D2情绪-{v}")

    # 距D1同档内天数差值扣分（v1.7：扩展到所有档，封顶15）
    d1_days_diff = abs(tc['cut_to_d1_days'] - cc['cut_to_d1_days'])
    if tc['cut_to_d1_category'] == cc['cut_to_d1_category'] and d1_days_diff > 0:
        v = min(d1_days_diff * CONFIG['penalty_d1_days_per'], CONFIG['penalty_d1_days_cap'])
        p += v
        d.append(f"距D1差{d1_days_diff}天-{v}")

    # 断板期涨跌幅（档位扣分）
    tpc, cpc = tc['break_period_pct_category'], cc['break_period_pct_category']
    if tpc != cpc:
        po = {'大跌': 0, '小跌': 1, '小涨': 2, '大涨': 3}
        gap = abs(po.get(tpc, 1) - po.get(cpc, 1))
        base = CONFIG['penalty_break_pct_2'] if gap >= 2 else CONFIG['penalty_break_pct_1']
        v = round(base * wb)
        p += v
        d.append(f"涨跌幅跨{gap}档-{v}")

    # 断板期涨跌幅（连续值扣分）
    pct_diff = abs(tc['break_period_pct'] - cc['break_period_pct'])
    if pct_diff > 0.15:
        v = round(20 * wb)
        p += v
        d.append(f"涨跌幅差{pct_diff:.0%}-{v}")
    elif pct_diff > 0.10:
        v = round(12 * wb)
        p += v
        d.append(f"涨跌幅差{pct_diff:.0%}-{v}")
    elif pct_diff > 0.05:
        v = round(6 * wb)
        p += v
        d.append(f"涨跌幅差{pct_diff:.0%}-{v}")

    # 波段次数
    if tc['wave_category'] != cc['wave_category']:
        v = CONFIG['penalty_wave_mismatch']
        p += v
        d.append(f"波段({tc['wave_category']}vs{cc['wave_category']})-{v}")

    # ===== 涨停段（保留原有逻辑：短涨停段加重） =====
    zt_day_mult = 1.0
    if tc['zt_days'] <= 2:
        zt_day_mult = 3.0
    elif tc['zt_days'] <= 3:
        zt_day_mult = 2.0

    zp = 0
    zd = []
    if cc['max_accel_category'] != tc['max_accel_category']:
        v = round(CONFIG['penalty_b_class'] * wz * zt_day_mult)
        zp += v
        zd.append(f"加速-{v}")

    tt, ct = tc['history_special_types'], cc['history_special_types']
    if tc['has_history_special'] or cc['has_history_special']:
        diff_count = len((tt - ct) | (ct - tt))
        if diff_count > 0:
            v = round(diff_count * CONFIG['penalty_b_class'] * wz * zt_day_mult)
            zp += v
            zd.append(f"涨停段板型差{diff_count}种-{v}")
        cp2, cd2 = calc_special_count_penalty(tc['history_special'], cc['history_special'])
        if cp2 > 0:
            cp2 = round(cp2 * wz * zt_day_mult)
            zp += cp2
            zd.append(f"数量差异-{cp2}")

    if tc['zt_days'] <= 2:
        cap = 90
    elif tc['zt_days'] <= 3:
        cap = 60
    else:
        cap = get_zt_seg_cap(tier)
    if zp > cap:
        zd.append(f"封顶({zp}->{cap})")
        zp = cap
    p += zp
    d.extend(zd)

    # ===== 2板逐日板型匹配（v1.7新增，额外扣分） =====
    if tc['zt_days'] <= 2:
        def _extract_zt_forms(case):
            forms = []
            for item in case['special_position_seq']:
                if not item.startswith('['):
                    forms.append(item)
            return forms

        t_forms = _extract_zt_forms(tc)
        c_forms = _extract_zt_forms(cc)

        if len(t_forms) >= 2 and len(c_forms) >= 2:
            if len(c_forms) == 2:
                # 候选也是2板：逐日对齐
                day_mismatch = 0
                for i in range(2):
                    if t_forms[i] != c_forms[i]:
                        day_mismatch += 1
                if day_mismatch > 0:
                    v = day_mismatch * 15
                    p += v
                    d.append(f"逐日板型差{day_mismatch}天-{v}")
            else:
                # 候选≥3板：滑动窗口找最佳2天对齐
                best_match = 0
                for start in range(len(c_forms) - 1):
                    match_count = 0
                    if t_forms[0] == c_forms[start]:
                        match_count += 1
                    if t_forms[1] == c_forms[start + 1]:
                        match_count += 1
                    if match_count > best_match:
                        best_match = match_count
                mismatch = 2 - best_match
                if mismatch > 0:
                    v = mismatch * 15
                    p += v
                    d.append(f"滑动板型差{mismatch}天-{v}")

    # D3+（断板实际天数>1才评估）
    if tc['break_actual_days'] > 1:
        td3, cd3 = tc['break_d3plus_special_forms'], cc['break_d3plus_special_forms']
        if not td3 and not cd3:
            v = round(CONFIG['bonus_d3_both_none'] * wb)
            b += v
            d.append(f"D3+双方无+{v}")
        elif td3 and cd3:
            if td3 == cd3:
                v = round(CONFIG['bonus_d3_exact'] * wb)
                b += v
                d.append(f"D3+一致+{v}")
            elif not (td3 & cd3):
                v = round(CONFIG['penalty_d3_mismatch'] * wb)
                p += v
                d.append(f"D3+零交集-{v}")
        else:
            v = round(CONFIG['penalty_d3_mismatch'] * wb)
            p += v
            d.append(f"D3+一方无-{v}")

    # 密度 + 跌停强度
    ds = DENSITY_MATRIX.get((tc['density_category'], cc['density_category']), 0)
    ds = round(ds * wb)
    if ds > 0:
        b += ds
        d.append(f"密度+{ds}")
        dt_order = {'无跌停': 0, '单跌停': 1, '连跌停': 2}
        t_dt = dt_order.get(tc['dt_intensity'], 0)
        c_dt = dt_order.get(cc['dt_intensity'], 0)
        dt_gap = abs(t_dt - c_dt)
        if dt_gap == 0:
            b += 15
            d.append(f"跌停强度+15")
        elif dt_gap == 1:
            p += 10
            d.append(f"跌停强度跨1档-10")
        else:
            p += 20
            d.append(f"跌停强度跨2档-20")
    elif ds < 0:
        p += abs(ds)
        d.append(f"密度{ds}")

    # D1加分/扣分
    if tc['break_d1_form'] != '无' and cc['break_d1_form'] != '无':
        if cc['break_d1_form'] == tc['break_d1_form']:
            v = round(CONFIG['bonus_d1_exact'] * wd)
            b += v
            d.append(f"D1精确+{v}")
        elif cc['break_d1_emotion'] == tc['break_d1_emotion']:
            v = round(CONFIG['bonus_d1_same_emotion'] * wd)
            b += v
            d.append(f"D1情绪+{v}")
        else:
            v = round(CONFIG['penalty_a_class'] * wd)
            p += v
            d.append(f"D1不匹配-{v}")

    # D2加分（断板实际天数>1才评估）
    if tc['break_actual_days'] > 1 and tc['break_d2_form'] != '无' and cc['break_d2_form'] != '无':
        if cc['break_d2_form'] == tc['break_d2_form']:
            b += CONFIG['bonus_d2_exact']
            d.append(f"D2精确+{CONFIG['bonus_d2_exact']}")
        elif cc['break_d2_emotion'] == tc['break_d2_emotion']:
            b += CONFIG['bonus_d2_same_emotion']
            d.append(f"D2情绪+{CONFIG['bonus_d2_same_emotion']}")

    # 触及
    if tc['break_d1_touched_zt'] and cc['break_d1_touched_zt']:
        v = round(CONFIG['bonus_touch_zt_match'] * wd)
        b += v
        d.append(f"D1触涨停+{v}")
    if tc['break_d1_touched_dt'] and cc['break_d1_touched_dt']:
        v = round(CONFIG['bonus_touch_dt_match'] * wd)
        b += v
        d.append(f"D1触跌停+{v}")

    return p, b, d


def calc_c_penalty(tc, cc):
    p = b = 0
    d = []
    if not tc['cut_is_zt'] and not cc['cut_is_zt']:
        vol_order = {'放量': 0, '平量': 1, '缩量': 2}
        t_vol = vol_order.get(tc['cut_volume_state'], 0)
        c_vol = vol_order.get(cc['cut_volume_state'], 0)
        vol_gap = abs(t_vol - c_vol)
        if vol_gap == 1:
            p += 10
            d.append(f"量能跨1档-10")
        elif vol_gap >= 2:
            p += 15
            d.append(f"量能跨2档-15")
    if tc['cut_touched_zt'] and cc['cut_touched_zt']:
        b += CONFIG['bonus_touch_zt_match']
        d.append(f"触涨停+{CONFIG['bonus_touch_zt_match']}")
    if tc['cut_touched_dt'] and cc['cut_touched_dt']:
        b += CONFIG['bonus_touch_dt_match']
        d.append(f"触跌停+{CONFIG['bonus_touch_dt_match']}")
    return p, b, d


def calc_micro_bonus(tc, cc):
    p = b = 0
    d = []
    tm, cm = tc['micro'], cc['micro']

    d1_days = tc['cut_to_d1_days']
    if d1_days <= 3:
        decay = 1.0
    elif d1_days <= 7:
        decay = 0.6
    else:
        decay = 0.2

    # 最近涨停
    ts_zt = tm['nearest_zt_subdivision']
    cs_zt = cm['nearest_zt_subdivision']
    if ts_zt == '无' and cs_zt == '无':
        v = round(CONFIG['bonus_micro_zt_both_none'] * decay)
        b += v
        d.append(f"微涨停双方无+{v}")
    elif ts_zt != '无' and cs_zt != '无':
        if match_subdivision(ts_zt, cs_zt):
            b += CONFIG['bonus_micro_zt_exact']
            d.append(f"微涨停精确+{CONFIG['bonus_micro_zt_exact']}")
        elif match_approx(ts_zt, cs_zt):
            b += CONFIG['bonus_micro_zt_compat']
            d.append(f"微涨停近似+{CONFIG['bonus_micro_zt_compat']}")

    # 中间特殊形态
    ts_mid = tm['mid_special_subdivision']
    cs_mid = cm['mid_special_subdivision']
    if ts_mid == '无' and cs_mid == '无':
        v = round(CONFIG['bonus_micro_mid_both_none'] * decay)
        b += v
        d.append(f"微中间双方无+{v}")
    elif ts_mid != '无' and cs_mid != '无':
        if match_subdivision(ts_mid, cs_mid):
            b += CONFIG['bonus_micro_mid_special_exact']
            d.append(f"微中间精确+{CONFIG['bonus_micro_mid_special_exact']}")
        elif match_approx(ts_mid, cs_mid):
            b += CONFIG['bonus_micro_mid_special_approx']
            d.append(f"微中间近似+{CONFIG['bonus_micro_mid_special_approx']}")
        else:
            p += CONFIG['penalty_micro_mid_mismatch']
            d.append(f"微中间不匹配-{CONFIG['penalty_micro_mid_mismatch']}")
    else:
        p += CONFIG['penalty_micro_mid_mismatch']
        d.append(f"微中间有无不匹配-{CONFIG['penalty_micro_mid_mismatch']}")

    # 前置形态
    ts_pre = tm['nearest_special_subdivision']
    cs_pre = cm['nearest_special_subdivision']
    if ts_pre == '无' or cs_pre == '无':
        if ts_pre == cs_pre:
            v = round(CONFIG['bonus_micro_pre_cold'] * decay)
            b += v
            d.append(f"微前置双方无+{v}")
        else:
            p += CONFIG['penalty_micro_pre_mismatch']
            d.append(f"微前置不匹配-{CONFIG['penalty_micro_pre_mismatch']}")
    elif match_subdivision(ts_pre, cs_pre):
        if ts_pre == '震荡':
            v = round(CONFIG['bonus_micro_pre_cold'] * decay)
            b += v
            d.append(f"微前置冷淡+{v}")
        else:
            b += CONFIG['bonus_micro_pre_exact']
            d.append(f"微前置({tm['nearest_special_before_cut']})+{CONFIG['bonus_micro_pre_exact']}")
    elif match_approx(ts_pre, cs_pre):
        b += CONFIG['bonus_micro_pre_approx']
        d.append(f"微前置近似+{CONFIG['bonus_micro_pre_approx']}")
    else:
        p += CONFIG['penalty_micro_pre_mismatch']
        d.append(f"微前置不匹配-{CONFIG['penalty_micro_pre_mismatch']}")

    # 前置的前一天
    ts_pp = tm['pre_prev_subdivision']
    cs_pp = cm['pre_prev_subdivision']
    if ts_pp != '无' and cs_pp != '无':
        if match_subdivision(ts_pp, cs_pp):
            v = CONFIG['bonus_micro_pre_prev_exact']
            b += v
            d.append(f"微前前精确+{v}")
        elif match_approx(ts_pp, cs_pp):
            v = CONFIG['bonus_micro_pre_prev_approx']
            b += v
            d.append(f"微前前近似+{v}")

    # 切面形态（不衰减）
    if match_subdivision(tm['cut_subdivision'], cm['cut_subdivision']):
        b += CONFIG['bonus_micro_cut_exact']
        d.append(f"微切面精确+{CONFIG['bonus_micro_cut_exact']}")
    elif match_approx(tm['cut_subdivision'], cm['cut_subdivision']):
        b += CONFIG['bonus_micro_cut_approx']
        d.append(f"微切面近似+{CONFIG['bonus_micro_cut_approx']}")
    else:
        p += CONFIG['penalty_micro_cut_mismatch']
        d.append(f"微切面不匹配-{CONFIG['penalty_micro_cut_mismatch']}")

    return p, b, d
def calc_distance(tc, cands):
    if not cands:
        return []

    def feat(c):
        return np.array([c['max_rise'], c['height_retracement'], c['break_period_pct'],
                         c['zt_density'], c['cut_to_d1_days'], c['cut_pct']], dtype=float)

    tf = feat(tc)
    cf = np.array([feat(c) for c in cands])
    af = np.vstack([tf.reshape(1, -1), cf])
    mn, mx = af.min(0), af.max(0)
    r = mx - mn
    r[r == 0] = 1.0
    nm = (af - mn) / r
    ds = np.sqrt(np.sum((nm[1:] - nm[0]) ** 2, axis=1))
    for i, c in enumerate(cands):
        c['distance'] = ds[i]
    return cands


def calc_final_score(tc, cands, ap):
    mp = CONFIG['max_penalty_threshold']
    bonus_cap = CONFIG['bonus_cap']
    scored = []
    for c in cands:
        bp, bb, bd = calc_b_penalty(tc, c)
        cp, cb, cd = calc_c_penalty(tc, c)
        mrp, mrb, mrd = calc_micro_bonus(tc, c)
        tp = ap + bp + cp + mrp
        tb_raw = bb + cb + mrb
        tb = min(tb_raw, bonus_cap)
        if (tp - tb) >= mp:
            continue
        det = []
        if ap > 0:
            det.append(f"A类-{ap}")
        det.extend(bd)
        det.extend(cd)
        det.extend(mrd)
        if tb_raw > bonus_cap:
            det.append(f"加分封顶({tb_raw}->{bonus_cap})")
        c['individual_penalty'] = tp
        c['individual_bonus'] = tb
        c['penalty_details'] = det
        scored.append(c)
    print(f"  扣分过滤(净扣>={mp})：{len(scored)}")
    return scored


def apply_distance_score(tc, sc):
    if not sc:
        return []
    dtn = CONFIG['distance_top_n']
    for c in sc:
        c['_ss'] = 100 - c['individual_penalty'] + c['individual_bonus']
    sc.sort(key=lambda x: x['_ss'], reverse=True)
    top, rest = sc[:dtn], sc[dtn:]
    if top:
        top = calc_distance(tc, top)
    mdp = 0
    for c in top:
        dp = c['distance'] * CONFIG['distance_multiplier']
        if dp > mdp:
            mdp = dp
        if dp > 0.01:
            c['penalty_details'].append(f"距离-{dp:.1f}")
        c['distance_penalty'] = round(dp, 2)
        c['structure_score'] = round(c['_ss'], 2)
        c['final_score'] = round(min(100, c['_ss']) - dp, 2)
        c['penalty_detail'] = '；'.join(c['penalty_details'])
    for c in rest:
        c['distance'] = 0
        c['distance_penalty'] = round(mdp, 2)
        c['structure_score'] = round(c['_ss'], 2)
        c['final_score'] = round(min(100, c['_ss']) - mdp, 2)
        if mdp > 0.01:
            c['penalty_details'].append(f"距离(外)-{mdp:.1f}")
        c['penalty_detail'] = '；'.join(c['penalty_details'])
    result = top + rest
    result.sort(key=lambda x: x['final_score'], reverse=True)
    for c in result:
        c.pop('_ss', None)
    return result


def format_output(tc, ranked, top_n=None):
    if top_n is None:
        top_n = CONFIG['top_n']
    rows = []
    for rank, c in enumerate(ranked[:top_n], 1):
        hsp = [f"{k}x{v}" for k, v in c['history_special'].items() if v > 0]
        sc = c['final_score']
        gr = '高' if sc >= 80 else '中' if sc >= 60 else '低'
        d3 = ', '.join(sorted(c['break_d3plus_special_forms'])) or '无'
        cm = c['micro']
        rows.append({
            '排名': rank, '代码': c['stock_code'], '名称': c['stock_name'],
            '切面日': str(c['cut_date'])[:10],
            '最终得分': c['final_score'], '结构分': c['structure_score'],
            '距离扣分': c['distance_penalty'], '相似度': gr,
            '断板类型': '严重' if c['is_severe_break'] else '普通',
            '距D1': c['cut_to_d1_days'], '距D1档': c['cut_to_d1_category'],
            '中间涨停': c.get('mid_zt_type', '无涨停'),
            '波段': c['wave_category'],
            '扣分明细': c['penalty_detail'],
            '最大涨幅': f"{c['max_rise']:.1%}", '涨幅档': c['max_rise_category'],
            '回撤比': f"{c['height_retracement']:.1%}", '回撤档': c['height_retracement_category'],
            'D1形态': c['break_d1_form'], 'D1情绪': c['break_d1_emotion'],
            'D1触涨停': '是' if c['break_d1_touched_zt'] else '否',
            'D2形态': c['break_d2_form'], 'D2情绪': c['break_d2_emotion'],
            '断板次数': c['break_count'], '次数档': c['break_count_category'],
            '断板天数': c['break_actual_days'], '天数档': c['break_days_category'],
            '断板期涨跌幅': f"{c['break_period_pct']:.2%}", '涨跌幅档': c['break_period_pct_category'],
            '密度': c['density_category'], '涨数': c['big_up_count'], '跌数': c['big_down_count'],
            '跌停强度': c['dt_intensity'],
            'D3+': d3, '加速': c['max_accel_duration'], '加速档': c['max_accel_category'],
            '历史板型': ', '.join(hsp) or '无',
            '板型序列': '->'.join(c['special_position_seq']),
            '微涨停': cm['nearest_zt_form'], '微涨停细分': cm['nearest_zt_subdivision'],
            '微中间': cm['mid_type'], '微中间特殊': cm['mid_special_form'],
            '微中间细分': cm['mid_special_subdivision'],
            '微前置': cm['nearest_special_before_cut'], '微前置细分': cm['nearest_special_subdivision'],
            '微前前': cm['pre_prev_form'], '微前前细分': cm['pre_prev_subdivision'],
            '微切面': cm['cut_form'], '微切面细分': cm['cut_subdivision'],
            '切面形态': c['cut_form'], '切面情绪': c['cut_emotion'],
            '切面涨停': '是' if c['cut_is_zt'] else '否',
            '切面涨跌': f"{c['cut_pct']:.2%}", '切面量能': c['cut_volume_state'],
            '0/1序列': '->'.join(str(x) for x in c['label_sequence']),
            '次日涨跌': f"{c['next_day_pct']:.2%}" if c['next_day_pct'] is not None else '无',
            '次日涨停': '是' if c['next_day_is_zt'] else '否' if c['next_day_is_zt'] is not None else '无',
            '次日开盘': f"{c['next_day_open_pct']:.2%}" if c['next_day_open_pct'] is not None else '无',
        })
    return pd.DataFrame(rows)


def print_target_info(tc):
    hsp = [f"{k}x{v}" for k, v in tc['history_special'].items() if v > 0]
    d3 = ', '.join(sorted(tc['break_d3plus_special_forms'])) or '无'
    sv = '严重' if tc['is_severe_break'] else '普通'
    tm = tc['micro']
    print("\n" + "=" * 70)
    print("标的股信息（断板版 v1.7）")
    print("=" * 70)
    print(f"  代码：{tc['stock_code']}  名称：{tc['stock_name']}")
    print(f"  切面日：{str(tc['cut_date'])[:10]}")
    print(f"  断板类型：{sv}  距D1:{tc['cut_to_d1_days']}天({tc['cut_to_d1_category']})")
    print(f"  中间涨停：{tc.get('mid_zt_type', '无涨停')}")
    print(f"  波段：{tc['wave_category']}({tc['wave_count']}次显著下跌)")
    print(f"  最大涨幅：{tc['max_rise']:.1%}({tc['max_rise_category']})")
    print(f"  高度回撤比：{tc['height_retracement']:.1%}({tc['height_retracement_category']})")
    print(f"  D1：{tc['break_d1_form']}({tc['break_d1_emotion']}) "
          f"触涨停:{'是' if tc['break_d1_touched_zt'] else '否'} "
          f"触跌停:{'是' if tc['break_d1_touched_dt'] else '否'}")
    print(f"  D2：{tc['break_d2_form']}({tc['break_d2_emotion']})")
    print(f"  断板：{tc['break_count']}次({tc['break_count_category']}) "
          f"{tc['break_actual_days']}天({tc['break_days_category']})")
    print(f"  断板期涨跌：{tc['break_period_pct']:.2%}({tc['break_period_pct_category']})")
    print(f"  密度：{tc['density_category']}(涨{tc['big_up_count']}/跌{tc['big_down_count']}) "
          f"跌停强度：{tc['dt_intensity']}")
    print(f"  D3+：{d3}")
    print(f"  加速：{tc['max_accel_duration']}天({tc['max_accel_category']})")
    print(f"  历史板型：{', '.join(hsp) or '无'}")
    print(f"  序列：{'->'.join(tc['special_position_seq'])}")
    print(f"  微型：涨停={tm['nearest_zt_form']}({tm['nearest_zt_subdivision']}) "
          f"中间={tm['mid_type']}[{tm['mid_special_form']}({tm['mid_special_subdivision']})] "
          f"前置={tm['nearest_special_before_cut']}({tm['nearest_special_subdivision']}) "
          f"前前={tm['pre_prev_form']}({tm['pre_prev_subdivision']}) "
          f"切面={tm['cut_form']}({tm['cut_subdivision']})")
    print(f"  切面日：{tc['cut_form']}({tc['cut_emotion']})")
    if tc['cut_is_zt']:
        print(f"  封板强度：{tc['cut_board_strength']}")
    else:
        print(f"  涨跌：{tc['cut_pct']:.2%}  量能：{tc['cut_volume_state']}")
    print(f"  0/1序列：{'->'.join(str(x) for x in tc['label_sequence'])}")
    print("=" * 70)


def print_summary(ranked):
    valid = [c for c in ranked if c['next_day_pct'] is not None]
    if not valid:
        return
    pcts = [c['next_day_pct'] for c in valid]
    zt = sum(1 for c in valid if c['next_day_is_zt'])
    print(f"\n统计({len(valid)}个): 平均{np.mean(pcts):.2%} 中位{np.median(pcts):.2%} "
          f"上涨{sum(1 for p in pcts if p > 0) / len(pcts):.1%} 涨停{zt / len(valid):.1%}")


def build_target_break_case(stock_code, cut_date_str, all_daily_data, stock_info_df):
    c2n = dict(zip(stock_info_df['code'], stock_info_df['name']))
    name = c2n.get(stock_code, '未知')
    if stock_code not in all_daily_data:
        raise ValueError(f"找不到{stock_code}的数据")
    rows = precompute_stock_data(all_daily_data[stock_code].copy())
    cut_date = pd.to_datetime(cut_date_str)
    ci = next((i for i, r in enumerate(rows) if pd.Timestamp(r['date']) == cut_date), None)
    if ci is None:
        raise ValueError(f"{stock_code}在{cut_date_str}无数据")
    for seq in find_break_sequences(rows):
        if seq['seq_start'] <= ci <= seq['seq_end'] and ci >= seq['break_periods'][0][0]:
            return build_break_case(stock_code, name, rows, seq, ci)
    raise ValueError(f"{stock_code}在{cut_date_str}不属于断板走势")


def run_break_matching(stock_code, cut_date_str, search_start, search_end,
                       top_n=None, output_excel=True):
    if top_n is None:
        top_n = CONFIG['top_n']
    print("=" * 70)
    print(f"K线相似（断板版）v1.7 | {stock_code} | {cut_date_str}")
    print("=" * 70)
    si = get_main_board_stock_list()
    ad = batch_download_daily_data(si, search_start, search_end)
    if not ad:
        return pd.DataFrame()
    tc = build_target_break_case(stock_code, cut_date_str, ad, si)
    print_target_info(tc)
    cl = build_all_break_cases(ad, si)
    print(f"\n匹配中... 案例库：{len(cl)}")
    cands, ap = hard_filter_with_downgrade(tc, cl)
    if not cands:
        print("\n硬匹配后无案例")
        return pd.DataFrame()
    scored = calc_final_score(tc, cands, ap)
    if not scored:
        print("\n扣分过滤后无案例")
        return pd.DataFrame()
    ranked = apply_distance_score(tc, scored)
    df = format_output(tc, ranked, top_n)
    print_summary(ranked[:top_n])
    if output_excel:
        fn = f"断板匹配_{stock_code}_{cut_date_str}.xlsx"
        df.to_excel(fn, index=False, engine='openpyxl')
        print(f"\n已保存：{fn}")
    print(f"\nTop 10：")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(df.head(10).to_string(index=False))
    return df


if __name__ == '__main__':
    result = run_break_matching(
        stock_code='002342',
        cut_date_str='2026-01-21',
        search_start='20230101',
        search_end='20260331',
        top_n=50,
        output_excel=True
    )