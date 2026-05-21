"""
K线相似度匹配系统 v2.3
新增：开盘涨幅 + 特殊板型亲疏 + 单方特殊按种类数扣分
修正：大长腿优先级 + 连板高度跨档分级 + 特殊板型数量差异扣分
"""

import os
import time
import warnings
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import akshare as ak

warnings.filterwarnings('ignore')

CONFIG = {
    'cache_dir': './stock_cache/',
    'zt_threshold': 0.098,
    'volume_lookback': 3,
    'bad_board_volume_multiple': 3,
    'volume_state_expand_ratio': 1.4,
    'deviation_high': 0.01,
    'deviation_low': -0.01,
    'amplitude_low': 0.05,
    'amplitude_high': 0.10,
    'first_day_amplitude_threshold': 0.03,
    'big_leg_threshold': 0.095,
    'dtb_amplitude_threshold': 0.16,
    'pre_rally_lookback': 20,
    'pre_rally_low': 0.15,
    'pre_rally_high': 0.25,
    'combined_height_threshold': 0.40,
    'downgrade_threshold': 5,
    'top_n': 50,
    'request_interval': 0.3,
    'max_retries': 3,

    'max_penalty_threshold': 40,

    # 连板高度：跨1档和跨2档分别扣分
    'penalty_height_1': 15,
    'penalty_height_2': 23,

    'penalty_accel_duration': 3,
    'penalty_first_day': 8,
    'penalty_amplitude': 5,
    'penalty_volume_state': 8,
    'penalty_board_strength': 5,

    'bonus_special_type_perfect': 8,
    'penalty_special_type_partial': 10,
    'penalty_special_type_none': 25,
    'penalty_special_type_one_side_per': 10,
    'bonus_special_type_both_none': 2,

    # 特殊板型数量差异：差≥2时每多1个扣分
    'penalty_special_count_per': 3,

    'bonus_special_pos_match': 2,
    'penalty_special_pos_diff_type': 1,
    'penalty_special_pos_one_side': 1.5,
    'penalty_special_pos_same_group': 0.3,

    'bonus_cut_special_match': 5,
    'penalty_cut_special_mismatch': 8,

    'penalty_accel_count_1': 3,
    'penalty_accel_count_2': 8,

    'penalty_pre_rally_1': 5,
    'penalty_pre_rally_2': 15,

    'bonus_pre_rally': 5,
    'bonus_combined_height': 10,

    'distance_multiplier': 5,

    'open_pct_high': 0.07,
    'open_pct_low': -0.05,
    'penalty_open_pct_1': 5,
    'penalty_open_pct_2': 12,

    'case_library_cache': './stock_cache/case_library_v23c.pkl',
    'distance_top_n': 30,
}

os.makedirs(CONFIG['cache_dir'], exist_ok=True)

SPECIAL_TYPES = ['一字板', 'T字板', '地天板', '大长腿', '秒板']
ACCEL_GROUP = {'一字板', 'T字板', '秒板'}
SWAP_GROUP = {'普通涨停', '大长腿', '地天板'}


def get_main_board_stock_list():
    print("正在获取股票列表...")
    stock_info = ak.stock_info_a_code_name()
    main_board_mask = stock_info['code'].str.match(r'^(600|601|603|000|001|002|003)')
    not_st_mask = ~stock_info['name'].str.contains('ST', case=False, na=False)
    result = stock_info[main_board_mask & not_st_mask].reset_index(drop=True)
    print(f"筛选完成，共 {len(result)} 只主板非ST股票")
    return result


def code_to_tencent_symbol(code):
    if code.startswith(('600', '601', '603')):
        return f"sh{code}"
    else:
        return f"sz{code}"


def get_daily_data(stock_code, start_date, end_date, max_retries=3):
    cache_file = os.path.join(CONFIG['cache_dir'],
                              f"daily_{stock_code}_{start_date}_{end_date}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    symbol = code_to_tencent_symbol(stock_code)
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, period="daily",
                                     start_date=start_date, end_date=end_date, adjust="")
            if df is not None and len(df) > 0:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                with open(cache_file, 'wb') as f:
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
    start_time = time.time()
    for i, row in stock_list.iterrows():
        code = row['code']
        cache_file = os.path.join(CONFIG['cache_dir'],
                                  f"daily_{code}_{start_date}_{end_date}.pkl")
        is_cached = os.path.exists(cache_file)
        df = get_daily_data(code, start_date, end_date, max_retries=CONFIG['max_retries'])
        if df is not None and len(df) > 0:
            all_data[code] = df
            success += 1
            if is_cached:
                from_cache += 1
        else:
            failed += 1
        if (i + 1) % 200 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            print(f"  进度：{i+1}/{total} ({(i+1)/total*100:.1f}%) | "
                  f"成功{success}(缓存{from_cache}) | 失败{failed} | {elapsed:.1f}秒")
        if not is_cached:
            time.sleep(CONFIG['request_interval'])
    print(f"\n加载完成，成功{success}（缓存{from_cache}）/ 失败{failed}")
    return all_data
def identify_zt_days(daily_df):
    df = daily_df.copy()
    df['pre_close'] = df['close'].shift(1)
    df['real_pct'] = (df['close'] - df['pre_close']) / df['pre_close']
    df['is_zt'] = df['real_pct'] >= CONFIG['zt_threshold']
    df['zt_price'] = (df['pre_close'] * 1.1).round(2)
    return df


