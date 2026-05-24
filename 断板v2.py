"""
K线相似度匹配系统 - 断板版 v2.0
统一研究范围框架 + 涨停段完整评分 + M组微型结构
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

# ============================================================
# 配置
# ============================================================

CONFIG = {
    'cache_dir': '../stock_cache/',
    'zt_threshold': 0.098,
    'dt_threshold': -0.098,
    'volume_lookback': 3,
    'bad_board_volume_multiple': 3,
    'request_interval': 0.3,
    'max_retries': 3,
    'top_n': 50,

    # 断板序列参数
    'break_window_low': 10,
    'break_window_mid': 20,
    'break_window_high': 30,
    'cold_gap_max': 3,
    'combined_height_low': 0.40,
    'combined_height_high': 1.00,
    'combined_height_very_high': 2.00,

    # 形态阈值
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
    'upper_shadow_strong_threshold': 0.05,
    'lower_shadow_weak_threshold': -0.05,

    # 涨停段开盘涨幅
    'open_pct_high': 0.07,
    'open_pct_low': -0.05,

    # 启动位置
    'pre_rally_lookback': 20,
    'pre_rally_low': 0.15,
    'pre_rally_high': 0.25,

    # 首日振幅
    'first_day_amplitude_threshold': 0.03,

    # 综合高度
    'combined_height_threshold': 0.40,

    # 严重断板
    'severe_drawdown_threshold': 0.20,
    'severe_form_count': 3,
    'severe_pct_threshold': 0.20,

    # 高度回撤比
    'height_retracement_1': 0.10,
    'height_retracement_2': 0.25,

    # 密度
    'density_pct_threshold': 0.10,
    'break_period_pct_high': 0.10,
    'break_period_pct_low': -0.10,

    # 最大涨幅回看
    'max_rise_lookback': 30,

    # 硬匹配降级
    'downgrade_threshold': 30,
    'penalty_a_class': 15,

    # ===== A组：涨停段评分 =====
    'penalty_height_1': 15,
    'penalty_height_2': 23,
    'penalty_accel_duration': 3,
    'penalty_accel_count_1': 3,
    'penalty_accel_count_2': 8,
    'penalty_first_day': 8,
    'penalty_open_pct_1': 5,
    'penalty_open_pct_2': 12,
    'penalty_pre_rally_1': 5,
    'penalty_pre_rally_2': 15,
    'bonus_pre_rally': 5,
    'bonus_combined_height': 10,
    'bonus_special_type_perfect': 8,
    'penalty_special_type_partial': 10,
    'penalty_special_type_none': 25,
    'penalty_special_type_one_side_per': 10,
    'bonus_special_type_both_none': 2,
    'penalty_special_count_per': 3,
    'bonus_special_pos_match': 2,
    'penalty_special_pos_diff_type': 1,
    'penalty_special_pos_one_side': 1.5,
    'penalty_special_pos_same_group': 0.3,

    # A组封顶
    'a_cap_compact': 60,
    'a_cap_standard': 40,
    'a_cap_wide': 25,

    # ===== B组：断板期评分 =====
    'penalty_rise_cross_1': 20,
    'penalty_rise_cross_2': 30,
    'penalty_break_count': 20,
    'penalty_d2_emotion_mismatch': 8,
    'penalty_d3_mismatch': 10,
    'bonus_d3_exact': 5,
    'bonus_d3_both_none': 1,
    'bonus_d1_exact': 6,
    'bonus_d1_same_emotion': 3,
    'penalty_d1_mismatch': 15,
    'bonus_d2_exact': 5,
    'bonus_d2_same_emotion': 2,
    'bonus_touch_zt_match': 5,
    'bonus_touch_dt_match': 5,

    # B9断板涨跌幅连续值
    'break_pct_bonus_threshold': 0.05,
    'break_pct_bonus': 5,
    'break_pct_penalty_mid': 0.12,
    'break_pct_penalty_mid_val': 12,
    'break_pct_penalty_high': 0.25,
    'break_pct_penalty_high_val': 20,

    # B6密度矩阵（同档加分值）
    'density_match_bonus': 10,
    # B7跌停强度补充
    'dt_intensity_recover': 5,
    'dt_intensity_extra_penalty': 10,

    # B组封顶
    'b_cap_compact': 25,
    'b_cap_standard': 40,
    'b_cap_wide': 60,

    # ===== M组：微型结构 =====
    'micro_exact_bonus': 8,
    'micro_approx_bonus': 4,
    'micro_approx_penalty': 3,
    'micro_emotion_bonus': 0,
    'micro_emotion_penalty': 6,
    'micro_mismatch_penalty': 10,
    'micro_both_none_bonus': 3,

    # M-cut各天权重基础分
    'mcut_day0_base': 15,
    'mcut_day1_base': 8,
    'mcut_day2_base': 5,

    # M-start各天权重基础分
    'mstart_day0_base': 10,
    'mstart_day1_base': 6,
    'mstart_day2_base': 4,

    # ===== E组：切面日基础 =====
    'penalty_cut_volume': 10,

    # ===== F组+全局 =====
    'max_penalty_threshold': 999,
    'distance_multiplier': 10,
    'distance_top_n': 30,

    'case_library_cache': '../stock_cache/case_library_break_v20.pkl',
    'worker_count': max(1, cpu_count() - 1),
}

os.makedirs(CONFIG['cache_dir'], exist_ok=True)

# ============================================================
# 形态常量
# ============================================================

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

SPECIAL_TYPES = {'一字板', 'T字板', '地天板', '大长腿涨停', '秒板'}
ACCEL_GROUP = {'一字板', 'T字板', '秒板'}
SWAP_GROUP = {'普通涨停', '大长腿涨停', '地天板'}


# ============================================================
# 形态识别函数
# ============================================================

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


def is_same_special_group(type_a, type_b):
    if type_a in ACCEL_GROUP and type_b in ACCEL_GROUP:
        return True
    if type_a in SWAP_GROUP and type_b in SWAP_GROUP:
        return True
    return False
# ============================================================
# 数据加载
# ============================================================

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


def _migrate_old_cache():
    """一次性迁移旧缓存（daily_{code}_{start}_{end}.pkl → daily_{code}.pkl）"""
    cache_dir = CONFIG['cache_dir']
    if not os.path.exists(cache_dir):
        return

    import glob
    old_files = glob.glob(os.path.join(cache_dir, 'daily_*_*_*.pkl'))
    if not old_files:
        return

    migrate_flag = os.path.join(cache_dir, '_migrated_v2.flag')
    if os.path.exists(migrate_flag):
        return

    print(f"\n检测到 {len(old_files)} 个旧缓存文件，开始迁移...")
    merged = {}

    for fpath in old_files:
        fname = os.path.basename(fpath)
        parts = fname.replace('.pkl', '').split('_')
        if len(parts) < 4 or parts[0] != 'daily':
            continue
        code = parts[1]
        try:
            with open(fpath, 'rb') as f:
                df = pickle.load(f)
            if df is not None and len(df) > 0:
                if 'date' not in df.columns:
                    continue
                df['date'] = pd.to_datetime(df['date'])
                if code in merged:
                    merged[code] = pd.concat([merged[code], df], ignore_index=True)
                else:
                    merged[code] = df.copy()
        except Exception:
            continue

    saved_count = 0
    for code, df in merged.items():
        df = df.drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)
        new_path = os.path.join(cache_dir, f'daily_{code}.pkl')
        try:
            with open(new_path, 'wb') as f:
                pickle.dump(df, f)
            saved_count += 1
        except Exception:
            pass

    deleted = 0
    for fpath in old_files:
        try:
            os.remove(fpath)
            deleted += 1
        except Exception:
            pass

    with open(migrate_flag, 'w') as f:
        f.write(f'migrated {saved_count} stocks, deleted {deleted} old files')

    print(f"  迁移完成：合并 {saved_count} 只股票，删除 {deleted} 个旧文件")


def get_daily_data(stock_code, start_date, end_date, max_retries=3):
    """增量更新版：只下载缓存中缺失的日期范围"""
    cache_dir = CONFIG['cache_dir']
    new_cache = os.path.join(cache_dir, f'daily_{stock_code}.pkl')

    cached_df = None
    if os.path.exists(new_cache):
        try:
            with open(new_cache, 'rb') as f:
                cached_df = pickle.load(f)
            if cached_df is not None and len(cached_df) > 0:
                cached_df['date'] = pd.to_datetime(cached_df['date'])
                cached_df = cached_df.drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)
        except Exception:
            cached_df = None

    req_start = pd.to_datetime(start_date, format='%Y%m%d')
    req_end = pd.to_datetime(end_date, format='%Y%m%d')

    need_download = []
    if cached_df is not None and len(cached_df) > 0:
        cache_min = cached_df['date'].min()
        cache_max = cached_df['date'].max()

        if req_start < cache_min - pd.Timedelta(days=5):
            need_download.append((req_start.strftime('%Y%m%d'),
                                  (cache_min - pd.Timedelta(days=1)).strftime('%Y%m%d')))
        if req_end > cache_max + pd.Timedelta(days=5):
            need_download.append(((cache_max + pd.Timedelta(days=1)).strftime('%Y%m%d'),
                                  req_end.strftime('%Y%m%d')))
    else:
        need_download.append((start_date, end_date))

    if not need_download:
        mask = (cached_df['date'] >= req_start) & (cached_df['date'] <= req_end)
        result = cached_df[mask].reset_index(drop=True)
        return result if len(result) > 0 else None

    symbol = code_to_tencent_symbol(stock_code)
    new_parts = []
    for dl_start, dl_end in need_download:
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_daily(symbol=symbol, start_date=dl_start,
                                         end_date=dl_end, adjust="")
                if df is not None and len(df) > 0:
                    df = df.copy()
                    df['date'] = pd.to_datetime(df['date'])
                    new_parts.append(df)
                break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1 + attempt * 2)

    all_parts = []
    if cached_df is not None and len(cached_df) > 0:
        all_parts.append(cached_df)
    all_parts.extend(new_parts)

    if not all_parts:
        return None

    merged = pd.concat(all_parts, ignore_index=True)
    merged['date'] = pd.to_datetime(merged['date'])
    merged = merged.drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)

    try:
        with open(new_cache, 'wb') as f:
            pickle.dump(merged, f)
    except Exception:
        pass

    mask = (merged['date'] >= req_start) & (merged['date'] <= req_end)
    result = merged[mask].reset_index(drop=True)
    return result if len(result) > 0 else None


def batch_download_daily_data(stock_list, start_date, end_date):
    _migrate_old_cache()

    all_data = {}
    total = len(stock_list)
    success = failed = from_cache = downloaded = 0
    print(f"开始加载日K数据，共 {total} 只股票...")
    st = time.time()

    for i, row in stock_list.iterrows():
        code = row['code']
        new_cache = os.path.join(CONFIG['cache_dir'], f'daily_{code}.pkl')

        needs_net = True
        if os.path.exists(new_cache):
            try:
                with open(new_cache, 'rb') as f:
                    cached_df = pickle.load(f)
                if cached_df is not None and len(cached_df) > 0:
                    cached_df['date'] = pd.to_datetime(cached_df['date'])
                    cache_min = cached_df['date'].min()
                    cache_max = cached_df['date'].max()
                    req_start = pd.to_datetime(start_date, format='%Y%m%d')
                    req_end = pd.to_datetime(end_date, format='%Y%m%d')
                    if cache_min <= req_start + pd.Timedelta(days=5) and \
                       cache_max >= req_end - pd.Timedelta(days=5):
                        needs_net = False
            except Exception:
                pass

        df = get_daily_data(code, start_date, end_date, max_retries=CONFIG['max_retries'])
        if df is not None and len(df) > 0:
            all_data[code] = df
            success += 1
            if not needs_net:
                from_cache += 1
            else:
                downloaded += 1
        else:
            failed += 1

        if (i + 1) % 200 == 0 or (i + 1) == total:
            print(f"  {i + 1}/{total} ({(i + 1) / total * 100:.1f}%) | "
                  f"成功{success}(缓存{from_cache}+下载{downloaded}) | "
                  f"失败{failed} | {time.time() - st:.1f}秒")

        if needs_net:
            time.sleep(CONFIG['request_interval'])

    print(f"\n加载完成，成功{success}（缓存{from_cache}+下载{downloaded}）/ 失败{failed}")
    return all_data


# ============================================================
# 预计算
# ============================================================

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
    vol_labels = np.zeros(n, dtype=int)
    for i in range(vl, n):
        avg = volumes[i - vl:i].mean()
        if avg > 0 and volumes[i] < avg:
            vol_labels[i] = 1

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
            'vol_label': vol_labels[i], 'touched_zt': touched_zt[i],
            'touched_dt': touched_dt[i],
            'form': forms[i], 'emotion': emotions[i],
            'subdivision': subdivisions[i],
        })
    return rows
# ============================================================
# 断板序列识别
# ============================================================

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


# ============================================================
# 分类函数
# ============================================================

def classify_research_scope(days):
    if days <= 3:
        return '紧凑'
    elif days <= 6:
        return '标准'
    return '宽泛'


def classify_d1_distance(days):
    if days <= 3:
        return '近期'
    elif days <= 7:
        return '中期'
    return '后期'


def classify_max_rise(mr):
    if mr >= CONFIG['combined_height_very_high']:
        return '超高位'
    elif mr >= CONFIG['combined_height_high']:
        return '高位'
    elif mr >= CONFIG['combined_height_low']:
        return '中位'
    return '低位'


def classify_height_retracement(r):
    if r <= CONFIG['height_retracement_1']:
        return '未回撤'
    elif r <= CONFIG['height_retracement_2']:
        return '小幅回撤'
    return '大幅回撤'


def classify_board_height(h):
    if h <= 3:
        return '低位'
    elif h <= 6:
        return '中位'
    return '高位'


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
    return '单跌停'


def classify_open_pct(open_pct):
    if open_pct >= CONFIG['open_pct_high']:
        return '高开'
    elif open_pct <= CONFIG['open_pct_low']:
        return '低开'
    return '正常开'


def classify_pre_rally(pr):
    if pr < CONFIG['pre_rally_low']:
        return '低位启动'
    elif pr > CONFIG['pre_rally_high']:
        return '高位启动'
    return '中位启动'


def classify_first_day_state(amplitude):
    return '强势首板' if amplitude <= CONFIG['first_day_amplitude_threshold'] else '分歧首板'


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
# ============================================================
# 微型结构提取（统一函数）
# ============================================================

def build_micro_3day(rows, anchor_idx):
    """从锚点往前提取3天的形态细分类+情绪，统一用于M-cut和M-start"""
    result = []
    for offset in range(2, -1, -1):  # 前2天, 前1天, 当天
        idx = anchor_idx - offset
        if idx < 0 or idx >= len(rows):
            result.append({'form': '无', 'subdivision': '无', 'emotion': '震荡',
                           'approx_group': '震荡类', 'pct': 0.0, 'vol_label': 0})
        else:
            r = rows[idx]
            result.append({
                'form': r['form'],
                'subdivision': r['subdivision'],
                'emotion': r['emotion'],
                'approx_group': get_approx_group(r['subdivision']),
                'pct': r['pct'],
                'vol_label': r['vol_label'],
            })
    return result  # [前2天, 前1天, 当天]


# ============================================================
# 案例构建
# ============================================================

def build_break_case(stock_code, stock_name, rows, seq_info, cut_idx):
    seq_start = seq_info['seq_start']
    segments = seq_info['segments']
    break_periods = seq_info['break_periods']
    cut_row = rows[cut_idx]
    cut_date = cut_row['date']

    # ===== 研究范围 =====
    research_days = cut_idx - seq_start + 1
    research_scope = classify_research_scope(research_days)

    # ===== 涨停段基础 =====
    zt_days = sum(1 for s, e in segments for idx in range(s, min(e, cut_idx) + 1)
                  if rows[idx]['is_zt'])
    total_days = research_days
    zt_density = zt_days / total_days if total_days > 0 else 0

    first_close = rows[seq_start]['pre_close']
    if first_close == 0 or np.isnan(first_close):
        first_close = rows[seq_start]['open']

    # ===== A9首日状态 =====
    first_day_amplitude = 0.0
    if seq_start < len(rows):
        r0 = rows[seq_start]
        if r0['pre_close'] > 0 and not np.isnan(r0['pre_close']):
            first_day_amplitude = (r0['high'] - r0['low']) / r0['pre_close']
    first_day_state = classify_first_day_state(first_day_amplitude)

    # ===== A14启动位置 =====
    pre_rally_lookback = CONFIG['pre_rally_lookback']
    pre_idx = seq_start - 1
    if pre_idx >= 0:
        base_idx = max(0, pre_idx - pre_rally_lookback)
        base_close = rows[base_idx]['close']
        pre_rally = (rows[pre_idx]['close'] - base_close) / base_close if base_close > 0 else 0
    else:
        pre_rally = 0.0
    pre_rally_category = classify_pre_rally(pre_rally)

    # ===== A15综合高度 =====
    board_height = zt_days
    height_category = classify_board_height(board_height)
    combined_height_val = pre_rally + board_height * 0.10
    combined_height_category = '高位' if combined_height_val >= CONFIG['combined_height_threshold'] else '低位'

    # ===== A12开盘涨幅 =====
    cut_open_pct = cut_row['open_pct']
    cut_open_pct_category = classify_open_pct(cut_open_pct)

    # ===== A组板型相关 =====
    hs = {'一字板': 0, 'T字板': 0, '地天板': 0, '大长腿涨停': 0, '秒板': 0}
    sps = []
    vol_label_per_day = []
    for idx in range(seq_start, cut_idx + 1):
        f = rows[idx]['form']
        if rows[idx]['is_zt']:
            sps.append(f)
            if idx < cut_idx and f in hs:
                hs[f] += 1
        else:
            sps.append(f'[{f}]')
        vol_label_per_day.append(rows[idx]['vol_label'])
    hst = set(k for k, v in hs.items() if v > 0)

    # ===== A6/A7加速 =====
    ls = [rows[idx]['vol_label'] if rows[idx]['is_zt'] else 'X'
          for idx in range(seq_start, cut_idx + 1)]
    ma = streak = 0
    for lb_v in ls:
        if lb_v == 1:
            streak += 1
            ma = max(ma, streak)
        else:
            streak = 0
    max_accel_category = '长波' if ma >= 3 else '短波'

    accel_count = 0
    seq_labels = [rows[idx]['vol_label'] for idx in range(seq_start, cut_idx + 1)
                  if rows[idx]['is_zt']]
    for i in range(1, len(seq_labels)):
        if seq_labels[i - 1] == 0 and seq_labels[i] == 1:
            accel_count += 1
    accel_density = sum(seq_labels) / len(seq_labels) if seq_labels else 0.0

    # ===== 偏离度 =====
    deviation = 0.0
    if cut_row['volume'] > 0 and cut_row['close'] > 0:
        try:
            avg_price = (cut_row['high'] + cut_row['low'] + cut_row['close']) / 3.0
            deviation = (cut_row['close'] - avg_price) / cut_row['close']
        except Exception:
            pass

    # ===== 主断板 =====
    mbpi, is_severe = find_main_break(rows, break_periods, cut_idx)
    mb = break_periods[mbpi] if mbpi is not None else None

    # ===== 最大涨幅 =====
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

    # ===== 高度回撤比 =====
    cut_close = rows[cut_idx]['close']
    hr = (max_close_30 - cut_close) / max_close_30 if max_close_30 > 0 else 0
    hr_category = classify_height_retracement(hr)

    # ===== B组断板期指标 =====
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
    denc = '冷淡'
    bppc = '小涨'
    cut_to_d1 = 0
    bc = 0

    if mb is not None:
        bs, be = mb
        d1_idx = bs
        bad = min(be, cut_idx) - bs + 1
        bpd = cut_idx - bs + 1
        cut_to_d1 = cut_idx - bs

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

        zt_in_break = dt_in_break = 0
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
        bppc = '大涨' if bpp > CONFIG['break_period_pct_high'] else \
            '小涨' if bpp >= 0 else \
            '小跌' if bpp >= CONFIG['break_period_pct_low'] else '大跌'
        denc = classify_density(buc, bdc_count, bpp, ztdt_in_break)

    d1_distance_cat = classify_d1_distance(cut_to_d1)

    # 断板次数
    inz = False
    for idx in range(seq_start, cut_idx + 1):
        if rows[idx]['is_zt']:
            inz = True
        elif inz:
            bc += 1
            inz = False
    bc_cat = '1次' if bc <= 1 else '多次'

    # ===== M组微型结构 =====
    m_cut = build_micro_3day(rows, cut_idx)
    m_start = build_micro_3day(rows, seq_start)

    # ===== E组 =====
    cut_volume_state = '缩量' if cut_row['vol_label'] == 1 else '放量'

    # ===== 次日数据 =====
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

        # 全局
        'research_days': research_days, 'research_scope': research_scope,

        # A组
        'zt_days': zt_days, 'zt_density': zt_density,
        'board_height': board_height, 'height_category': height_category,
        'first_day_amplitude': first_day_amplitude, 'first_day_state': first_day_state,
        'pre_rally': pre_rally, 'pre_rally_category': pre_rally_category,
        'combined_height': combined_height_val, 'combined_height_category': combined_height_category,
        'cut_open_pct': cut_open_pct, 'cut_open_pct_category': cut_open_pct_category,
        'history_special': hs, 'history_special_types': hst,
        'has_history_special': len(hst) > 0,
        'special_position_seq': sps, 'volume_label_per_day': vol_label_per_day,
        'max_accel_duration': ma, 'max_accel_category': max_accel_category,
        'accel_count': accel_count, 'accel_density': accel_density,
        'deviation': deviation,

        # B组
        'max_rise': max_rise, 'max_rise_category': max_rise_category,
        'height_retracement': hr, 'height_retracement_category': hr_category,
        'is_severe_break': is_severe,
        'break_d1_form': d1f, 'break_d1_emotion': d1e,
        'break_d1_touched_zt': d1tz, 'break_d1_touched_dt': d1td,
        'break_d2_form': d2f, 'break_d2_emotion': d2e,
        'break_period_days': bpd, 'break_actual_days': bad,
        'cut_to_d1_days': cut_to_d1, 'd1_distance_cat': d1_distance_cat,
        'break_period_pct': bpp, 'break_period_pct_category': bppc,
        'break_d3plus_special_forms': d3sp,
        'big_up_count': buc, 'big_down_count': bdc_count,
        'density_category': denc, 'dt_intensity': dt_int,
        'break_count': bc, 'break_count_category': bc_cat,

        # M组
        'm_cut': m_cut, 'm_start': m_start,

        # E组
        'cut_form': cut_row['form'], 'cut_emotion': cut_row['emotion'],
        'cut_subdivision': cut_row['subdivision'],
        'cut_is_zt': cut_row['is_zt'], 'cut_pct': cut_row['pct'],
        'cut_volume_state': cut_volume_state,
        'cut_touched_zt': cut_row['touched_zt'], 'cut_touched_dt': cut_row['touched_dt'],

        # F组
        'label_sequence': ls,

        # 次日
        'next_day_pct': np_, 'next_day_is_zt': nz, 'next_day_open_pct': no,
    }


# ============================================================
# 案例库构建
# ============================================================

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
            mc = c['m_cut']
            cur_key = (
                str(c['seq_start_date'])[:10],
                mc[0]['subdivision'], mc[1]['subdivision'], mc[2]['subdivision'],
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


# ============================================================
# 研究范围权重工具
# ============================================================

def get_scope_weights(scope):
    """返回 (a_weight, b_weight, a_cap, b_cap)"""
    if scope == '紧凑':
        return 3.0, 0.3, CONFIG['a_cap_compact'], CONFIG['b_cap_compact']
    elif scope == '标准':
        return 2.0, 1.0, CONFIG['a_cap_standard'], CONFIG['b_cap_standard']
    return 1.0, 1.5, CONFIG['a_cap_wide'], CONFIG['b_cap_wide']


def get_scope_internal_boost(scope, indicator):
    """研究范围对A组内部指标的额外加权"""
    boosts = {
        '紧凑': {'A2': 1.5, 'A4': 1.5, 'A9': 1.5, 'A12': 1.3},
        '标准': {'A2': 1.2, 'A4': 1.2, 'A9': 1.2},
    }
    return boosts.get(scope, {}).get(indicator, 1.0)


def get_mcut_weight(scope, day_offset):
    """M-cut各天的研究范围加权，day_offset: 0=切面日,1=前1天,2=前2天"""
    weights = {
        '紧凑': {0: 1.3, 1: 1.3, 2: 1.2},
        '标准': {0: 1.0, 1: 1.0, 2: 1.0},
        '宽泛': {0: 1.3, 1: 1.2, 2: 1.0},
    }
    return weights.get(scope, {}).get(day_offset, 1.0)


def get_d1_weights(d1_cat):
    """距D1对B组内部的权重：返回 (d1_w, break_period_w)"""
    if d1_cat == '近期':
        return 1.5, 0.5
    elif d1_cat == '中期':
        return 1.0, 1.0
    return 0.8, 1.5


def get_d1_decay(d1_days):
    """微型结构双方无衰减系数"""
    if d1_days <= 3:
        return 1.0
    elif d1_days <= 7:
        return 0.6
    return 0.2


# ============================================================
# 硬匹配
# ============================================================

def hard_filter_with_downgrade(target_case, case_library):
    threshold = CONFIG['downgrade_threshold']
    tap = 0
    pa = CONFIG['penalty_a_class']
    scope = target_case['research_scope']
    current = [c for c in case_library if c['stock_code'] != target_case['stock_code']]
    print(f"  排除同股票：{len(current)}")

    # ===== B12 回撤比 =====
    f = [c for c in current
         if c['height_retracement_category'] == target_case['height_retracement_category']]
    if len(f) >= threshold:
        current = f
        print(f"  回撤比({target_case['height_retracement_category']})：{len(current)}")
    else:
        tap += pa
        print(f"  回撤比放开：{len(current)}（-{pa}）")

    # ===== B11 最大涨幅（差≥2档淘汰） =====
    rise_order = {'低位': 0, '中位': 1, '高位': 2, '超高位': 3}
    t_ro = rise_order.get(target_case['max_rise_category'], 1)
    f = [c for c in current
         if abs(rise_order.get(c['max_rise_category'], 1) - t_ro) <= 1]
    if len(f) >= threshold:
        current = f
        print(f"  涨幅(差≤1档)：{len(current)}")
    else:
        tap += pa
        print(f"  涨幅放开：{len(current)}（-{pa}）")

    # ===== B15 距D1 =====
    if target_case['cut_to_d1_days'] > 0:
        t_d1_cat = target_case['d1_distance_cat']
        f = [c for c in current if c['d1_distance_cat'] == t_d1_cat]
        if len(f) >= threshold:
            current = f
            print(f"  距D1({t_d1_cat})：{len(current)}")
        else:
            compat = {'近期': ('近期', '中期'), '中期': ('近期', '中期'), '后期': ('后期',)}
            allowed = compat.get(t_d1_cat, (t_d1_cat,))
            f = [c for c in current if c['d1_distance_cat'] in allowed]
            if len(f) >= threshold:
                current = f
                tap += pa
                print(f"  距D1互通({allowed})：{len(current)}（-{pa}）")
            else:
                tap += pa
                print(f"  距D1全放开：{len(current)}（-{pa}）")

    # ===== M-start 首板微型（紧凑档=硬匹配） =====
    if scope == '紧凑':
        tm = target_case['m_start']
        # 首板当天细分类匹配
        f = [c for c in current
             if match_subdivision(tm[2]['subdivision'], c['m_start'][2]['subdivision'])]
        if len(f) >= threshold:
            current = f
            print(f"  M-start首板({tm[2]['form']})：{len(current)}")
        else:
            f = [c for c in current
                 if match_approx(tm[2]['subdivision'], c['m_start'][2]['subdivision'])]
            if len(f) >= threshold:
                current = f
                tap += pa
                print(f"  M-start首板近似：{len(current)}（-{pa}）")
            else:
                tap += pa
                print(f"  M-start首板放开：{len(current)}（-{pa}）")

        # 首板前1天
        f = [c for c in current
             if match_approx(tm[1]['subdivision'], c['m_start'][1]['subdivision'])
             or tm[1]['subdivision'] == '无' or c['m_start'][1]['subdivision'] == '无']
        if len(f) >= threshold:
            current = f
            print(f"  M-start前1天：{len(current)}")
        else:
            tap += pa
            print(f"  M-start前1天放开：{len(current)}（-{pa}）")

    # ===== M-cut 切面日微型 =====
    tm_cut = target_case['m_cut']

    def _match_cut_exact(c):
        return match_subdivision(tm_cut[2]['subdivision'], c['m_cut'][2]['subdivision'])

    def _match_cut_approx(c):
        return match_approx(tm_cut[2]['subdivision'], c['m_cut'][2]['subdivision'])

    def _match_cut_d1_exact(c):
        return (_match_cut_exact(c) and
                match_approx(tm_cut[1]['subdivision'], c['m_cut'][1]['subdivision']))

    levels = [
        (_match_cut_d1_exact, "M-cut(切面精确+前1天近似)", 0),
        (_match_cut_exact, "M-cut(切面精确)", pa),
        (_match_cut_approx, "M-cut(切面近似)", pa),
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
        print(f"  M-cut全放开：{len(current)}（-{tap}）")

    # ===== B6 密度 =====
    if target_case['cut_to_d1_days'] > 0:
        td = target_case['density_category']
        f = [c for c in current if c['density_category'] == td]
        if len(f) >= threshold:
            current = f
            print(f"  密度({td})：{len(current)}")
        else:
            tap += pa
            print(f"  密度放开：{len(current)}（-{pa}）")

    # ===== B1 D1形态 =====
    if target_case['cut_to_d1_days'] > 0:
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


# ============================================================
# A组评分：涨停段
# ============================================================

def calc_a_score(tc, cc):
    """返回 (penalty, bonus, details)"""
    p = b = 0
    d = []
    scope = tc['research_scope']

    # A1连板高度（仅断板场景，纯连板由B11替代）
    if tc['cut_to_d1_days'] > 0:
        h_order = {'低位': 0, '中位': 1, '高位': 2}
        gap = abs(h_order.get(tc['height_category'], 1) - h_order.get(cc['height_category'], 1))
        if gap == 1:
            v = CONFIG['penalty_height_1']
            p += v
            d.append(f"连板高度跨1档-{v}")
        elif gap >= 2:
            v = CONFIG['penalty_height_2']
            p += v
            d.append(f"连板高度跨{gap}档-{v}")

    # A2特殊板型种类
    tt = tc['history_special_types']
    ct = cc['history_special_types']
    t_has = tc['has_history_special']
    c_has = cc['has_history_special']
    boost_a2 = get_scope_internal_boost(scope, 'A2')

    if not t_has and not c_has:
        v = round(CONFIG['bonus_special_type_both_none'] * boost_a2)
        b += v
        d.append(f"双方无特殊板型+{v}")
    elif t_has and not c_has:
        tc_ = len(tt)
        v = round(tc_ * CONFIG['penalty_special_type_one_side_per'] * boost_a2)
        p += v
        d.append(f"候选无特殊板型(标的有{tc_}种)-{v}")
    elif not t_has and c_has:
        cc_ = len(ct)
        v = round(cc_ * CONFIG['penalty_special_type_one_side_per'] * boost_a2)
        p += v
        d.append(f"标的无但候选有{cc_}种-{v}")
    else:
        if tt == ct:
            v = round(CONFIG['bonus_special_type_perfect'] * boost_a2)
            b += v
            d.append(f"板型种类完全一致+{v}")
        elif tt & ct:
            mc = len((tt - ct) | (ct - tt))
            v = round(mc * CONFIG['penalty_special_type_partial'] * boost_a2)
            p += v
            d.append(f"板型部分重合(差{mc}种)-{v}")
        else:
            v = round(CONFIG['penalty_special_type_none'] * boost_a2)
            p += v
            d.append(f"板型零交集-{v}")

    # A3特殊板型数量差异
    if t_has or c_has:
        all_types = set(list(tc['history_special'].keys()) + list(cc['history_special'].keys()))
        total_excess = sum(max(0, abs(tc['history_special'].get(t, 0) -
                                      cc['history_special'].get(t, 0)) - 1) for t in all_types)
        if total_excess > 0:
            v = total_excess * CONFIG['penalty_special_count_per']
            p += v
            d.append(f"板型数量差异(超{total_excess}个)-{v}")

    # A4特殊板型位置+亲疏
    boost_a4 = get_scope_internal_boost(scope, 'A4')
    if t_has and c_has:
        t_seq = tc['special_position_seq']
        c_seq = cc['special_position_seq']
        t_vol = tc.get('volume_label_per_day', [])
        c_vol = cc.get('volume_label_per_day', [])
        sp_set = SPECIAL_TYPES
        for i in range(min(len(t_seq), len(c_seq))):
            ts, cs = t_seq[i], c_seq[i]
            t_is = ts in sp_set
            c_is = cs in sp_set
            if t_is and c_is:
                if ts == cs:
                    v = round(CONFIG['bonus_special_pos_match'] * boost_a4)
                    b += v
                    d.append(f"第{i+1}板{ts}位置匹配+{v}")
                elif is_same_special_group(ts, cs):
                    tv = t_vol[i] if i < len(t_vol) else 0
                    cv = c_vol[i] if i < len(c_vol) else 0
                    if tv == cv:
                        v = round(CONFIG['penalty_special_pos_same_group'] * boost_a4)
                        p += v
                        d.append(f"第{i+1}板同组量能一致-{v}")
                    else:
                        v = round(CONFIG['penalty_special_pos_diff_type'] * boost_a4)
                        p += v
                        d.append(f"第{i+1}板同组量能不一致-{v}")
                else:
                    v = round(CONFIG['penalty_special_pos_diff_type'] * boost_a4)
                    p += v
                    d.append(f"第{i+1}板类型不同-{v}")
            elif t_is or c_is:
                v = round(CONFIG['penalty_special_pos_one_side'] * boost_a4)
                p += v
                d.append(f"第{i+1}板单方特殊-{v}")

    # A6加速持续
    if cc['max_accel_category'] != tc['max_accel_category']:
        p += CONFIG['penalty_accel_duration']
        d.append(f"加速持续不匹配-{CONFIG['penalty_accel_duration']}")

    # A7加速次数
    gap = abs(tc['accel_count'] - cc['accel_count'])
    if gap == 1:
        p += CONFIG['penalty_accel_count_1']
        d.append(f"加速次数差1-{CONFIG['penalty_accel_count_1']}")
    elif gap >= 2:
        p += CONFIG['penalty_accel_count_2']
        d.append(f"加速次数差{gap}-{CONFIG['penalty_accel_count_2']}")

    # A9首日状态
    boost_a9 = get_scope_internal_boost(scope, 'A9')
    if cc['first_day_state'] != tc['first_day_state']:
        v = round(CONFIG['penalty_first_day'] * boost_a9)
        p += v
        d.append(f"首日状态不匹配-{v}")

    # A14启动位置
    pr_order = {'低位启动': 0, '中位启动': 1, '高位启动': 2}
    pr_gap = abs(pr_order.get(tc['pre_rally_category'], 1) -
                 pr_order.get(cc['pre_rally_category'], 1))
    if pr_gap == 1:
        p += CONFIG['penalty_pre_rally_1']
        d.append(f"启动位置跨1档-{CONFIG['penalty_pre_rally_1']}")
    elif pr_gap >= 2:
        p += CONFIG['penalty_pre_rally_2']
        d.append(f"启动位置跨2档-{CONFIG['penalty_pre_rally_2']}")
    else:
        b += CONFIG['bonus_pre_rally']
        d.append(f"启动位置匹配+{CONFIG['bonus_pre_rally']}")

    # A15综合高度补偿
    h_mm = tc['height_category'] != cc['height_category']
    pr_mm = pr_gap > 0
    if (h_mm or pr_mm) and cc['combined_height_category'] == tc['combined_height_category']:
        pr_actual_penalty = 0
        if pr_gap == 1:
            pr_actual_penalty = CONFIG['penalty_pre_rally_1']
        elif pr_gap >= 2:
            pr_actual_penalty = CONFIG['penalty_pre_rally_2']
        max_compensation = max(1, round(pr_actual_penalty * 0.5))
        v = min(CONFIG['bonus_combined_height'], max_compensation)
        b += v
        d.append(f"综合高度同档+{v}")

    return p, b, d


# ============================================================
# B组评分：断板期
# ============================================================

def calc_b_score(tc, cc):
    """返回 (penalty, bonus, details)"""
    if tc['cut_to_d1_days'] == 0:
        return 0, 0, []

    p = b = 0
    d = []
    d1_w, bp_w = get_d1_weights(tc['d1_distance_cat'])

    # B11最大涨幅跨档
    rise_order = {'低位': 0, '中位': 1, '高位': 2, '超高位': 3}
    rg = abs(rise_order.get(tc['max_rise_category'], 1) -
             rise_order.get(cc['max_rise_category'], 1))
    if rg == 1:
        p += CONFIG['penalty_rise_cross_1']
        d.append(f"涨幅跨1档-{CONFIG['penalty_rise_cross_1']}")
    elif rg >= 2:
        p += CONFIG['penalty_rise_cross_2']
        d.append(f"涨幅跨{rg}档-{CONFIG['penalty_rise_cross_2']}")

    # B10断板次数
    if cc['break_count_category'] != tc['break_count_category']:
        v = round(CONFIG['penalty_break_count'] * bp_w)
        p += v
        d.append(f"断板次数-{v}")

    # B2 D2情绪
    if tc['break_actual_days'] > 1 and (tc['break_d2_form'] != '无' or cc['break_d2_form'] != '无'):
        if cc['break_d2_emotion'] != tc['break_d2_emotion']:
            v = round(CONFIG['penalty_d2_emotion_mismatch'] * bp_w)
            p += v
            d.append(f"D2情绪-{v}")

    # B9断板涨跌幅（连续值）
    pct_diff = abs(tc['break_period_pct'] - cc['break_period_pct'])
    if pct_diff <= CONFIG['break_pct_bonus_threshold']:
        v = round(CONFIG['break_pct_bonus'] * bp_w)
        b += v
        d.append(f"涨跌幅接近(差{pct_diff:.0%})+{v}")
    elif pct_diff > CONFIG['break_pct_penalty_high']:
        v = round(CONFIG['break_pct_penalty_high_val'] * bp_w)
        p += v
        d.append(f"涨跌幅差{pct_diff:.0%}-{v}")
    elif pct_diff > CONFIG['break_pct_penalty_mid']:
        v = round(CONFIG['break_pct_penalty_mid_val'] * bp_w)
        p += v
        d.append(f"涨跌幅差{pct_diff:.0%}-{v}")

    # B5 D3+
    if tc['break_actual_days'] > 1:
        td3, cd3 = tc['break_d3plus_special_forms'], cc['break_d3plus_special_forms']
        if not td3 and not cd3:
            v = round(CONFIG['bonus_d3_both_none'] * bp_w)
            b += v
            d.append(f"D3+双方无+{v}")
        elif td3 and cd3:
            if td3 == cd3:
                v = round(CONFIG['bonus_d3_exact'] * bp_w)
                b += v
                d.append(f"D3+一致+{v}")
            elif not (td3 & cd3):
                v = round(CONFIG['penalty_d3_mismatch'] * bp_w)
                p += v
                d.append(f"D3+零交集-{v}")
        else:
            v = round(CONFIG['penalty_d3_mismatch'] * bp_w)
            p += v
            d.append(f"D3+一方无-{v}")

    # B6密度 + B7跌停强度（方案C）
    ds = DENSITY_MATRIX.get((tc['density_category'], cc['density_category']), 0)
    ds = round(ds * bp_w)
    if ds > 0:
        b += ds
        d.append(f"密度+{ds}")
        # 密度同档，不看跌停强度
    elif ds < 0:
        p += abs(ds)
        d.append(f"密度{ds}")
        # 密度不匹配，跌停强度补充
        dt_order = {'无跌停': 0, '单跌停': 1, '连跌停': 2}
        t_dt = dt_order.get(tc['dt_intensity'], 0)
        c_dt = dt_order.get(cc['dt_intensity'], 0)
        dt_gap = abs(t_dt - c_dt)
        if dt_gap == 0:
            v = round(CONFIG['dt_intensity_recover'] * bp_w)
            b += v
            d.append(f"跌停强度同档补+{v}")
        elif dt_gap == 1:
            v = round(5 * bp_w)
            p += v
            d.append(f"跌停强度跨1档-{v}")
        elif dt_gap >= 2:
            v = round(CONFIG['dt_intensity_extra_penalty'] * bp_w)
            p += v
            d.append(f"跌停强度跨{dt_gap}档额外-{v}")

    # B1 D1加分/扣分
    if tc['break_d1_form'] != '无' and cc['break_d1_form'] != '无':
        if cc['break_d1_form'] == tc['break_d1_form']:
            v = round(CONFIG['bonus_d1_exact'] * d1_w)
            b += v
            d.append(f"D1精确+{v}")
        elif cc['break_d1_emotion'] == tc['break_d1_emotion']:
            v = round(CONFIG['bonus_d1_same_emotion'] * d1_w)
            b += v
            d.append(f"D1情绪+{v}")
        else:
            v = round(CONFIG['penalty_d1_mismatch'] * d1_w)
            p += v
            d.append(f"D1不匹配-{v}")

    # B2 D2加分
    if tc['break_actual_days'] > 1 and tc['break_d2_form'] != '无' and cc['break_d2_form'] != '无':
        if cc['break_d2_form'] == tc['break_d2_form']:
            b += CONFIG['bonus_d2_exact']
            d.append(f"D2精确+{CONFIG['bonus_d2_exact']}")
        elif cc['break_d2_emotion'] == tc['break_d2_emotion']:
            b += CONFIG['bonus_d2_same_emotion']
            d.append(f"D2情绪+{CONFIG['bonus_d2_same_emotion']}")

    # B3/B4触及
    if tc['break_d1_touched_zt'] and cc['break_d1_touched_zt']:
        v = round(CONFIG['bonus_touch_zt_match'] * d1_w)
        b += v
        d.append(f"D1触涨停+{v}")
    if tc['break_d1_touched_dt'] and cc['break_d1_touched_dt']:
        v = round(CONFIG['bonus_touch_dt_match'] * d1_w)
        b += v
        d.append(f"D1触跌停+{v}")

    return p, b, d


# ============================================================
# M组评分：微型结构
# ============================================================

def calc_micro_day_score(t_day, c_day, base_score, weight, decay):
    ts = t_day['subdivision']
    cs = c_day['subdivision']
    if ts == '无' and cs == '无':
        v = round(CONFIG['micro_both_none_bonus'] * decay * weight)
        return 0, v, f"双方无+{v}"
    if ts == '无' or cs == '无':
        v = round(base_score * 0.3 * weight)
        return v, 0, f"一方无-{v}"
    if match_subdivision(ts, cs):
        v = round(CONFIG['micro_exact_bonus'] * weight)
        return 0, v, f"精确({ts})+{v}"
    if match_approx(ts, cs):
        v = round(CONFIG['micro_approx_penalty'] * weight)
        return v, 0, f"近似({ts}vs{cs})-{v}"
    if match_emotion(t_day['emotion'], c_day['emotion']):
        v = round(CONFIG['micro_emotion_penalty'] * weight)
        return v, 0, f"情绪匹配-{v}"
    v = round(CONFIG['micro_mismatch_penalty'] * weight)
    return v, 0, f"不匹配({ts}vs{cs})-{v}"


def calc_mcut_score(tc, cc):
    """M-cut切面日微型结构评分"""
    p = b = 0
    d = []
    scope = tc['research_scope']
    decay = get_d1_decay(tc['cut_to_d1_days'])
    tm = tc['m_cut']
    cm = cc['m_cut']

    for i, label in enumerate(['前2天', '前1天', '切面日']):
        day_offset = 2 - i  # 2,1,0
        w = get_mcut_weight(scope, day_offset)
        dp, db, dd = calc_micro_day_score(tm[i], cm[i],
                                          CONFIG['micro_mismatch_penalty'], w, decay)
        p += dp
        b += db
        d.append(f"M-cut{label}:{dd}")

    return p, b, d


def calc_mstart_score(tc, cc):
    """M-start首板微型结构评分"""
    p = b = 0
    d = []
    scope = tc['research_scope']
    tm = tc['m_start']
    cm = cc['m_start']

    if scope == '宽泛':
        # 宽泛档：匹配才加分，不匹配不扣
        for i, label in enumerate(['前2天', '前1天', '首板']):
            ts = tm[i]['subdivision']
            cs = cm[i]['subdivision']
            if ts != '无' and cs != '无':
                if match_subdivision(ts, cs):
                    b += 3
                    d.append(f"M-start{label}匹配+3")
                elif match_approx(ts, cs):
                    b += 1
                    d.append(f"M-start{label}近似+1")
    elif scope == '标准':
        # 标准档：B类扣分
        for i, label in enumerate(['前2天', '前1天', '首板']):
            base = CONFIG['mstart_day0_base'] if i == 2 else \
                   CONFIG['mstart_day1_base'] if i == 1 else CONFIG['mstart_day2_base']
            dp, db, dd = calc_micro_day_score(tm[i], cm[i], base, 1.0, 1.0)
            p += dp
            b += db
            d.append(f"M-start{label}:{dd}")
    # 紧凑档已在硬匹配处理，这里只做精确匹配额外加分
    elif scope == '紧凑':
        for i, label in enumerate(['前2天', '前1天', '首板']):
            ts = tm[i]['subdivision']
            cs = cm[i]['subdivision']
            if ts != '无' and cs != '无' and match_subdivision(ts, cs):
                v = 5 if i == 2 else 3
                b += v
                d.append(f"M-start{label}精确+{v}")

    return p, b, d


# ============================================================
# E组评分：切面日基础
# ============================================================

def calc_e_score(tc, cc):
    p = b = 0
    d = []
    scope = tc['research_scope']

    # E1量能
    if not tc['cut_is_zt'] and not cc['cut_is_zt']:
        if cc['cut_volume_state'] != tc['cut_volume_state']:
            p += CONFIG['penalty_cut_volume']
            d.append(f"量能-{CONFIG['penalty_cut_volume']}")

    # E2触涨停/跌停
    if tc['cut_touched_zt'] and cc['cut_touched_zt']:
        b += CONFIG['bonus_touch_zt_match']
        d.append(f"触涨停+{CONFIG['bonus_touch_zt_match']}")
    if tc['cut_touched_dt'] and cc['cut_touched_dt']:
        b += CONFIG['bonus_touch_dt_match']
        d.append(f"触跌停+{CONFIG['bonus_touch_dt_match']}")

    # E3开盘涨幅（从A12移入）
    boost_e3 = get_scope_internal_boost(scope, 'A12')
    op_order = {'低开': 0, '正常开': 1, '高开': 2}
    op_gap = abs(op_order.get(tc['cut_open_pct_category'], 1) -
                 op_order.get(cc['cut_open_pct_category'], 1))
    if op_gap == 1:
        v = round(CONFIG['penalty_open_pct_1'] * boost_e3)
        p += v
        d.append(f"开盘涨幅跨1档-{v}")
    elif op_gap >= 2:
        v = round(CONFIG['penalty_open_pct_2'] * boost_e3)
        p += v
        d.append(f"开盘涨幅跨2档-{v}")

    return p, b, d


# ============================================================
# 汇总评分 + 封顶
# ============================================================

def calc_final_score(tc, cands, ap):
    mp = CONFIG['max_penalty_threshold']
    scope = tc['research_scope']
    a_w, b_w, a_cap, b_cap = get_scope_weights(scope)
    scored = []

    for c in cands:
        # A组
        a_p, a_b, a_d = calc_a_score(tc, c)
        a_net = round((a_p - a_b) * a_w)
        if a_net > a_cap:
            a_d.append(f"A组封顶({a_net}→{a_cap})")
            a_net = a_cap
        elif a_net < -a_cap:
            a_net = -a_cap

        # B组
        b_p, b_b, b_d = calc_b_score(tc, c)
        b_net = round((b_p - b_b) * b_w)
        if b_net > b_cap:
            b_d.append(f"B组封顶({b_net}→{b_cap})")
            b_net = b_cap
        elif b_net < -b_cap:
            b_net = -b_cap

        # M-cut
        mc_p, mc_b, mc_d = calc_mcut_score(tc, c)
        # M-start
        ms_p, ms_b, ms_d = calc_mstart_score(tc, c)
        # E组
        e_p, e_b, e_d = calc_e_score(tc, c)

        # 汇总
        total_p = ap + max(0, a_net) + max(0, b_net) + mc_p + ms_p + e_p
        total_b = abs(min(0, a_net)) + abs(min(0, b_net)) + mc_b + ms_b + e_b

        if (total_p - total_b) >= mp:
            continue

        det = []
        if ap > 0:
            det.append(f"硬匹配降级-{ap}")
        det.extend(a_d)
        det.extend(b_d)
        det.extend(mc_d)
        det.extend(ms_d)
        det.extend(e_d)

        c['individual_penalty'] = total_p
        c['individual_bonus'] = total_b
        c['penalty_details'] = det
        scored.append(c)

    print(f"  扣分过滤(净扣≥{mp})：{len(scored)}")
    return scored


# ============================================================
# F组：欧氏距离
# ============================================================

def calc_distance(tc, cands):
    if not cands:
        return []

    def feat(c):
        return np.array([
            c['max_rise'], c['height_retracement'], c['break_period_pct'],
            c['zt_density'], c['cut_to_d1_days'], c['accel_density'],
            c['deviation'],
        ], dtype=float)

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
    seen_stocks = set()
    deduped = []
    for c in result:
        if c['stock_code'] not in seen_stocks:
            deduped.append(c)
            seen_stocks.add(c['stock_code'])
    result = deduped
    for c in result:
        c.pop('_ss', None)
    return result


# ============================================================
# 输出格式化
# ============================================================

def format_output(tc, ranked, top_n=None):
    if top_n is None:
        top_n = CONFIG['top_n']
    rows = []
    for rank, c in enumerate(ranked[:top_n], 1):
        hsp = [f"{k}×{v}" for k, v in c['history_special'].items() if v > 0]
        sc = c['final_score']
        gr = '✅高' if sc >= 80 else '⚠️中' if sc >= 60 else '❌低'
        d3 = ', '.join(sorted(c['break_d3plus_special_forms'])) or '无'
        mc = c['m_cut']
        ms = c['m_start']
        rows.append({
            '排名': rank, '代码': c['stock_code'], '名称': c['stock_name'],
            '切面日': str(c['cut_date'])[:10],
            '最终得分': c['final_score'], '结构分': c['structure_score'],
            '距离扣分': c['distance_penalty'], '相似度': gr,
            '研究范围': f"{c['research_days']}天({c['research_scope']})",
            '扣分明细': c['penalty_detail'],
            # A组
            '连板高度': c['board_height'], '高度档': c['height_category'],
            '首日状态': c['first_day_state'],
            '启动位置': c['pre_rally_category'],
            '综合高度': f"{c['combined_height']:.1%}({c['combined_height_category']})",
            '开盘涨幅': f"{c['cut_open_pct']:.2%}({c['cut_open_pct_category']})",
            '加速': f"{c['max_accel_duration']}天({c['max_accel_category']})",
            '加速次数': c['accel_count'],
            '历史板型': ', '.join(hsp) or '无',
            '板型序列': '→'.join(c['special_position_seq']),
            # B组
            '最大涨幅': f"{c['max_rise']:.1%}({c['max_rise_category']})",
            '回撤比': f"{c['height_retracement']:.1%}({c['height_retracement_category']})",
            '断板类型': '严重' if c['is_severe_break'] else '普通',
            '距D1': f"{c['cut_to_d1_days']}天({c['d1_distance_cat']})",
            'D1形态': f"{c['break_d1_form']}({c['break_d1_emotion']})",
            'D2形态': f"{c['break_d2_form']}({c['break_d2_emotion']})",
            '断板次数': f"{c['break_count']}({c['break_count_category']})",
            '断板涨跌幅': f"{c['break_period_pct']:.2%}({c['break_period_pct_category']})",
            '密度': c['density_category'],
            '涨数': c['big_up_count'], '跌数': c['big_down_count'],
            '跌停强度': c['dt_intensity'],
            'D3+': d3,
            # M组
            'M-cut': f"{mc[0]['form']}→{mc[1]['form']}→{mc[2]['form']}",
            'M-start': f"{ms[0]['form']}→{ms[1]['form']}→{ms[2]['form']}",
            # E组
            '切面形态': f"{c['cut_form']}({c['cut_emotion']})",
            '切面涨跌': f"{c['cut_pct']:.2%}",
            '切面量能': c['cut_volume_state'],
            # 次日
            '次日涨跌': f"{c['next_day_pct']:.2%}" if c['next_day_pct'] is not None else '无',
            '次日涨停': '是' if c['next_day_is_zt'] else '否' if c['next_day_is_zt'] is not None else '无',
            '次日开盘': f"{c['next_day_open_pct']:.2%}" if c['next_day_open_pct'] is not None else '无',
        })
    return pd.DataFrame(rows)


# ============================================================
# 打印函数
# ============================================================

def print_target_info(tc):
    hsp = [f"{k}×{v}" for k, v in tc['history_special'].items() if v > 0]
    d3 = ', '.join(sorted(tc['break_d3plus_special_forms'])) or '无'
    sv = '⚠️严重' if tc['is_severe_break'] else '普通'
    mc = tc['m_cut']
    ms = tc['m_start']
    print("\n" + "=" * 70)
    print(f"标的股信息（断板版 v2.0）")
    print("=" * 70)
    print(f"  代码：{tc['stock_code']}  名称：{tc['stock_name']}")
    print(f"  切面日：{str(tc['cut_date'])[:10]}")
    print(f"  研究范围：{tc['research_days']}天({tc['research_scope']})")
    print(f"  断板类型：{sv}  距D1:{tc['cut_to_d1_days']}天({tc['d1_distance_cat']})")
    print(f"  最大涨幅：{tc['max_rise']:.1%}({tc['max_rise_category']})")
    print(f"  高度回撤比：{tc['height_retracement']:.1%}({tc['height_retracement_category']})")
    print(f"  连板高度：{tc['board_height']}板({tc['height_category']})")
    print(f"  首日状态：{tc['first_day_state']}  启动位置：{tc['pre_rally_category']}")
    print(f"  综合高度：{tc['combined_height']:.1%}({tc['combined_height_category']})")
    print(f"  开盘涨幅：{tc['cut_open_pct']:.2%}({tc['cut_open_pct_category']})")
    print(f"  加速：{tc['max_accel_duration']}天({tc['max_accel_category']}) 次数：{tc['accel_count']}")
    print(f"  历史板型：{', '.join(hsp) or '无'}")
    print(f"  序列：{'→'.join(tc['special_position_seq'])}")
    print(f"  D1：{tc['break_d1_form']}({tc['break_d1_emotion']})")
    print(f"  D2：{tc['break_d2_form']}({tc['break_d2_emotion']})")
    print(f"  断板：{tc['break_count']}次({tc['break_count_category']})")
    print(f"  断板涨跌幅：{tc['break_period_pct']:.2%}({tc['break_period_pct_category']})")
    print(f"  密度：{tc['density_category']}(涨{tc['big_up_count']}/跌{tc['big_down_count']}) "
          f"跌停强度：{tc['dt_intensity']}")
    print(f"  D3+：{d3}")
    print(f"  M-cut：{mc[0]['form']}({mc[0]['subdivision']}) → "
          f"{mc[1]['form']}({mc[1]['subdivision']}) → "
          f"{mc[2]['form']}({mc[2]['subdivision']})")
    print(f"  M-start：{ms[0]['form']}({ms[0]['subdivision']}) → "
          f"{ms[1]['form']}({ms[1]['subdivision']}) → "
          f"{ms[2]['form']}({ms[2]['subdivision']})")
    print(f"  切面日：{tc['cut_form']}({tc['cut_emotion']}) "
          f"涨跌:{tc['cut_pct']:.2%} 量能:{tc['cut_volume_state']}")
    print("=" * 70)


def print_summary(ranked):
    valid = [c for c in ranked if c['next_day_pct'] is not None]
    if not valid:
        return
    pcts = [c['next_day_pct'] for c in valid]
    zt = sum(1 for c in valid if c['next_day_is_zt'])
    print(f"\n统计({len(valid)}个): 平均{np.mean(pcts):.2%} 中位{np.median(pcts):.2%} "
          f"上涨{sum(1 for p in pcts if p > 0) / len(pcts):.1%} 涨停{zt / len(valid):.1%}")


# ============================================================
# 入口函数
# ============================================================

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
    print(f"K线相似（断板版）v2.0 | {stock_code} | {cut_date_str}")
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
        print("\n⚠️ 硬匹配后无案例")
        return pd.DataFrame()
    scored = calc_final_score(tc, cands, ap)
    if not scored:
        print("\n⚠️ 扣分过滤后无案例")
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
        search_end='20260514',
        top_n=50,
        output_excel=True
    )