def find_consecutive_zt_sequences(daily_df):
    sequences = []
    i = 0
    n = len(daily_df)
    while i < n:
        if daily_df.iloc[i]['is_zt']:
            start = i
            while i < n and daily_df.iloc[i]['is_zt']:
                i += 1
            end = i - 1
            if end - start >= 1:
                sequences.append((start, end))
        else:
            i += 1
    return sequences


def calculate_01_label(daily_df, idx, volume_lookback=3):
    if idx < volume_lookback:
        return 0
    current_volume = daily_df.iloc[idx]['volume']
    prev_volumes = daily_df.iloc[idx - volume_lookback: idx]['volume']
    avg_volume = prev_volumes.mean()
    if avg_volume == 0:
        return 0
    return 1 if current_volume < avg_volume else 0


def calculate_board_strength(daily_df, idx, volume_lookback=3):
    row = daily_df.iloc[idx]
    open_price, close_price, zt_price = row['open'], row['close'], row['zt_price']
    if abs(open_price - zt_price) < 0.01 and abs(close_price - zt_price) < 0.01:
        return '一字'
    current_volume = row['volume']
    if idx < volume_lookback:
        avg_volume = current_volume
    else:
        avg_volume = daily_df.iloc[idx - volume_lookback: idx]['volume'].mean()
    if avg_volume == 0:
        return '换手'
    volume_ratio = current_volume / avg_volume
    if volume_ratio < 1.0:
        return '硬板'
    elif volume_ratio < CONFIG['bad_board_volume_multiple']:
        return '换手'
    else:
        return '烂板'


def classify_special_board(daily_df, idx):
    """
    优先级：1.一字板 2.地天板 3.大长腿 4.T字板 5.秒板 6.普通涨停
    大长腿：实体>9.5% 或 高开≥7.5%且振幅>9.8% 或 T字形态但振幅>9.8%
    T字板：开=收=涨停且低<涨停，振幅≤9.8%
    """
    row = daily_df.iloc[idx]
    if not row['is_zt']:
        return '非涨停'
    open_price, close_price = row['open'], row['close']
    low_price, high_price = row['low'], row['high']
    zt_price, pre_close = row['zt_price'], row['pre_close']

    # 优先级1：一字板
    if (abs(open_price - zt_price) < 0.01 and abs(close_price - zt_price) < 0.01
            and abs(low_price - zt_price) < 0.01):
        return '一字板'

    # 优先级2：地天板
    if pre_close > 0:
        if (high_price - low_price) / pre_close > CONFIG['dtb_amplitude_threshold']:
            return '地天板'

    # 优先级3：大长腿（三种情况）
    if pre_close > 0:
        body_pct = (close_price - open_price) / pre_close
        open_pct = (open_price - pre_close) / pre_close
        amplitude = (high_price - low_price) / pre_close
        if body_pct > CONFIG['big_leg_threshold']:
            return '大长腿'
        if open_pct >= 0.075 and amplitude > 0.098:
            return '大长腿'
        if (abs(open_price - zt_price) < 0.01 and abs(close_price - zt_price) < 0.01
                and low_price < zt_price - 0.01 and amplitude > 0.098):
            return '大长腿'

    # 优先级4：T字板（振幅≤9.8%才算）
    if (abs(open_price - zt_price) < 0.01 and abs(close_price - zt_price) < 0.01
            and low_price < zt_price - 0.01):
        return 'T字板'

    # 优先级5：秒板
    if pre_close > 0:
        if (open_price - pre_close) / pre_close >= 0.075:
            return '秒板'

    return '普通涨停'


def calculate_deviation(daily_df, idx):
    row = daily_df.iloc[idx]
    if row['volume'] == 0 or row['close'] == 0:
        return 0.0
    avg_price = row['amount'] / row['volume']
    return (row['close'] - avg_price) / row['close']


def calculate_amplitude(daily_df, idx):
    row = daily_df.iloc[idx]
    if row['pre_close'] == 0:
        return 0.0
    return (row['high'] - row['low']) / row['pre_close']


def calculate_open_pct(daily_df, idx):
    row = daily_df.iloc[idx]
    pre_close = row['pre_close']
    if pre_close == 0 or pd.isna(pre_close):
        return 0.0
    return (row['open'] - pre_close) / pre_close


def classify_open_pct(open_pct):
    if open_pct >= CONFIG['open_pct_high']:
        return '高开'
    elif open_pct <= CONFIG['open_pct_low']:
        return '低开'
    return '正常开'


def calculate_open_pct_penalty(target_cat, cand_cat):
    order = {'低开': 0, '正常开': 1, '高开': 2}
    gap = abs(order.get(target_cat, 1) - order.get(cand_cat, 1))
    if gap == 0:
        return 0
    elif gap == 1:
        return CONFIG['penalty_open_pct_1']
    return CONFIG['penalty_open_pct_2']


def is_same_special_group(type_a, type_b):
    if type_a in ACCEL_GROUP and type_b in ACCEL_GROUP:
        return True
    if type_a in SWAP_GROUP and type_b in SWAP_GROUP:
        return True
    return False


def calculate_volume_ratio_vs_yesterday(daily_df, idx):
    if idx < 1:
        return 1.0
    y = daily_df.iloc[idx - 1]['volume']
    return daily_df.iloc[idx]['volume'] / y if y > 0 else 1.0


def calculate_volume_ratio_vs_3day(daily_df, idx, volume_lookback=3):
    if idx < volume_lookback:
        return 1.0
    avg = daily_df.iloc[idx - volume_lookback: idx]['volume'].mean()
    return daily_df.iloc[idx]['volume'] / avg if avg > 0 else 1.0


def calculate_first_day_amplitude(daily_df, seq_start):
    row = daily_df.iloc[seq_start]
    if row['pre_close'] == 0 or pd.isna(row['pre_close']):
        return 0.0
    return (row['high'] - row['low']) / row['pre_close']


def classify_volume_state(vr):
    if vr < 1.0:
        return '缩量'
    elif vr < CONFIG['volume_state_expand_ratio']:
        return '平量'
    return '放量'


def classify_deviation(d):
    if d > CONFIG['deviation_high']:
        return '强锁仓'
    elif d < CONFIG['deviation_low']:
        return '弱出货'
    return '均势'


def classify_board_height(h):
    if h <= 3:
        return '低位'
    elif h <= 6:
        return '中位'
    return '高位'


def classify_max_accel_duration(d):
    return '长波' if d >= 3 else '短波'


def classify_amplitude(a):
    if a < CONFIG['amplitude_low']:
        return '低振幅'
    elif a > CONFIG['amplitude_high']:
        return '高振幅'
    return '中振幅'


def classify_first_day_state(a):
    return '强势首板' if a <= CONFIG['first_day_amplitude_threshold'] else '分歧首板'


def calculate_pre_rally(daily_df, seq_start):
    lookback = CONFIG['pre_rally_lookback']
    pre_idx = seq_start - 1
    if pre_idx < 0:
        return 0.0
    base_idx = max(0, pre_idx - lookback)
    base_close = daily_df.iloc[base_idx]['close']
    if base_close == 0:
        return 0.0
    return (daily_df.iloc[pre_idx]['close'] - base_close) / base_close


def classify_pre_rally(pr):
    if pr < CONFIG['pre_rally_low']:
        return '低位启动'
    elif pr > CONFIG['pre_rally_high']:
        return '高位启动'
    return '中位启动'


def calculate_combined_height(pre_rally, board_height):
    return pre_rally + board_height * 0.10


def classify_combined_height(ch):
    return '低位' if ch < CONFIG['combined_height_threshold'] else '高位'


def calculate_pre_rally_penalty(t_cat, c_cat):
    order = {'低位启动': 0, '中位启动': 1, '高位启动': 2}
    gap = abs(order.get(t_cat, 1) - order.get(c_cat, 1))
    if gap == 0:
        return 0
    elif gap == 1:
        return CONFIG['penalty_pre_rally_1']
    return CONFIG['penalty_pre_rally_2']


def calculate_accel_count_penalty(t_count, c_count):
    gap = abs(t_count - c_count)
    if gap == 0:
        return 0
    elif gap == 1:
        return CONFIG['penalty_accel_count_1']
    return CONFIG['penalty_accel_count_2']


def calculate_height_penalty(target_cat, cand_cat):
    """连板高度跨档扣分：跨1档和跨2档分开扣"""
    order = {'低位': 0, '中位': 1, '高位': 2}
    gap = abs(order.get(target_cat, 1) - order.get(cand_cat, 1))
    if gap == 0:
        return 0
    elif gap == 1:
        return CONFIG['penalty_height_1']
    return CONFIG['penalty_height_2']


def calculate_special_count_penalty(target_special, cand_special):
    """特殊板型数量差异扣分：按每种分别算，差≤1不扣，差≥2每多1个扣分"""
    all_types = set(list(target_special.keys()) + list(cand_special.keys()))
    total_excess = 0
    for sp_type in all_types:
        t_count = target_special.get(sp_type, 0)
        c_count = cand_special.get(sp_type, 0)
        diff = abs(t_count - c_count)
        if diff >= 2:
            total_excess += (diff - 1)
    if total_excess == 0:
        return 0, ''
    penalty = total_excess * CONFIG['penalty_special_count_per']
    return penalty, f"特殊板型数量差异(超{total_excess}个)-{penalty}"


def build_case_from_sequence(stock_code, stock_name, daily_df, seq_start, seq_end, cut_idx):
    lookback = CONFIG['volume_lookback']
    cut_row = daily_df.iloc[cut_idx]
    cut_date = cut_row['date']
    board_height = cut_idx - seq_start + 1

    label_today = calculate_01_label(daily_df, cut_idx, lookback)
    label_yesterday = calculate_01_label(daily_df, cut_idx - 1, lookback) if cut_idx >= 1 else 0
    end_pattern = f"{label_yesterday}→{label_today}"

    sequence_labels = []
    for i in range(seq_start, cut_idx + 1):
        sequence_labels.append(calculate_01_label(daily_df, i, lookback))

    accel_count = 0
    for i in range(1, len(sequence_labels)):
        if sequence_labels[i - 1] == 0 and sequence_labels[i] == 1:
            accel_count += 1

    max_accel_duration = current_streak = 0
    for label in sequence_labels:
        if label == 1:
            current_streak += 1
            max_accel_duration = max(max_accel_duration, current_streak)
        else:
            current_streak = 0

    accel_density = sum(sequence_labels) / len(sequence_labels) if sequence_labels else 0.0
    first_day_amplitude = calculate_first_day_amplitude(daily_df, seq_start)
    first_day_state = classify_first_day_state(first_day_amplitude)
    pre_rally = calculate_pre_rally(daily_df, seq_start)
    pre_rally_category = classify_pre_rally(pre_rally)
    combined_height = calculate_combined_height(pre_rally, board_height)
    combined_height_category = classify_combined_height(combined_height)

    history_special = {'一字板': 0, 'T字板': 0, '地天板': 0, '大长腿': 0, '秒板': 0}
    special_position_seq = []
    volume_label_per_day = []

    for i in range(seq_start, cut_idx + 1):
        sp = classify_special_board(daily_df, i)
        special_position_seq.append(sp)
        volume_label_per_day.append(calculate_01_label(daily_df, i, lookback))
        if i < cut_idx and sp in history_special:
            history_special[sp] += 1

    history_special_types = set(k for k, v in history_special.items() if v > 0)
    has_history_special = len(history_special_types) > 0
    cut_special = classify_special_board(daily_df, cut_idx)
    board_strength = calculate_board_strength(daily_df, cut_idx, lookback)
    deviation = calculate_deviation(daily_df, cut_idx)
    amplitude = calculate_amplitude(daily_df, cut_idx)
    volume_ratio_vs_yesterday = calculate_volume_ratio_vs_yesterday(daily_df, cut_idx)
    volume_state = classify_volume_state(volume_ratio_vs_yesterday)
    volume_ratio_vs_3day = calculate_volume_ratio_vs_3day(daily_df, cut_idx, lookback)
    open_pct = calculate_open_pct(daily_df, cut_idx)
    open_pct_category = classify_open_pct(open_pct)

    height_category = classify_board_height(board_height)
    max_accel_category = classify_max_accel_duration(max_accel_duration)
    deviation_category = classify_deviation(deviation)
    amplitude_category = classify_amplitude(amplitude)
    board_strength_l2 = '加速' if board_strength in ['一字', '硬板'] else '分歧'

    next_day_pct = next_day_is_zt = next_day_open_pct = None
    if cut_idx + 1 < len(daily_df):
        next_row = daily_df.iloc[cut_idx + 1]
        npc = cut_row['close']
        if npc > 0:
            next_day_pct = (next_row['close'] - npc) / npc
            next_day_open_pct = (next_row['open'] - npc) / npc
            next_day_is_zt = next_day_pct >= CONFIG['zt_threshold']

    return {
        'stock_code': stock_code, 'stock_name': stock_name, 'cut_date': cut_date,
        'seq_start_date': daily_df.iloc[seq_start]['date'],
        'seq_end_date': daily_df.iloc[seq_end]['date'],
        'end_pattern': end_pattern, 'board_height': board_height,
        'height_category': height_category, 'accel_count': accel_count,
        'max_accel_duration': max_accel_duration, 'max_accel_category': max_accel_category,
        'accel_density': accel_density, 'first_day_amplitude': first_day_amplitude,
        'first_day_state': first_day_state, 'pre_rally': pre_rally,
        'pre_rally_category': pre_rally_category, 'combined_height': combined_height,
        'combined_height_category': combined_height_category,
        'history_special': history_special, 'history_special_types': history_special_types,
        'has_history_special': has_history_special,
        'history_special_total': sum(history_special.values()),
        'special_position_seq': special_position_seq,
        'volume_label_per_day': volume_label_per_day,
        'cut_special': cut_special, 'board_strength': board_strength,
        'board_strength_l2': board_strength_l2, 'deviation': deviation,
        'deviation_category': deviation_category, 'amplitude': amplitude,
        'amplitude_category': amplitude_category, 'open_pct': open_pct,
        'open_pct_category': open_pct_category,
        'volume_ratio_vs_yesterday': volume_ratio_vs_yesterday,
        'volume_state': volume_state, 'volume_ratio_vs_3day': volume_ratio_vs_3day,
        'board_time': None, 'next_day_pct': next_day_pct,
        'next_day_is_zt': next_day_is_zt, 'next_day_open_pct': next_day_open_pct,
        'label_sequence': sequence_labels,
    }


def build_all_cases(all_daily_data, stock_info_df):
    cache_file = CONFIG.get('case_library_cache')
    if cache_file and os.path.exists(cache_file):
        try:
            print(f"\n从缓存加载案例库...")
            with open(cache_file, 'rb') as f:
                all_cases = pickle.load(f)
            print(f"案例库: {len(all_cases)} 个案例（缓存）")
            return all_cases
        except Exception:
            print(f"缓存失败，重新构建...")

    code_to_name = dict(zip(stock_info_df['code'], stock_info_df['name']))
    all_cases = []
    total = len(all_daily_data)
    processed = 0
    print(f"\n构建案例库，共 {total} 只...")
    for code, daily_df in all_daily_data.items():
        processed += 1
        if processed % 200 == 0 or processed == total:
            print(f"  {processed}/{total} ({processed/total*100:.1f}%) | {len(all_cases)} 案例")
        name = code_to_name.get(code, '未知')
        try:
            daily_df = identify_zt_days(daily_df)
            for s, e in find_consecutive_zt_sequences(daily_df):
                for ci in range(s, e + 1):
                    all_cases.append(build_case_from_sequence(code, name, daily_df, s, e, ci))
        except Exception:
            continue

    print(f"案例库完成: {len(all_cases)} 个")
    if cache_file:
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(all_cases, f)
            print(f"已缓存: {cache_file}")
        except Exception:
            pass
    return all_cases
def calculate_special_board_score(target_case, candidate_case):
    target_types = target_case['history_special_types']
    cand_types = candidate_case['history_special_types']
    target_has = target_case['has_history_special']
    cand_has = candidate_case['has_history_special']

    score = 0
    details = []

    # 种类匹配
    if not target_has and not cand_has:
        s = CONFIG['bonus_special_type_both_none']
        score += s
        details.append(f"双方无特殊板型+{s}")
    elif target_has and not cand_has:
        tc = len(target_types)
        p = tc * CONFIG['penalty_special_type_one_side_per']
        score -= p
        details.append(f"候选无特殊板型(标的有{tc}种)-{p}")
    elif not target_has and cand_has:
        tc = len(cand_types)
        p = tc * CONFIG['penalty_special_type_one_side_per']
        score -= p
        details.append(f"标的无但候选有{tc}种特殊板型-{p}")
    else:
        intersection = target_types & cand_types
        t_only = target_types - cand_types
        c_only = cand_types - target_types
        if target_types == cand_types:
            s = CONFIG['bonus_special_type_perfect']
            score += s
            details.append(f"特殊板型种类完全一致+{s}")
        elif len(intersection) > 0:
            mc = len(t_only) + len(c_only)
            p = mc * CONFIG['penalty_special_type_partial']
            score -= p
            details.append(f"特殊板型种类部分重合(差{mc}种)-{p}")
        else:
            p = CONFIG['penalty_special_type_none']
            score -= p
            details.append(f"特殊板型种类零交集-{p}")

    # 数量差异扣分（按每种分别算，差≤1不扣，差≥2每多1个扣分）
    if target_has or cand_has:
        count_penalty, count_detail = calculate_special_count_penalty(
            target_case['history_special'], candidate_case['history_special'])
        if count_penalty > 0:
            score -= count_penalty
            details.append(count_detail)

    # 位置匹配（含亲疏关系）
    if target_has and cand_has:
        t_seq = target_case['special_position_seq']
        c_seq = candidate_case['special_position_seq']
        t_vol = target_case.get('volume_label_per_day', [])
        c_vol = candidate_case.get('volume_label_per_day', [])

        for i in range(min(len(t_seq), len(c_seq))):
            ts, cs = t_seq[i], c_seq[i]
            t_is = ts in SPECIAL_TYPES
            c_is = cs in SPECIAL_TYPES

            if t_is and c_is:
                if ts == cs:
                    b = CONFIG['bonus_special_pos_match']
                    score += b
                    details.append(f"第{i+1}板{ts}位置匹配+{b}")
                elif is_same_special_group(ts, cs):
                    tv = t_vol[i] if i < len(t_vol) else 0
                    cv = c_vol[i] if i < len(c_vol) else 0
                    if tv == cv:
                        p = CONFIG['penalty_special_pos_same_group']
                        score -= p
                        details.append(f"第{i+1}板同组近似({ts}vs{cs},量能一致)-{p}")
                    else:
                        p = CONFIG['penalty_special_pos_diff_type']
                        score -= p
                        details.append(f"第{i+1}板同组量能不一致({ts}vs{cs})-{p}")
                else:
                    p = CONFIG['penalty_special_pos_diff_type']
                    score -= p
                    details.append(f"第{i+1}板类型不同({ts}vs{cs})-{p}")
            elif t_is or c_is:
                p = CONFIG['penalty_special_pos_one_side']
                score -= p
                sp = ts if t_is else cs
                details.append(f"第{i+1}板单方特殊({sp})-{p}")

    return score, details


def pre_filter(target_case, case_library):
    threshold = CONFIG['downgrade_threshold']
    current = [c for c in case_library
               if not (c['stock_code'] == target_case['stock_code']
                       and c['cut_date'] == target_case['cut_date'])]
    print(f"  排除自身：{len(current)}")

    current = [c for c in current if c['board_height'] >= 2]
    print(f"  过滤首板后：{len(current)}")

    if target_case['has_history_special']:
        tt = target_case['history_special_types']
        f1 = [c for c in current if len(c['history_special_types'] & tt) > 0]
        if len(f1) >= threshold:
            current = f1
            print(f"  特殊板型(历史·宽松)：{len(current)}")
        else:
            f2 = [c for c in current if c['has_history_special']]
            if len(f2) >= threshold:
                current = f2
                print(f"  特殊板型(历史·降级)：{len(current)}")

    if target_case['cut_special'] in SPECIAL_TYPES:
        tsp = target_case['cut_special']
        f = [c for c in current if c['cut_special'] == tsp]
        if len(f) >= threshold:
            current = f
            print(f"  特殊板型(切面日·{tsp})：{len(current)}")

    return current


def hard_filter(target_case, candidates):
    f = [c for c in candidates if c['end_pattern'] == target_case['end_pattern']]
    print(f"  硬过滤(末端={target_case['end_pattern']})：{len(f)}")
    return f


def conditional_filter(target_case, candidates):
    threshold = CONFIG['downgrade_threshold']
    cp = {'board_strength': 0}
    l1 = [c for c in candidates if c['board_strength'] == target_case['board_strength']]
    if len(l1) >= threshold:
        result = l1
    else:
        result = [c for c in candidates
                  if c['board_strength_l2'] == target_case['board_strength_l2']]
        cp['board_strength'] = CONFIG['penalty_board_strength']
    print(f"  条件过滤(封板强度)：{len(result)}")
    return result, cp


def calculate_similarity_distance(target_case, candidates):
    if not candidates:
        return []
    sm = {'一字': 4, '硬板': 3, '换手': 2, '烂板': 1}

    def scd(case):
        t, c = target_case['history_special'], case['history_special']
        return sum(abs(t[k] - c[k]) for k in t)

    def feat(case):
        return np.array([
            case['board_height'], case['max_accel_duration'], case['accel_count'],
            case['accel_density'], case['first_day_amplitude'], case['pre_rally'],
            case['combined_height'], sm.get(case['board_strength'], 2),
            case['deviation'], case['amplitude'], case['volume_ratio_vs_yesterday'],
            case['volume_ratio_vs_3day'], 2, scd(case), case.get('open_pct', 0),
        ], dtype=float)

    tf = feat(target_case)
    tf[-2] = 0.0
    cf = np.array([feat(c) for c in candidates])
    af = np.vstack([tf.reshape(1, -1), cf])
    fmin, fmax = af.min(0), af.max(0)
    fr = fmax - fmin
    fr[fr == 0] = 1.0
    norm = (af - fmin) / fr
    dists = np.sqrt(np.sum((norm[1:] - norm[0]) ** 2, axis=1))
    for i, c in enumerate(candidates):
        c['distance'] = dists[i]
    return candidates


def calculate_final_score(target_case, candidates, cond_penalties):
    max_p = CONFIG['max_penalty_threshold']
    scored = []

    for case in candidates:
        ip, ib, details = 0, 0, []

        # 连板高度：跨1档/跨2档分别扣分
        hp = calculate_height_penalty(target_case['height_category'], case['height_category'])
        if hp > 0:
            ip += hp
            details.append(f"连板高度不匹配({case['height_category']}vs{target_case['height_category']})-{hp}")

        if case['max_accel_category'] != target_case['max_accel_category']:
            ip += CONFIG['penalty_accel_duration']
            details.append(f"最大加速持续不匹配-{CONFIG['penalty_accel_duration']}")
        if case['first_day_state'] != target_case['first_day_state']:
            ip += CONFIG['penalty_first_day']
            details.append(f"首日状态不匹配-{CONFIG['penalty_first_day']}")
        if case['amplitude_category'] != target_case['amplitude_category']:
            ip += CONFIG['penalty_amplitude']
            details.append(f"振幅不匹配({case['amplitude_category']}vs{target_case['amplitude_category']})-{CONFIG['penalty_amplitude']}")
        if case['volume_state'] != target_case['volume_state']:
            ip += CONFIG['penalty_volume_state']
            details.append(f"量能状态不匹配({case['volume_state']}vs{target_case['volume_state']})-{CONFIG['penalty_volume_state']}")

        op = calculate_open_pct_penalty(target_case['open_pct_category'], case['open_pct_category'])
        if op > 0:
            ip += op
            details.append(f"开盘涨幅不匹配({case['open_pct_category']}vs{target_case['open_pct_category']})-{op}")

        sp_score, sp_details = calculate_special_board_score(target_case, case)
        if sp_score >= 0:
            ib += sp_score
        else:
            ip += abs(sp_score)
        details.extend(sp_details)

        if target_case['cut_special'] in SPECIAL_TYPES:
            if case['cut_special'] == target_case['cut_special']:
                b = CONFIG['bonus_cut_special_match']
                ib += b
                details.append(f"切面日特殊板型匹配+{b}")
            else:
                p = CONFIG['penalty_cut_special_mismatch']
                ip += p
                details.append(f"切面日特殊板型不匹配-{p}")
        elif case['cut_special'] in SPECIAL_TYPES:
            p = CONFIG['penalty_cut_special_mismatch']
            ip += p
            details.append(f"切面日特殊板型多余-{p}")

        if cond_penalties['board_strength'] > 0:
            if case['board_strength'] != target_case['board_strength']:
                ip += cond_penalties['board_strength']
                details.append(f"封板强度L2不匹配-{cond_penalties['board_strength']}")

        ap = calculate_accel_count_penalty(target_case['accel_count'], case['accel_count'])
        if ap > 0:
            ip += ap
            details.append(f"加速次数差异-{ap}")

        prp = calculate_pre_rally_penalty(target_case['pre_rally_category'], case['pre_rally_category'])
        pr_mm = False
        if prp > 0:
            ip += prp
            details.append(f"启动位置跨档-{prp}")
            pr_mm = True
        else:
            ib += CONFIG['bonus_pre_rally']
            details.append(f"启动位置匹配+{CONFIG['bonus_pre_rally']}")

        h_mm = case['height_category'] != target_case['height_category']
        if h_mm or pr_mm:
            if case['combined_height_category'] == target_case['combined_height_category']:
                b = CONFIG['bonus_combined_height']
                ib += b
                details.append(f"综合高度同档({target_case['combined_height_category']})+{b}")

        if (ip - ib) >= max_p:
            continue

        case['individual_penalty'] = ip
        case['individual_bonus'] = ib
        case['penalty_details'] = details
        scored.append(case)

    print(f"  扣分过滤(≥{max_p})：{len(scored)}")
    return scored


def apply_distance_and_final_score(target_case, scored_candidates):
    if not scored_candidates:
        return []
    dtn = CONFIG.get('distance_top_n', 30)
    for c in scored_candidates:
        c['_ss'] = 100 - c['individual_penalty'] + c['individual_bonus']
    scored_candidates.sort(key=lambda x: x['_ss'], reverse=True)

    top = scored_candidates[:dtn]
    rest = scored_candidates[dtn:]

    if top:
        top = calculate_similarity_distance(target_case, top)

    max_distance_penalty = 0
    for c in top:
        dp = c['distance'] * CONFIG['distance_multiplier']
        if dp > max_distance_penalty:
            max_distance_penalty = dp
        if dp > 0.01:
            c['penalty_details'].append(f"距离扣分-{dp:.1f}")
        ss = c['_ss']
        capped = min(100, ss)
        c['distance_penalty'] = round(dp, 2)
        c['structure_score'] = round(ss, 2)
        c['capped_structure_score'] = round(capped, 2)
        c['final_score'] = round(capped - dp, 2)
        c['penalty_detail'] = '；'.join(c['penalty_details'])

    for c in rest:
        ss = c['_ss']
        capped = min(100, ss)
        c['distance'] = 0
        c['distance_penalty'] = round(max_distance_penalty, 2)
        c['structure_score'] = round(ss, 2)
        c['capped_structure_score'] = round(capped, 2)
        c['final_score'] = round(capped - max_distance_penalty, 2)
        if max_distance_penalty > 0.01:
            c['penalty_details'].append(f"距离扣分(未入Top30,取最大值)-{max_distance_penalty:.1f}")
        c['penalty_detail'] = '；'.join(c['penalty_details'])

    result = top + rest
    result.sort(key=lambda x: x['final_score'], reverse=True)
    for c in result:
        c.pop('_ss', None)
    return result
def format_output(target_case, ranked_candidates, top_n=None):
    if top_n is None:
        top_n = CONFIG['top_n']
    rows = []
    for rank, case in enumerate(ranked_candidates[:top_n], 1):
        hsp = [f"{k}×{v}" for k, v in case['history_special'].items() if v > 0]
        score = case['final_score']
        grade = '✅高' if score >= 80 else '⚠️中' if score >= 60 else '❌低'
        rows.append({
            '排名': rank, '股票代码': case['stock_code'], '股票名称': case['stock_name'],
            '切面日期': case['cut_date'].strftime('%Y-%m-%d') if pd.notna(case['cut_date']) else '',
            '最终得分': case['final_score'],
            '结构分(封顶前)': case['structure_score'],
            '结构分(封顶后)': case['capped_structure_score'],
            '距离扣分': case['distance_penalty'], '相似度': grade,
            '扣分明细': case['penalty_detail'],
            '连板高度': case['board_height'], '高度档位': case['height_category'],
            '综合高度': f"{case['combined_height']:.1%}",
            '综合高度档位': case['combined_height_category'],
            '末端形态': case['end_pattern'], '加速次数': case['accel_count'],
            '最大加速持续': case['max_accel_duration'],
            '加速持续档位': case['max_accel_category'],
            '加速密度': f"{case['accel_density']:.1%}",
            '首日振幅': f"{case['first_day_amplitude']:.2%}",
            '首日状态': case['first_day_state'],
            '连板前涨幅': f"{case['pre_rally']:.2%}",
            '启动位置': case['pre_rally_category'],
            '历史特殊板型': ', '.join(hsp) if hsp else '无',
            '特殊板型位置': '→'.join(case['special_position_seq']),
            '切面日特殊板型': case['cut_special'],
            '封板强度': case['board_strength'],
            '偏离度': f"{case['deviation']:.2%}", '偏离档位': case['deviation_category'],
            '振幅': f"{case['amplitude']:.2%}", '振幅档位': case['amplitude_category'],
            '开盘涨幅': f"{case['open_pct']:.2%}", '开盘涨幅档位': case['open_pct_category'],
            '日量比(vs昨日)': f"{case['volume_ratio_vs_yesterday']:.2f}",
            '量能状态': case['volume_state'],
            '次日涨跌幅': f"{case['next_day_pct']:.2%}" if case['next_day_pct'] is not None else '无数据',
            '次日是否晋级': '是' if case['next_day_is_zt'] else '否' if case['next_day_is_zt'] is not None else '无数据',
            '次日开盘涨幅': f"{case['next_day_open_pct']:.2%}" if case['next_day_open_pct'] is not None else '无数据',
            '0/1序列': '→'.join(map(str, case['label_sequence'])),
        })
    return pd.DataFrame(rows)


def print_target_info(tc):
    hsp = [f"{k}×{v}" for k, v in tc['history_special'].items() if v > 0]
    print("\n" + "=" * 70)
    print("标的股信息")
    print("=" * 70)
    print(f"  代码：{tc['stock_code']}  名称：{tc['stock_name']}")
    print(f"  切面日：{tc['cut_date'].strftime('%Y-%m-%d')}")
    print(f"  连板高度：{tc['board_height']}板({tc['height_category']})")
    print(f"  综合高度：{tc['combined_height']:.1%}({tc['combined_height_category']})")
    print(f"  末端形态：{tc['end_pattern']}")
    print(f"  加速次数：{tc['accel_count']}  最大加速：{tc['max_accel_duration']}天({tc['max_accel_category']})")
    print(f"  首日振幅：{tc['first_day_amplitude']:.2%}({tc['first_day_state']})")
    print(f"  启动位置：{tc['pre_rally']:.2%}({tc['pre_rally_category']})")
    print(f"  历史特殊板型：{', '.join(hsp) if hsp else '无'}")
    print(f"  特殊板型位置：{'→'.join(tc['special_position_seq'])}")
    print(f"  切面日特殊：{tc['cut_special']}  封板强度：{tc['board_strength']}")
    print(f"  振幅：{tc['amplitude']:.2%}({tc['amplitude_category']})")
    print(f"  开盘涨幅：{tc['open_pct']:.2%}({tc['open_pct_category']})")
    print(f"  量能：{tc['volume_ratio_vs_yesterday']:.2f}({tc['volume_state']})")
    print("=" * 70)


def print_summary_stats(ranked):
    valid = [c for c in ranked if c['next_day_pct'] is not None]
    if not valid:
        return
    pcts = [c['next_day_pct'] for c in valid]
    zt = sum(1 for c in valid if c['next_day_is_zt'])
    print(f"\n统计({len(valid)}个): 平均{np.mean(pcts):.2%} 中位{np.median(pcts):.2%} "
          f"上涨{sum(1 for p in pcts if p>0)/len(pcts):.1%} 晋级{zt/len(valid):.1%}")


def build_target_case(stock_code, cut_date_str, all_daily_data, stock_info_df):
    code_to_name = dict(zip(stock_info_df['code'], stock_info_df['name']))
    name = code_to_name.get(stock_code, '未知')
    if stock_code not in all_daily_data:
        raise ValueError(f"找不到{stock_code}的数据")
    daily_df = identify_zt_days(all_daily_data[stock_code].copy())
    cut_date = pd.to_datetime(cut_date_str)
    mask = daily_df['date'] == cut_date
    if not mask.any():
        raise ValueError(f"{stock_code}在{cut_date_str}无数据")
    cut_idx = daily_df[mask].index[0]
    if not daily_df.iloc[cut_idx]['is_zt']:
        raise ValueError(f"{stock_code}在{cut_date_str}非涨停")
    seq_start = cut_idx
    while seq_start > 0 and daily_df.iloc[seq_start - 1]['is_zt']:
        seq_start -= 1
    seq_end = cut_idx
    while seq_end < len(daily_df) - 1 and daily_df.iloc[seq_end + 1]['is_zt']:
        seq_end += 1
    if cut_idx - seq_start + 1 < 2:
        raise ValueError(f"{stock_code}在{cut_date_str}仅首板")
    return build_case_from_sequence(stock_code, name, daily_df, seq_start, seq_end, cut_idx)


def run_matching(stock_code, cut_date_str, search_start, search_end,
                 top_n=None, output_excel=True):
    if top_n is None:
        top_n = CONFIG['top_n']
    print("=" * 70)
    print(f"K线相似 v2.3 | {stock_code} | {cut_date_str}")
    print("=" * 70)

    stock_info = get_main_board_stock_list()
    all_daily = batch_download_daily_data(stock_info, search_start, search_end)
    if not all_daily:
        return pd.DataFrame()

    target = build_target_case(stock_code, cut_date_str, all_daily, stock_info)
    print_target_info(target)
    case_library = build_all_cases(all_daily, stock_info)

    print(f"\n匹配中... 案例库：{len(case_library)}")
    cands = pre_filter(target, case_library)
    if not cands:
        print("\n⚠️ 预过滤后无案例")
        return pd.DataFrame()
    cands = hard_filter(target, cands)
    if not cands:
        print("\n⚠️ 硬过滤后无案例")
        return pd.DataFrame()
    cands, cp = conditional_filter(target, cands)
    if not cands:
        print("\n⚠️ 条件过滤后无案例")
        return pd.DataFrame()
    scored = calculate_final_score(target, cands, cp)
    if not scored:
        print("\n⚠️ 扣分过滤后无案例")
        return pd.DataFrame()
    ranked = apply_distance_and_final_score(target, scored)

    result_df = format_output(target, ranked, top_n)
    print_summary_stats(ranked[:top_n])

    if output_excel:
        fn = f"匹配结果_{stock_code}_{cut_date_str}.xlsx"
        result_df.to_excel(fn, index=False, engine='openpyxl')
        print(f"\n已保存：{fn}")

    print(f"\nTop 10：")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(result_df.head(10).to_string(index=False))
    return result_df


if __name__ == '__main__':
    result = run_matching(
        stock_code='603221', cut_date_str='2025-04-09',
        search_start='20240101', search_end='20260331',
        top_n=50, output_excel=True
    )
