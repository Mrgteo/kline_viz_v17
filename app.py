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

PROJECT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_cache')

CONFIG = {
    'cache_dir': PROJECT_CACHE_DIR,
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
    'hard_threshold_break': 60,        # 断板场景淘汰阈值（原75改为60）
    'hard_threshold_no_break': 30,     # 纯连板场景保持30

    # ===== A组：涨停段评分 =====
    'penalty_height_1': 15,
    'penalty_height_2': 23,
    'penalty_accel_duration': 10,
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

    # ===== 封顶规则（v3）=====
    # 加分上限：所有组统一+20
    'cap_bonus_all': 20,

    # A组扣分上限
    'cap_penalty_a_compact': 60,
    'cap_penalty_a_standard': 50,
    'cap_penalty_a_wide': 40,

    # B组扣分上限（统一为50）
    'cap_penalty_b_compact': 50,
    'cap_penalty_b_standard': 50,
    'cap_penalty_b_wide': 50,

    # B组原始扣分淘汰阈值（加权后、封顶前）
    'b_raw_penalty_eliminate': 110,

    # M-cut扣分上限（×3.0权重后放宽至60）
    'cap_penalty_mcut': 60,

    # M-start扣分上限（紧凑最重，宽泛不扣分）
    'cap_penalty_mstart_compact': 25,
    'cap_penalty_mstart_standard': 15,
    'cap_penalty_mstart_wide': 0,

    # E组扣分上限（统一）
    'cap_penalty_e': 30,

    # ===== B组：断板期评分 =====
    'penalty_rise_cross_1': 20,
    'penalty_rise_cross_2': 30,
    'penalty_break_count': 20,
    'penalty_d2_emotion_mismatch': 8,
    'penalty_d3_mismatch': 10,
    'bonus_d3_exact': 5,
    'bonus_d3_both_none': 1,
    # 'bonus_d1_exact': 6,  # 已废弃，改用b_d1_exact_bonus
    # 'bonus_d1_same_emotion': 3,  # 已废弃
    # 'penalty_d1_mismatch': 15,  # 已废弃
    # 'bonus_d2_exact': 5,  # 已废弃，改用b_d2_exact_bonus
    # 'bonus_d2_same_emotion': 2,  # 已废弃
    'bonus_touch_zt_match': 5,
    'bonus_touch_dt_match': 5,

    # B组D1/D2 v2新规则
    'b_d1_exact_bonus': 10,          # 精确加10
    'b_d1_approx_bonus': 0,           # 近似不加分
    'b_d1_emotion_penalty': 15,       # 情绪相同扣15
    'b_d1_diff_emotion_penalty': 30,  # 情绪不同扣30

    # D2按D1的0.5倍
    'b_d2_exact_bonus': 5,
    'b_d2_approx_bonus': 0,
    'b_d2_emotion_penalty': 8,        # 15*0.5≈8
    'b_d2_diff_emotion_penalty': 15,

    # 硬匹配D1扣分
    'hp_d1_approx_penalty': 5,        # 硬匹配近似扣5

    # ===== 硬匹配规则 v3 =====
    # 距D1/断板天数：跨1档按天数差×10扣分，上限30
    'hp_days_per_diff': 10,
    'hp_days_cap': 30,

    # 密度矩阵扣分（跨1档）
    'hp_density_match_penalty': 20,

    # 跌停强度独立扣分
    'hp_dt_intensity_1gap': 15,
    'hp_dt_intensity_2gap': 25,

    # E组触及涨跌停（双方触及+5、单方触及-5）
    'hp_e_touch_one_side_penalty': 5,

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

    # ===== M组：微型结构（v2新规则）=====
    # 基础分（M-cut和M-start通用）
    'micro_base_day0': 10,   # 第3天（切面日/首板）
    'micro_base_day1': 6,    # 前1天
    'micro_base_day2': 4,    # 前2天

    # 加分扣分系数（基础分的倍数）
    'micro_exact_mult': 1.0,    # 精确：+1.0×基础分
    'micro_approx_mult': 0.5,   # 近似：+0.5×基础分
    'micro_emotion_mult': 1.0,  # 情绪：-1.0×基础分
    'micro_mismatch_mult': 2.0, # 不匹配：-2.0×基础分

    # 整组权重
    'mcut_group_weight': 3.0,           # M-cut所有研究范围都×3.0
    'mstart_group_weight_compact': 1.5,  # M-start紧凑
    'mstart_group_weight_standard': 1.0, # M-start标准
    'mstart_group_weight_wide': 0.5,     # M-start宽泛

    # ===== E组：切面日基础 =====
    'penalty_cut_volume': 10,

    # ===== F组+全局 =====
    'max_penalty_threshold': 999,
    'distance_multiplier': 10,
    'distance_top_n': 30,

    # ===== 写死参数提CONFIG =====
    # A1b 紧凑档主波高度精细匹配
    'bonus_a1_compact_match': 5,         # 紧凑档主波高度一致加分
    'penalty_a1_compact_mismatch': 10,   # 紧凑档主波高度不一致扣分

    # A1b 次波高度
    'penalty_subwave_cross_1': 10,       # 次波高度跨1档扣分

    # A1c 紧凑D0近似扣分
    'penalty_a1_d0_approx': 10,          # 紧凑档D0近似匹配扣分

    # A2 板型集合匹配
    'bonus_a2_perfect': 5,                       # 板型完全重合加分
    'penalty_a2_partial_compact': 10,            # 板型部分重合扣分（紧凑档）
    'penalty_a2_partial_standard': 5,            # 板型部分重合扣分（标准档）
    'penalty_a2_none': 10,                       # 板型不重合扣分（标准档）

    # A4 标准首板形态
    'penalty_a4_first_no_approx': 10,    # 标准档首板形态不近似扣分（×2.0=20）

    # B10b 紧凑档断板天数精细匹配
    'bonus_b10b_match': 5,               # 紧凑档断板天数一致加分
    'penalty_b10b_mismatch': 10,         # 紧凑档断板天数不一致扣分

    # B10c 紧凑档距D1精细匹配
    'bonus_b10c_match': 5,               # 紧凑档距D1一致加分
    'penalty_b10c_mismatch': 10,         # 紧凑档距D1不一致扣分

    # A16 回撤比同档差异
    'penalty_height_retrace_1': 15,         # 回撤比跨1档扣分
    'bonus_height_retrace_same': 5,         # 回撤比同档极相似(相对差≤20%)
    'penalty_height_retrace_same_cap': 11,  # 回撤比同档大差距上限

    # A17 最大涨幅同档差异
    'penalty_max_rise_1': 15,               # 最大涨幅跨1档扣分
    'bonus_max_rise_same': 5,               # 最大涨幅同档极相似
    'penalty_max_rise_same_cap': 11,        # 最大涨幅同档大差距上限

    # E4 开盘涨幅同档差异
    'bonus_open_pct_same': 5,               # 开盘涨幅同档极相似
    'penalty_open_pct_same_cap': 4,         # 开盘涨幅同档大差距上限

    # B 波次
    'penalty_wave_cross_1': 15,          # 波次跨1档扣分（受bp_w加权）

    'case_library_cache': os.path.join(PROJECT_CACHE_DIR, 'case_library_break_v22.pkl'),
    'worker_count': max(1, cpu_count() - 1),
}

CONFIG['cache_dir'] = PROJECT_CACHE_DIR
CONFIG['case_library_cache'] = os.path.join(
    PROJECT_CACHE_DIR, os.path.basename(CONFIG['case_library_cache'])
)
os.makedirs(PROJECT_CACHE_DIR, exist_ok=True)

# ============================================================
# 形态常量
# ============================================================

# 严重断板形态判断已改为用score_v2 <= -0.5（中阴线及以下）
# 旧常量SEVERE_BREAK_FORMS已废弃


# ============================================================
# 形态识别函数
# ============================================================

def classify_volume_v2(today_vol, last3_avg, yesterday_vol):
    """
    量能分类（用于v2形态识别）
    返回: '缩量' / '放量' / '中性' / '未知'
    """
    if today_vol is None or yesterday_vol is None or last3_avg is None:
        return '未知'
    if last3_avg <= 0:
        return '未知'

    # 缩量
    if today_vol < last3_avg:
        return '缩量'
    # 放量
    if today_vol > last3_avg * 2.5:
        return '放量'

    # 中间状态：看今天vs昨天
    if yesterday_vol <= 0:
        return '未知'
    if today_vol < yesterday_vol:
        return '缩量'
    elif today_vol > yesterday_vol:
        return '放量'
    return '中性'


# v3形态体系：24种细分类（二维矩阵穷举，无兜底）
SUBDIVISION_V2_INFO = {
    # 涨停类（6种，不变）
    '一字涨停': {'score': 2.5, 'group': '加速涨停类', 'emotion_class': '强势'},
    '缩量加速涨停': {'score': 2.4, 'group': '加速涨停类', 'emotion_class': '强势'},
    '非缩量加速涨停': {'score': 2.3, 'group': '加速涨停类', 'emotion_class': '强势'},
    '反转涨停': {'score': 2.2, 'group': '普通涨停类', 'emotion_class': '强势'},
    '普通涨停': {'score': 2.1, 'group': '普通涨停类', 'emotion_class': '强势'},
    '烂板涨停': {'score': 2.1, 'group': '普通涨停类', 'emotion_class': '强势'},
    # 阳线类（3种，二维矩阵）
    '大阳线': {'score': 0.8, 'group': '阳线类', 'emotion_class': '强势'},
    '中阳线': {'score': 0.5, 'group': '阳线类', 'emotion_class': '强势'},
    '小阳线': {'score': 0.2, 'group': '阳线类', 'emotion_class': '强势'},
    # 宽幅震荡（5种，长影线类）
    '强势长上影': {'score': 0.2, 'group': '宽幅震荡', 'emotion_class': '震荡', 'emotion_also': '强势'},
    '震荡弱势长上影': {'score': 0.1, 'group': '宽幅震荡', 'emotion_class': '震荡'},
    '长十字星': {'score': 0, 'group': '宽幅震荡', 'emotion_class': '震荡'},
    '强势长下影': {'score': -0.1, 'group': '宽幅震荡', 'emotion_class': '震荡'},
    '震荡弱势长下影': {'score': -0.2, 'group': '宽幅震荡', 'emotion_class': '震荡', 'emotion_also': '弱势'},
    # 窄幅震荡（2种）
    '窄幅小阳线': {'score': 0.05, 'group': '窄幅震荡', 'emotion_class': '震荡'},
    '窄幅小阴线': {'score': -0.05, 'group': '窄幅震荡', 'emotion_class': '震荡'},
    # 阴线类（3种，二维矩阵）
    '小阴线': {'score': -0.2, 'group': '阴线类', 'emotion_class': '弱势'},
    '中阴线': {'score': -0.5, 'group': '阴线类', 'emotion_class': '弱势'},
    '大阴线': {'score': -0.8, 'group': '阴线类', 'emotion_class': '弱势'},
    # 跌停类（5种，不变）
    '跌停': {'score': -2.1, 'group': '普通跌停类', 'emotion_class': '弱势'},
    '反转跌停': {'score': -2.1, 'group': '普通跌停类', 'emotion_class': '弱势'},
    '非缩量加速跌停': {'score': -2.2, 'group': '加速跌停类', 'emotion_class': '弱势'},
    '加速跌停': {'score': -2.3, 'group': '加速跌停类', 'emotion_class': '弱势'},
    '一字跌停': {'score': -2.4, 'group': '加速跌停类', 'emotion_class': '弱势'},
}


def classify_kline_v2(form, pct, open_pct, body_pct, amplitude,
                     upper_shadow, lower_shadow, vol_class):
    """
    K线形态分类 v3.0
    判断顺序：涨跌停 → 长十字星 → 长上影 → 长下影 → 窄幅震荡 → 阳/阴线二维矩阵

    参数:
        form: 粗形态（'一字板'、'T字板'等）
        pct: 收盘涨跌幅（前收为基准）
        open_pct: 开盘涨幅
        body_pct: 实体涨幅 = (close-open)/pre_close
        amplitude: 振幅 = (high-low)/pre_close
        upper_shadow: 上影线 = (high-max(open,close))/pre_close
        lower_shadow: 下影线 = (min(open,close)-low)/pre_close
        vol_class: 量能分类

    返回: (subdivision_name, score, approx_group)
    """

    # ===== 第1步：涨停类 =====
    if form == '一字板':
        return '一字涨停', 2.5, '加速涨停类'
    if form in ('T字板', '秒板'):
        if vol_class == '缩量':
            return '缩量加速涨停', 2.4, '加速涨停类'
        else:
            return '非缩量加速涨停', 2.3, '加速涨停类'
    if form in ('地天板', '大长腿涨停'):
        return '反转涨停', 2.2, '普通涨停类'
    if form == '普通涨停':
        if vol_class == '放量':
            return '烂板涨停', 2.1, '普通涨停类'
        else:
            return '普通涨停', 2.1, '普通涨停类'

    # ===== 第1步：跌停类 =====
    if form == '一字跌停':
        return '一字跌停', -2.4, '加速跌停类'
    if form in ('倒T字跌停', '秒跌停'):
        if vol_class == '缩量':
            return '加速跌停', -2.3, '加速跌停类'
        else:
            return '非缩量加速跌停', -2.2, '加速跌停类'
    if form in ('天地板', '大长腿跌停'):
        return '反转跌停', -2.1, '普通跌停类'
    if form == '普通跌停':
        return '跌停', -2.1, '普通跌停类'

    # ===== 以下为非涨跌停日 =====
    shadow_threshold = 0.05  # 长影线阈值5%

    # ===== 第2步：长十字星（上影>5% 且 下影>5%）=====
    if upper_shadow > shadow_threshold and lower_shadow > shadow_threshold:
        return '长十字星', 0, '宽幅震荡'

    # ===== 第3步：长上影类（上影>5%）=====
    if upper_shadow > shadow_threshold:
        if body_pct > 0:
            return '强势长上影', 0.2, '宽幅震荡'
        else:  # body_pct <= 0
            return '震荡弱势长上影', 0.1, '宽幅震荡'

    # ===== 第4步：长下影类（下影>5%）=====
    if lower_shadow > shadow_threshold:
        if body_pct > 0:
            return '强势长下影', -0.1, '宽幅震荡'
        else:  # body_pct <= 0
            return '震荡弱势长下影', -0.2, '宽幅震荡'

    # ===== 第5步：窄幅震荡（涨跌幅∈(-3%,3%) 且 振幅<3%）=====
    if -0.03 < pct < 0.03 and amplitude < 0.03:
        if pct > 0:
            return '窄幅小阳线', 0.05, '窄幅震荡'
        elif pct < 0:
            return '窄幅小阴线', -0.05, '窄幅震荡'
        else:  # pct == 0
            if body_pct >= 0:
                return '窄幅小阳线', 0.05, '窄幅震荡'
            else:
                return '窄幅小阴线', -0.05, '窄幅震荡'

    # ===== 第6步：阳/阴线二维矩阵（收盘涨幅 × 实体涨幅）=====
    # 收盘涨幅分档：>7%, 3-7%, 0-3%, -3-0%, -7--3%, <-7%
    # 实体涨幅分档：>7%, 3-7%, 0-3%, -3-0%, -7--3%, <-7%

    # 确定收盘涨幅档位
    if pct > 0.07:
        pct_level = 5      # >7%
    elif pct > 0.03:
        pct_level = 4      # 3-7%
    elif pct >= 0:
        pct_level = 3      # 0-3%
    elif pct > -0.03:
        pct_level = 2      # -3-0%
    elif pct > -0.07:
        pct_level = 1      # -7--3%
    else:
        pct_level = 0      # <-7%

    # 确定实体涨幅档位
    if body_pct > 0.07:
        body_level = 5     # >7%
    elif body_pct > 0.03:
        body_level = 4     # 3-7%
    elif body_pct >= 0:
        body_level = 3     # 0-3%
    elif body_pct > -0.03:
        body_level = 2     # -3-0%
    elif body_pct > -0.07:
        body_level = 1     # -7--3%
    else:
        body_level = 0     # <-7%

    # 二维矩阵查表
    # 格式：MATRIX[pct_level][body_level] = (细分类, 分值, 近似组)
    # pct_level: 0=<-7%, 1=-7--3%, 2=-3-0%, 3=0-3%, 4=3-7%, 5=>7%
    # body_level: 0=<-7%, 1=-7--3%, 2=-3-0%, 3=0-3%, 4=3-7%, 5=>7%

    MATRIX = {
        # pct >7%
        5: {
            5: ('大阳线', 0.8, '阳线类'),
            4: ('大阳线', 0.8, '阳线类'),
            3: ('大阳线', 0.8, '阳线类'),
            2: ('中阳线', 0.5, '阳线类'),
            1: ('中阳线', 0.5, '阳线类'),  # 物理上极难出现，防御性归类
            0: ('中阳线', 0.5, '阳线类'),  # 物理上极难出现，防御性归类
        },
        # pct 3-7%
        4: {
            5: ('大阳线', 0.8, '阳线类'),
            4: ('中阳线', 0.5, '阳线类'),
            3: ('中阳线', 0.5, '阳线类'),
            2: ('小阳线', 0.2, '阳线类'),
            1: ('小阴线', -0.2, '阴线类'),
            0: ('小阴线', -0.2, '阴线类'),  # 物理上极难出现，防御性归类
        },
        # pct 0-3%
        3: {
            5: ('大阳线', 0.8, '阳线类'),
            4: ('中阳线', 0.5, '阳线类'),
            3: ('小阳线', 0.2, '阳线类'),
            2: ('窄幅小阳线', 0.05, '窄幅震荡'),  # 小阴小阳区域，默认归窄幅小阳
            1: ('小阴线', -0.2, '阴线类'),
            0: ('中阴线', -0.5, '阴线类'),
        },
        # pct -3-0%
        2: {
            5: ('中阳线', 0.5, '阳线类'),
            4: ('小阳线', 0.2, '阳线类'),
            3: ('窄幅小阴线', -0.05, '窄幅震荡'),  # 小阴小阳区域，默认归窄幅小阴
            2: ('小阴线', -0.2, '阴线类'),
            1: ('中阴线', -0.5, '阴线类'),
            0: ('大阴线', -0.8, '阴线类'),
        },
        # pct -7--3%
        1: {
            5: ('小阳线', 0.2, '阳线类'),  # 物理上极难出现，防御性归类
            4: ('小阳线', 0.2, '阳线类'),
            3: ('小阴线', -0.2, '阴线类'),
            2: ('中阴线', -0.5, '阴线类'),
            1: ('中阴线', -0.5, '阴线类'),
            0: ('大阴线', -0.8, '阴线类'),
        },
        # pct <-7%
        0: {
            5: ('中阴线', -0.5, '阴线类'),  # 物理上极难出现，防御性归类
            4: ('中阴线', -0.5, '阴线类'),  # 物理上极难出现，防御性归类
            3: ('中阴线', -0.5, '阴线类'),
            2: ('大阴线', -0.8, '阴线类'),
            1: ('大阴线', -0.8, '阴线类'),
            0: ('大阴线', -0.8, '阴线类'),
        },
    }

    result = MATRIX.get(pct_level, {}).get(body_level)
    if result:
        return result

    # 理论上不会到这里（矩阵已穷举），防御性兜底
    if pct >= 0:
        return '小阳线', 0.2, '阳线类'
    else:
        return '小阴线', -0.2, '阴线类'


def match_kline_v2(t_sub, c_sub, t_pct=None, c_pct=None):
    """
    1对1形态匹配（v2）
    返回: '精确' / '近似' / '情绪' / '不匹配'

    可选参数 t_pct/c_pct：用于判断假阴线/假阳线
    支持 emotion_also 双重情绪归属
    支持 CROSS_GROUP_APPROX 跨组近似映射
    """
    if t_sub == c_sub:
        # 同名情况下，检查阴线/阳线类的真假
        if t_pct is not None and c_pct is not None:
            group = SUBDIVISION_V2_INFO.get(t_sub, {}).get('group', '')
            if group == '阴线类':
                t_fake = t_pct > 0
                c_fake = c_pct > 0
                if t_fake != c_fake:
                    return '近似'
            elif group == '阳线类':
                t_fake = t_pct < 0
                c_fake = c_pct < 0
                if t_fake != c_fake:
                    return '近似'
        return '精确'

    # 跨组近似映射（特定形态可跨近似组匹配为"近似"）
    CROSS_GROUP_APPROX = {
        ('强势长上影', '中阳线'),
        ('中阳线', '强势长上影'),
        ('震荡弱势长下影', '中阴线'),
        ('中阴线', '震荡弱势长下影'),
    }
    if (t_sub, c_sub) in CROSS_GROUP_APPROX:
        return '近似'

    t_info = SUBDIVISION_V2_INFO.get(t_sub)
    c_info = SUBDIVISION_V2_INFO.get(c_sub)

    if t_info is None or c_info is None:
        return '不匹配'

    t_group = t_info['group']
    c_group = c_info['group']
    t_score = t_info['score']
    c_score = c_info['score']

    # 同近似组（用round避免浮点精度问题）
    if t_group == c_group:
        if round(abs(t_score - c_score), 4) <= 0.1:
            return '近似'
        else:
            return '情绪'

    # 不同近似组，看情绪类（支持双重情绪归属）
    t_emotions = {t_info['emotion_class']}
    c_emotions = {c_info['emotion_class']}
    if t_info.get('emotion_also'):
        t_emotions.add(t_info['emotion_also'])
    if c_info.get('emotion_also'):
        c_emotions.add(c_info['emotion_also'])

    if t_emotions & c_emotions:
        return '情绪'

    return '不匹配'


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
    """并行批量下载日K数据（v2优化版）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    _migrate_old_cache()

    # 智能截断end_date：如果超过今天，自动截断到今天
    today = pd.Timestamp.now().normalize()
    req_end_dt = pd.to_datetime(end_date, format='%Y%m%d')
    if req_end_dt > today:
        original_end = end_date
        end_date = today.strftime('%Y%m%d')
        print(f"  ⚠️ end_date从{original_end}截断到今天{end_date}（避免无效下载）")

    all_data = {}
    total = len(stock_list)
    success = failed = from_cache = downloaded = 0
    max_workers = 15  # 并发数（akshare限流容忍度）

    print(f"开始加载日K数据，共 {total} 只股票（{max_workers}线程并行）...")
    st = time.time()

    codes = stock_list['code'].tolist()

    # 线程安全的状态
    lock = threading.Lock()
    completed = [0]

    def process_one(code):
        """处理单只股票（线程内执行）"""
        new_cache = os.path.join(CONFIG['cache_dir'], f'daily_{code}.pkl')

        # 判断是否需要网络
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
        return code, df, needs_net

    # 线程池并行下载
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, code): code for code in codes}

        for future in as_completed(futures):
            try:
                code, df, needs_net = future.result()
                with lock:
                    if df is not None and len(df) > 0:
                        all_data[code] = df
                        success += 1
                        if not needs_net:
                            from_cache += 1
                        else:
                            downloaded += 1
                    else:
                        failed += 1

                    completed[0] += 1
                    if completed[0] % 200 == 0 or completed[0] == total:
                        elapsed = time.time() - st
                        speed = completed[0] / elapsed if elapsed > 0 else 0
                        print(f"  {completed[0]}/{total} ({completed[0]/total*100:.1f}%) | "
                              f"成功{success}(缓存{from_cache}+下载{downloaded}) | "
                              f"失败{failed} | {elapsed:.1f}秒 | {speed:.1f}只/秒")
            except Exception as e:
                with lock:
                    failed += 1
                    completed[0] += 1

    print(f"\n加载完成，成功{success}（缓存{from_cache}+下载{downloaded}）/ 失败{failed} | 总耗时{time.time()-st:.1f}秒")
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
        # 涨停日本身就是"触及涨停"
        if is_zt[i]:
            touched_zt[i] = True
        elif not np.isnan(zt_prices[i]) and zt_prices[i] > 0:
            if highs[i] >= zt_prices[i] - 0.01:
                touched_zt[i] = True
        # 跌停日本身就是"触及跌停"
        if is_dt[i]:
            touched_dt[i] = True
        elif not np.isnan(dt_prices[i]) and dt_prices[i] > 0:
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

    subdivisions_v2 = []
    scores_v2 = []
    groups_v2 = []

    for i in range(n):
        # v2量能分类
        if i >= 2:
            avg_3 = volumes[i-2:i+1].mean()
        elif i >= 1:
            avg_3 = volumes[:i+1].mean()
        else:
            avg_3 = volumes[i] if volumes[i] > 0 else None

        vol_class = classify_volume_v2(
            volumes[i] if not np.isnan(volumes[i]) else None,
            avg_3,
            volumes[i-1] if i > 0 else None
        )

        # v2形态分类
        sub_v2, score_v2, group_v2 = classify_kline_v2(
            forms[i], pcts[i], open_pcts[i], body_pcts[i],
            amplitudes[i], upper_shadows[i], lower_shadows[i],
            vol_class
        )
        subdivisions_v2.append(sub_v2)
        scores_v2.append(score_v2)
        groups_v2.append(group_v2)

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
            'form': forms[i],
            'subdivision_v2': subdivisions_v2[i],
            'score_v2': scores_v2[i],
            'group_v2': groups_v2[i],
            'is_fallback_v2': False,  # v3无兜底分类，矩阵穷举
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
        if k < len(rows) and rows[k]['group_v2'] == '震荡类':
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
    # 严重形态：中阴线及以下（score_v2 <= -0.5）
    sc = sum(1 for k in range(bp_start, ae + 1)
             if k < len(rows) and rows[k]['score_v2'] <= -0.5)
    cond2 = sc >= CONFIG['severe_form_count']
    pc = rows[bp_start - 1]['close'] if bp_start > 0 else rows[bp_start]['close']
    mc = min((rows[k]['close'] for k in range(bp_start, ae + 1) if k < len(rows)), default=pc)
    cond3 = (pc - mc) / pc > CONFIG['severe_pct_threshold'] if pc > 0 else False
    return (cond1 or cond2) and cond3


def find_main_break(rows, break_periods, cut_idx, segments=None):
    """
    找主断板期：距离切面日最近的"完整波"之后的断板期

    完整波定义：
    - 涨停段连续≥2天涨停（segments[i]长度≥2）
    - 且后面有断板期（break_periods[i]存在）

    单天涨停（孤立涨停）和切面日所在的未完结波 → 自动并入断板期
    """
    if not segments or not break_periods:
        return None, False

    # 找出对应"完整波"的断板期索引
    valid_indices = []
    for i in range(len(break_periods)):
        if i >= len(segments):
            break
        seg = segments[i]
        bp = break_periods[i]
        seg_length = seg[1] - seg[0] + 1

        # 完整波条件1：连续≥2天涨停
        if seg_length < 2:
            continue
        # 完整波条件2：断板期开始位置在切面日之前（含切面日当天）
        if bp[0] > cut_idx:
            continue

        valid_indices.append(i)

    if not valid_indices:
        return None, False

    # 选距离切面日最近的（bp[0]最大的那个）
    main_idx = max(valid_indices, key=lambda i: break_periods[i][0])

    bp = break_periods[main_idx]
    sev = is_severe_break(rows, bp[0], bp[1], cut_idx)
    return main_idx, sev


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

            # 断板期扫描：寻找满足延伸条件的涨停段
            # 不满足延伸条件的涨停当作断板期一部分，继续观察
            j = bs
            bdc = 0  # 从上一个涨停段结束后的总天数（含不延伸的涨停天）
            found_extend = False

            while j < n and bdc <= mw:
                if not rows[j]['is_zt']:
                    bdc += 1
                    j += 1
                    continue

                # 遇到涨停，检查延伸条件
                zt_streak = 0
                k = j
                while k < n and rows[k]['is_zt']:
                    zt_streak += 1
                    k += 1

                extend = False
                if zt_streak >= 2:
                    extend = True  # 连续≥2天涨停，直接延伸
                else:
                    # 单天涨停，检查3天涨幅>20%
                    if j + 2 < n:
                        ext_base = rows[j]['pre_close'] if j > 0 else rows[j]['open']
                        if ext_base > 0:
                            ext_day3 = rows[j + 2]['close']
                            ext_rise = (ext_day3 - ext_base) / ext_base
                            if ext_rise > 0.20:
                                extend = True

                if extend:
                    found_extend = True
                    break  # 找到满足延伸条件的涨停段
                else:
                    # 不满足延伸条件，把这些涨停天当作断板期一部分
                    bdc += zt_streak
                    j = k  # 跳过这些涨停天，继续扫描

            if not found_extend:
                # 观察窗口用完或到达数据末尾，序列结束
                if bdc > mw:
                    bps.append((bs, min(bs + mw - 1, n - 1)))
                else:
                    bps.append((bs, j - 1 if j < n else n - 1))
                break

            # 延伸成功
            be = j - 1
            if not check_break_continuity(rows, bs, be, ch):
                break
            bps.append((bs, be))
            nss = j
            while j < n and rows[j]['is_zt']:
                j += 1
            segs.append((nss, j - 1))
            ce = j - 1
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

def classify_research_scope(days, board_height):
    """研究范围分类：连板≤3板强制紧凑，连板≥7板强制宽泛"""
    # 规则1：连板≤3板 → 强制紧凑
    if board_height <= 3:
        return '紧凑'
    # 规则2：连板≥7板 → 强制宽泛
    if board_height >= 7:
        return '宽泛'
    # 规则3：按天数分类
    if days <= 3:
        return '紧凑'
    elif days <= 10:
        return '标准'
    return '宽泛'


def classify_d1_distance(days):
    """距D1分档（与断板天数完全一致的4档）"""
    if days <= 1:
        return '极短'
    elif days <= 3:
        return '短'
    elif days <= 7:
        return '中'
    return '长'


def classify_break_days(days):
    if days <= 1:
        return '极短'
    elif days <= 3:
        return '短'
    elif days <= 7:
        return '中'
    return '长'


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
            result.append({'form': '无', 'subdivision_v2': '无', 'emotion_class': '震荡',
                           'group_v2': '震荡类', 'pct': 0.0, 'vol_label': 0})
        else:
            r = rows[idx]
            emo_info = SUBDIVISION_V2_INFO.get(r['subdivision_v2'], {})
            result.append({
                'form': r['form'],
                'subdivision_v2': r['subdivision_v2'],
                'emotion_class': emo_info.get('emotion_class', '震荡'),
                'group_v2': r['group_v2'],
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
    # ===== 上涨波次统计（v4新规则）=====
    # 起波条件（满足任一即可）：
    #   1. 连续≥2天涨停 → 直接起波（豁免3天>20%检查）
    #   2. 单天涨停 + 3天涨幅>20% → 起波
    # 波的范围：从起波日开始，连续涨停的所有天
    # 第一个非涨停日 → 波结束
    waves_info = []
    i = seq_start
    while i <= cut_idx:
        # 跳过非涨停日
        if not rows[i]['is_zt']:
            i += 1
            continue

        # 计算从当前位置开始的连续涨停天数
        zt_streak = 0
        k = i
        while k <= cut_idx and rows[k]['is_zt']:
            zt_streak += 1
            k += 1

        # 起波条件
        triggered = False
        if zt_streak >= 2:
            # 条件1：连续≥2天涨停 → 直接起波
            triggered = True
        else:
            # 条件2：单天涨停，检查3天涨幅>20%
            if i + 2 <= cut_idx:
                base_close = rows[i]['pre_close'] if i > 0 else rows[i]['open']
                if base_close > 0:
                    day3_close = rows[i + 2]['close']
                    rise_3d = (day3_close - base_close) / base_close
                    if rise_3d > 0.20:
                        triggered = True

        if triggered:
            # 起波：波的范围 = 连续涨停的所有天（k已经是非涨停日位置）
            waves_info.append({
                'start': i,
                'end': k - 1,
                'zt_count': zt_streak
            })
            i = k  # 跳到这一波之后
        else:
            i += 1

    # ===== 剔除前置小波（迭代直到稳定）=====
    # 剔除条件：小波zt≤2 + 与下波间隔>3 + 下波zt≥5
    waves_info_before_trim = list(waves_info)  # 保留剔除前快照（用于诊断）
    trimmed_pre_waves = []
    while len(waves_info) >= 2:
        trimmed = False
        for wi in range(len(waves_info) - 1):
            wave = waves_info[wi]
            next_wave = waves_info[wi + 1]
            interval = next_wave['start'] - wave['end'] - 1
            if (wave['zt_count'] <= 2
                and interval > 3
                and next_wave['zt_count'] >= 5):
                # 剔除当前小波
                trimmed_pre_waves.append({
                    'start': wave['start'],
                    'end': wave['end'],
                    'zt_count': wave['zt_count'],
                    'interval_to_next': interval,
                    'next_wave_zt': next_wave['zt_count'],
                })
                del waves_info[wi]
                trimmed = True
                break
        if not trimmed:
            break

    # 波次分类
    wave_count = len(waves_info)
    if wave_count <= 1:
        wave_category = '1波'
    elif wave_count == 2:
        wave_category = '2波'
    else:
        wave_category = '多波'

    # 波间隔分析（紧凑波 vs 松散波）
    if len(waves_info) >= 2:
        wave_intervals = []
        for wi in range(1, len(waves_info)):
            interval = waves_info[wi]['start'] - waves_info[wi-1]['end'] - 1
            wave_intervals.append(interval)
        max_wave_interval = max(wave_intervals) if wave_intervals else 0
        if max_wave_interval <= 3:
            wave_pattern = '紧凑波'
        else:
            wave_pattern = '松散波'
    else:
        wave_intervals = []
        max_wave_interval = 0
        wave_pattern = '无'

    # board_height = 最长一波的涨停天数
    board_height = max((w['zt_count'] for w in waves_info), default=zt_days)
    if board_height == 0:  # 如果所有波都没涨停（理论上不应该出现）
        board_height = zt_days

    # ===== A15综合高度 =====
    height_category = classify_board_height(board_height)
    combined_height_val = pre_rally + board_height * 0.10
    combined_height_category = '高位' if combined_height_val >= CONFIG['combined_height_threshold'] else '低位'

    # ===== 研究范围（必须在board_height计算之后）=====
    research_scope = classify_research_scope(research_days, board_height)

    # ===== A12开盘涨幅 =====
    cut_open_pct = cut_row['open_pct']
    cut_open_pct_category = classify_open_pct(cut_open_pct)

    # ===== A组板型相关 =====
    # 用v2细分类统计涨停板型
    hs = {
        '一字涨停': 0,
        '缩量加速涨停': 0,
        '非缩量加速涨停': 0,
        '反转涨停': 0,
        '普通涨停': 0,
        '烂板涨停': 0,
    }
    sps = []
    vol_label_per_day = []
    for idx in range(seq_start, cut_idx + 1):
        sub = rows[idx]['subdivision_v2']
        if rows[idx]['is_zt']:
            sps.append(sub)  # 涨停日存细分类
            if idx < cut_idx and sub in hs:
                hs[sub] += 1
        else:
            sps.append(f'[{sub}]')  # 非涨停日加方括号
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
    if seq_labels and seq_labels[0] == 1:
        accel_count = 1
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
    mbpi, is_severe = find_main_break(rows, break_periods, cut_idx, segments)
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

    # ===== 高度回撤比（v3定义）=====
    # 序列范围内最高价(high)到切面日的最低价(low)的回撤
    # 注：含最高价当天和切面日当天
    cut_close = rows[cut_idx]['close']
    seq_range = list(range(seq_start, cut_idx + 1))
    max_high = max(rows[k]['high'] for k in seq_range)
    # 取最早出现max_high的位置（让回撤窗口最大）
    max_high_idx = next(k for k in seq_range if rows[k]['high'] == max_high)
    # 从最高价当天(含)到切面日(含)的最低价
    min_low = min(rows[k]['low'] for k in range(max_high_idx, cut_idx + 1))
    hr = (max_high - min_low) / max_high if max_high > 0 else 0
    hr_category = classify_height_retracement(hr)

    # ===== B组断板期指标 =====
    d1f, d1e = '无', '震荡'
    d1tz = d1td = False
    d2f, d2e = '无', '震荡'
    d1_pct = 0.0
    d2_pct = 0.0
    bpp = 0.0
    bpd = bad = 0
    buc = bdc_count = 0
    d1_idx = None
    d0_subdivision_v2 = '无'
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
            d1f = rows[bs]['subdivision_v2']  # v3：用细分类
            d1e = SUBDIVISION_V2_INFO.get(d1f, {}).get('emotion_class', '震荡')
            d1tz = rows[bs]['touched_zt']
            d1td = rows[bs]['touched_dt']
            d1_pct = rows[bs]['pct']

        # D0 = 涨停段最后一板（断板期前一天）
        if bs > 0:
            d0_subdivision_v2 = rows[bs - 1].get('subdivision_v2', '无')

        if bs + 1 <= be and bs + 1 < len(rows) and bs + 1 < cut_idx:
            d2f = rows[bs + 1]['subdivision_v2']  # v3：用细分类
            d2e = SUBDIVISION_V2_INFO.get(d2f, {}).get('emotion_class', '震荡')
            d2_pct = rows[bs + 1]['pct']

        zt_in_break = dt_in_break = 0
        for k in range(bs, cut_idx):
            if k < len(rows):
                sv = rows[k]['score_v2']
                if sv > 0.3:
                    buc += 1
                if sv < -0.3:
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
    else:
        # D0 = 涨停段最后一板（纯连板：切面日前一天）
        if cut_idx > 0:
            d0_subdivision_v2 = rows[cut_idx - 1].get('subdivision_v2', '无')

    d1_distance_cat = classify_d1_distance(cut_to_d1)
    break_days_cat = classify_break_days(bad) if cut_to_d1 > 0 else '无'

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
        'break_d1_pct': d1_pct,
        'break_d2_form': d2f, 'break_d2_emotion': d2e,
        'break_d2_pct': d2_pct,
        'break_period_days': bpd, 'break_actual_days': bad,
        'break_days_cat': break_days_cat,
        'cut_to_d1_days': cut_to_d1, 'd1_distance_cat': d1_distance_cat,
        'break_period_pct': bpp, 'break_period_pct_category': bppc,
        'big_up_count': buc, 'big_down_count': bdc_count,
        'density_category': denc, 'dt_intensity': dt_int,
        'break_count': bc, 'break_count_category': bc_cat,

        # D0（涨停段最后一板）
        'd0_subdivision_v2': d0_subdivision_v2,

        # 波次
        'wave_count': wave_count,
        'wave_category': wave_category,
        'waves_info': waves_info,
        'wave_pattern': wave_pattern,
        'wave_intervals': wave_intervals,
        'max_wave_interval': max_wave_interval,
        'trimmed_pre_waves': trimmed_pre_waves,
        'waves_info_before_trim': waves_info_before_trim,

        # M组
        'm_cut': m_cut, 'm_start': m_start,

        # E组
        'cut_form': cut_row['subdivision_v2'],  # v3：统一用细分类
        'cut_emotion': SUBDIVISION_V2_INFO.get(cut_row['subdivision_v2'], {}).get('emotion_class', '震荡'),
        'cut_subdivision': cut_row['subdivision_v2'],
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
                mc[0]['subdivision_v2'], mc[1]['subdivision_v2'], mc[2]['subdivision_v2'],
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
    if wc <= 1:
        p = 0
        for a in ta:
            p += 1
            if p % 200 == 0 or p == total:
                print(f"  {p}/{total} | {len(ac)} 案例", flush=True)
            ac.extend(_process_single_stock(a))
    else:
        try:
            with Pool(processes=wc) as pool:
                p = 0
                for cl in pool.imap_unordered(_process_single_stock, ta, chunksize=50):
                    p += 1
                    ac.extend(cl)
                    if p % 200 == 0 or p == total:
                        print(f"  {p}/{total} | {len(ac)} 案例", flush=True)
        except Exception as e:
            print(f"多进程失败({e})，单进程...")
            p = 0
            for a in ta:
                p += 1
                if p % 200 == 0 or p == total:
                    print(f"  {p}/{total} | {len(ac)} 案例", flush=True)
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
    """返回 (a_weight, b_weight)"""
    if scope == '紧凑':
        return 3.0, 1.0
    elif scope == '标准':
        return 2.0, 1.0
    return 1.0, 1.5


def get_scope_internal_boost(scope, indicator):
    """研究范围对A组内部指标的额外加权"""
    boosts = {
        '紧凑': {'A2': 1.5, 'A4': 1.5, 'A9': 1.5, 'A12': 1.3},
        '标准': {'A2': 1.2, 'A4': 1.2, 'A9': 1.2},
    }
    return boosts.get(scope, {}).get(indicator, 1.0)


def get_d1_weights(d1_cat):
    """距D1对B组内部的权重：返回 (d1_w, break_period_w)"""
    if d1_cat == '极短':
        return 1.5, 0.5
    elif d1_cat == '短':
        return 1.2, 0.8
    elif d1_cat == '中':
        return 1.0, 1.0
    return 0.8, 1.5


# ============================================================
# 硬匹配
# ============================================================

def hard_filter_with_downgrade(target_case, case_library):
    """硬匹配：纯门槛pass/fail（无扣分、无阈值）"""
    is_break = target_case['cut_to_d1_days'] > 0
    scope = target_case['research_scope']

    current = [c for c in case_library if c['stock_code'] != target_case['stock_code']]
    print(f"  排除同股票：{len(current)}")

    # ===== 第1层：绝对淘汰门槛 =====

    # 研究范围匹配（紧凑严格、标准/宽泛互通但天数差阈值不同）
    t_days = target_case['research_days']
    def _scope_match_check(c):
        c_scope = c['research_scope']
        c_days = c['research_days']
        day_diff = abs(t_days - c_days)
        if scope == '紧凑':
            if c_scope == '紧凑':
                return True  # 同档直接通过
            elif c_scope == '标准':
                return day_diff <= 2  # 跨1档：天数差≤2
            else:
                return False  # 紧凑vs宽泛：淘汰
        elif scope == '标准':
            if c_scope == '紧凑':
                return day_diff <= 2  # 跨1档：天数差≤2
            elif c_scope == '标准':
                return True  # 同档直接通过
            else:
                return day_diff <= 5  # 跨1档：天数差≤5
        else:  # 宽泛
            if c_scope == '紧凑':
                return False  # 宽泛vs紧凑：淘汰
            elif c_scope == '标准':
                return day_diff <= 5  # 跨1档：天数差≤5
            else:
                return True  # 同档直接通过
    current = [c for c in current if _scope_match_check(c)]
    print(f"  研究范围({scope}/{t_days}天)：{len(current)}")

    # 回撤比：差≥2档淘汰
    hr_order = {'未回撤': 0, '小幅回撤': 1, '大幅回撤': 2}
    t_hr = hr_order.get(target_case['height_retracement_category'], 1)
    current = [c for c in current
               if abs(hr_order.get(c['height_retracement_category'], 1) - t_hr) <= 1]
    print(f"  回撤比(差≤1档)：{len(current)}")

    # 最大涨幅：差≥2档淘汰
    rise_order = {'低位': 0, '中位': 1, '高位': 2, '超高位': 3}
    t_ro = rise_order.get(target_case['max_rise_category'], 1)
    current = [c for c in current
               if abs(rise_order.get(c['max_rise_category'], 1) - t_ro) <= 1]
    print(f"  涨幅(差≤1档)：{len(current)}")

    # 波次：差≥2档淘汰
    wave_order = {'1波': 0, '2波': 1, '多波': 2}
    t_wave = wave_order.get(target_case.get('wave_category', '1波'), 0)
    current = [c for c in current
               if abs(wave_order.get(c.get('wave_category', '1波'), 0) - t_wave) <= 1]
    print(f"  波次(差≤1档)：{len(current)}")

    # 波次pattern：紧凑波 vs 松散波 → 淘汰（仅2波及以上才比较）
    t_wave_pattern = target_case.get('wave_pattern', '无')
    if t_wave_pattern != '无':
        current = [c for c in current
                   if c.get('wave_pattern', '无') == '无' or c.get('wave_pattern', '无') == t_wave_pattern]
        print(f"  波次pattern({t_wave_pattern})：{len(current)}")
    else:
        # 标的是1波时，不限制候选的pattern（候选可以是任何pattern）
        pass

    # 连板高度：差≥2档淘汰
    h_order = {'低位': 0, '中位': 1, '高位': 2}
    t_h = h_order.get(target_case['height_category'], 1)
    current = [c for c in current
               if abs(h_order.get(c['height_category'], 1) - t_h) <= 1]
    print(f"  连板高度(差≤1档)：{len(current)}")

    # 标准型：板数差>2淘汰
    if scope == '标准':
        t_bh = target_case['board_height']
        current = [c for c in current if abs(c['board_height'] - t_bh) <= 2]
        print(f"  [标准]板数差≤2({t_bh}板)：{len(current)}")

    # 距D1：差≥2档淘汰（仅断板场景）
    days_order = {'极短': 0, '短': 1, '中': 2, '长': 3}
    if is_break:
        t_d1c = days_order.get(target_case['d1_distance_cat'], 1)
        current = [c for c in current
                   if abs(days_order.get(c['d1_distance_cat'], 1) - t_d1c) <= 1]
        print(f"  距D1(差≤1档)：{len(current)}")

    # 断板天数：差≥2档淘汰；跨1档且天数差>5天也淘汰
    if is_break:
        t_bdc = days_order.get(target_case['break_days_cat'], 1)
        t_bd_days = target_case['break_actual_days']
        def _break_days_check(c):
            c_bdc = days_order.get(c.get('break_days_cat', '无'), 1)
            gap = abs(c_bdc - t_bdc)
            if gap >= 2:
                return False
            if gap == 1:
                day_diff = abs(c.get('break_actual_days', 0) - t_bd_days)
                if day_diff > 5:
                    return False
            return True
        current = [c for c in current if _break_days_check(c)]
        print(f"  断板天数(差≤1档且天数差≤5)：{len(current)}")

    # 密度淘汰组合
    if is_break:
        DENSITY_ELIMINATE_PAIRS = {
            ('大涨主导', '冷淡'), ('冷淡', '大涨主导'),
            ('大涨主导', '大跌主导'), ('大跌主导', '大涨主导'),
            ('大跌主导', '冷淡'), ('冷淡', '大跌主导'),
            ('冷淡', '极端博弈'), ('极端博弈', '冷淡'),
        }
        t_den = target_case['density_category']
        current = [c for c in current
                   if (t_den, c['density_category']) not in DENSITY_ELIMINATE_PAIRS]
        print(f"  密度淘汰：{len(current)}")

    # ===== 第2层：逐个pass/fail门槛 =====
    ZT_DT_GROUPS = {'加速涨停类', '普通涨停类', '加速跌停类', '普通跌停类'}
    filtered = []
    cut_eliminated = 0
    d0_eliminated = 0
    sub_wave_eliminated = 0
    mcut_zt_dt_eliminated = 0
    板型不重合淘汰 = 0
    首板形态淘汰 = 0

    for c in current:
        # 次波高度跨2档淘汰（仅双方都是多波时）
        t_wave_cat = target_case.get('wave_category', '1波')
        c_wave_cat = c.get('wave_category', '1波')
        if t_wave_cat != '1波' and c_wave_cat != '1波':
            t_waves_sorted = sorted([w['zt_count'] for w in target_case.get('waves_info', [])], reverse=True)
            c_waves_sorted = sorted([w['zt_count'] for w in c.get('waves_info', [])], reverse=True)
            if len(t_waves_sorted) >= 2 and len(c_waves_sorted) >= 2:
                h_order_sub = {'低位': 0, '中位': 1, '高位': 2}
                t_sub_cat = classify_board_height(t_waves_sorted[1])
                c_sub_cat = classify_board_height(c_waves_sorted[1])
                sub_gap = abs(h_order_sub.get(t_sub_cat, 1) - h_order_sub.get(c_sub_cat, 1))
                if sub_gap >= 2:
                    sub_wave_eliminated += 1
                    continue

        # ===== 紧凑档：板型集合对称差≥2 → 淘汰 =====
        if scope == '紧凑':
            t_set_check = set(s for s in target_case['special_position_seq'] if not s.startswith('['))
            c_set_check = set(s for s in c['special_position_seq'] if not s.startswith('['))
            sym_diff_check = len(t_set_check.symmetric_difference(c_set_check))
            if sym_diff_check >= 2:
                板型不重合淘汰 += 1
                continue

        # ===== 紧凑档：首板形态必须近似匹配 → 淘汰 =====
        # （标准档首板不近似改为A组大扣分，不在这里淘汰；宽泛档不限制）
        if scope == '紧凑':
            t_first_check = target_case['m_start'][2].get('subdivision_v2', '无')
            c_first_check = c['m_start'][2].get('subdivision_v2', '无')
            if t_first_check != '无' and c_first_check != '无':
                first_match_check = match_kline_v2(t_first_check, c_first_check)
                if first_match_check not in ('精确', '近似'):
                    首板形态淘汰 += 1
                    continue

        # 紧凑档：切面日必须近似匹配
        if scope == '紧凑':
            t_cut_check = target_case['m_cut'][2].get('subdivision_v2', '无')
            c_cut_check = c['m_cut'][2].get('subdivision_v2', '无')
            if t_cut_check != '无' and c_cut_check != '无':
                cut_check_match = match_kline_v2(t_cut_check, c_cut_check)
                if cut_check_match not in ('精确', '近似'):
                    cut_eliminated += 1
                    continue

            # 紧凑档：D0必须近似匹配
            t_d0_check = target_case.get('d0_subdivision_v2', '无')
            c_d0_check = c.get('d0_subdivision_v2', '无')
            if t_d0_check != '无' and c_d0_check != '无':
                d0_check_match = match_kline_v2(t_d0_check, c_d0_check)
                if d0_check_match not in ('精确', '近似'):
                    d0_eliminated += 1
                    continue

        # M-cut前1天/前2天涨停跌停不匹配 → 淘汰
        mcut_zt_dt_eliminate = False
        for day_idx in [0, 1]:
            t_sub = target_case['m_cut'][day_idx].get('subdivision_v2', '无')
            c_sub = c['m_cut'][day_idx].get('subdivision_v2', '无')
            if t_sub != '无' and c_sub != '无':
                day_match = match_kline_v2(t_sub, c_sub)
                if day_match == '不匹配':
                    t_group = SUBDIVISION_V2_INFO.get(t_sub, {}).get('group', '')
                    c_group = SUBDIVISION_V2_INFO.get(c_sub, {}).get('group', '')
                    if t_group in ZT_DT_GROUPS or c_group in ZT_DT_GROUPS:
                        mcut_zt_dt_eliminate = True
                        break
        if mcut_zt_dt_eliminate:
            mcut_zt_dt_eliminated += 1
            continue

        # 通过所有门槛
        c['_hard_penalty'] = 0
        c['_mcut_penalized'] = []
        c['_mstart_penalized'] = []
        filtered.append(c)

    print(f"  次波高度淘汰：{sub_wave_eliminated}")
    print(f"  [紧凑]切面日淘汰：{cut_eliminated}")
    print(f"  [紧凑]D0淘汰：{d0_eliminated}")
    print(f"  M-cut涨停跌停淘汰：{mcut_zt_dt_eliminated}")
    print(f"  [紧凑]板型不重合淘汰：{板型不重合淘汰}")
    print(f"  [紧凑]首板形态淘汰：{首板形态淘汰}")
    print(f"  通过硬匹配：{len(filtered)}")

    return filtered, 0


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

    # A1b 紧凑档主波高度精细匹配（一致+5，不一致-10）
    if scope == '紧凑':
        if tc['board_height'] == cc['board_height']:
            v = CONFIG['bonus_a1_compact_match']
            b += v
            d.append(f"[紧凑]主波高度一致({tc['board_height']}板)+{v}")
        else:
            v = CONFIG['penalty_a1_compact_mismatch']
            p += v
            d.append(f"[紧凑]主波高度不一致({tc['board_height']}板vs{cc['board_height']}板)-{v}")

    # A1c 紧凑档D0近似扣分（精确0，近似-10×3.0=-30）
    # 注：D0情绪/不匹配在第1层已淘汰
    if scope == '紧凑':
        t_d0_sub = tc.get('d0_subdivision_v2', '无')
        c_d0_sub = cc.get('d0_subdivision_v2', '无')
        if t_d0_sub != '无' and c_d0_sub != '无':
            d0_match = match_kline_v2(t_d0_sub, c_d0_sub)
            if d0_match == '近似':
                v = CONFIG['penalty_a1_d0_approx']
                p += v
                d.append(f"[紧凑]D0近似({t_d0_sub}vs{c_d0_sub})-{v}")

    # A1b 次波高度（仅双方都是多波时）
    t_wave_cat = tc.get('wave_category', '1波')
    c_wave_cat = cc.get('wave_category', '1波')
    if t_wave_cat != '1波' and c_wave_cat != '1波':
        t_waves_sorted = sorted([w['zt_count'] for w in tc.get('waves_info', [])], reverse=True)
        c_waves_sorted = sorted([w['zt_count'] for w in cc.get('waves_info', [])], reverse=True)
        if len(t_waves_sorted) >= 2 and len(c_waves_sorted) >= 2:
            t_sub_cat = classify_board_height(t_waves_sorted[1])
            c_sub_cat = classify_board_height(c_waves_sorted[1])
            h_order_sub = {'低位': 0, '中位': 1, '高位': 2}
            sub_gap = abs(h_order_sub.get(t_sub_cat, 1) - h_order_sub.get(c_sub_cat, 1))
            if sub_gap == 1:
                v = CONFIG['penalty_subwave_cross_1']
                p += v
                d.append(f"次波高度跨1档({t_waves_sorted[1]}板{t_sub_cat} vs {c_waves_sorted[1]}板{c_sub_cat})-{v}")

    # ===== 新A2：板型集合匹配（合并原A2+A3+A4）=====
    # 提取双方涨停日的细分类序列（不含切面日，因为切面日在m_cut处理）
    t_zt_seq = [s for s in tc['special_position_seq'] if not s.startswith('[')]
    c_zt_seq = [s for s in cc['special_position_seq'] if not s.startswith('[')]
    t_set = set(t_zt_seq)
    c_set = set(c_zt_seq)

    # 对称差大小
    sym_diff_count = len(t_set.symmetric_difference(c_set))

    # 判定集合匹配档位
    if sym_diff_count == 0:
        if scope == '紧凑':
            # 紧凑档需顺序一致+板数一致
            if t_zt_seq == c_zt_seq:
                a2_level = '完全重合'
            else:
                a2_level = '部分重合'
        else:
            a2_level = '完全重合'
    elif sym_diff_count <= 2:
        a2_level = '部分重合'
    else:
        a2_level = '不重合'

    # 加扣分（基础值，由a_w自动加权）
    if a2_level == '完全重合':
        v = CONFIG['bonus_a2_perfect']
        b += v
        d.append(f"板型完全重合+{v}")
    elif a2_level == '部分重合':
        if scope == '宽泛':
            d.append(f"板型部分重合(对称差{sym_diff_count}) 0扣分")
        elif scope == '紧凑':
            v = CONFIG['penalty_a2_partial_compact']
            p += v
            d.append(f"板型部分重合(对称差{sym_diff_count})-{v}")
        else:  # 标准
            v = CONFIG['penalty_a2_partial_standard']
            p += v
            d.append(f"板型部分重合(对称差{sym_diff_count})-{v}")
    else:  # 不重合
        if scope == '宽泛':
            d.append(f"板型不重合(对称差{sym_diff_count}) 0扣分")
        elif scope == '标准':
            v = CONFIG['penalty_a2_none']
            p += v
            d.append(f"板型不重合(对称差{sym_diff_count})-{v}")
        # 紧凑档不重合已在第1层淘汰

    # ===== 新A3：数量差异（每超1个扣1分基础值）=====
    all_subs = t_set | c_set
    total_excess = sum(
        max(0, abs(tc['history_special'].get(s, 0) - cc['history_special'].get(s, 0)) - 1)
        for s in all_subs
    )
    if total_excess > 0:
        p += total_excess
        d.append(f"数量差异(超{total_excess}个)-{total_excess}")

    # ===== 新A4：标准档首板形态不近似 → 大扣分 =====
    # （紧凑档已在第1层淘汰；宽泛档由M-start自然处理）
    if scope == '标准':
        t_first_form = tc['m_start'][2].get('subdivision_v2', '无')
        c_first_form = cc['m_start'][2].get('subdivision_v2', '无')
        if t_first_form != '无' and c_first_form != '无':
            first_match = match_kline_v2(t_first_form, c_first_form)
            if first_match not in ('精确', '近似'):
                v = CONFIG['penalty_a4_first_no_approx']
                p += v
                d.append(f"[标准]首板形态{first_match}({t_first_form}vs{c_first_form})-{v}")

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

    # ===== A17：最大涨幅同档差异处理 =====
    rise_order = {'低位': 0, '中位': 1, '高位': 2, '超高位': 3}
    t_ro = rise_order.get(tc['max_rise_category'], 1)
    c_ro = rise_order.get(cc['max_rise_category'], 1)
    ro_gap = abs(t_ro - c_ro)

    if ro_gap == 1:
        # 跨1档但相对差≤20%时不扣分（处理边界案例）
        t_mr_val = tc['max_rise']
        c_mr_val = cc['max_rise']
        max_val_mr = max(abs(t_mr_val), abs(c_mr_val), 0.01)
        rel_diff_mr = abs(t_mr_val - c_mr_val) / max_val_mr
        if rel_diff_mr <= 0.20:
            d.append(f"最大涨幅跨1档但相对差{rel_diff_mr:.1%}≤20%(不扣分)")
        else:
            v = CONFIG['penalty_max_rise_1']
            p += v
            d.append(f"最大涨幅跨1档(相对差{rel_diff_mr:.1%})-{v}")
    elif ro_gap == 0:
        t_mr_val = tc['max_rise']
        c_mr_val = cc['max_rise']
        abs_diff_mr = abs(t_mr_val - c_mr_val)
        if abs_diff_mr <= 0.01:
            v = CONFIG['bonus_max_rise_same']
            b += v
            d.append(f"最大涨幅极相似(绝对差{abs_diff_mr:.1%})+{v}")
        elif abs_diff_mr <= 0.03:
            d.append(f"最大涨幅相近(绝对差{abs_diff_mr:.1%}) 0")
        else:
            max_val = max(abs(t_mr_val), abs(c_mr_val), 0.01)
            rel_diff = abs_diff_mr / max_val
            if rel_diff <= 0.20:
                v = CONFIG['bonus_max_rise_same']
                b += v
                d.append(f"最大涨幅同档极相似(相对差{rel_diff:.1%})+{v}")
            else:
                cap = CONFIG['penalty_max_rise_same_cap']
                penalty_v = round(min((rel_diff - 0.20) / 0.30 * cap, cap))
                if penalty_v > 0:
                    p += penalty_v
                    d.append(f"最大涨幅同档大差距(相对差{rel_diff:.1%})-{penalty_v}")

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

    # B0a 距D1跨1档天数差扣分（移自硬匹配第2层）
    days_order_bp = {'极短': 0, '短': 1, '中': 2, '长': 3}
    t_d1c_bp = days_order_bp.get(tc['d1_distance_cat'], 1)
    c_d1c_bp = days_order_bp.get(cc['d1_distance_cat'], 1)
    if abs(t_d1c_bp - c_d1c_bp) == 1:
        day_diff = abs(tc['cut_to_d1_days'] - cc['cut_to_d1_days'])
        v = min(day_diff * CONFIG['hp_days_per_diff'], CONFIG['hp_days_cap'])
        p += v
        d.append(f"距D1跨1档(差{day_diff}天)-{v}")

    # B0b 断板天数跨1档天数差扣分（移自硬匹配第2层）
    t_bdc_bp = days_order_bp.get(tc.get('break_days_cat', '无'), 1)
    c_bdc_bp = days_order_bp.get(cc.get('break_days_cat', '无'), 1)
    if abs(t_bdc_bp - c_bdc_bp) == 1:
        day_diff = abs(tc['break_actual_days'] - cc['break_actual_days'])
        v = min(day_diff * CONFIG['hp_days_per_diff'], CONFIG['hp_days_cap'])
        p += v
        d.append(f"断板天数跨1档(差{day_diff}天)-{v}")

    # B0c 密度通融组合扣分（移自硬匹配第2层）
    DENSITY_PENALTY_PAIRS = {
        ('大涨主导', '极端博弈'), ('极端博弈', '大涨主导'),
        ('大跌主导', '极端博弈'), ('极端博弈', '大跌主导'),
    }
    if tc['density_category'] != cc['density_category']:
        if (tc['density_category'], cc['density_category']) in DENSITY_PENALTY_PAIRS:
            v = CONFIG['hp_density_match_penalty']
            p += v
            d.append(f"密度通融({tc['density_category']}vs{cc['density_category']})-{v}")

    # B0d 跌停强度扣分（移自硬匹配第2层）
    dt_order_bp = {'无跌停': 0, '单跌停': 1, '连跌停': 2}
    dt_gap = abs(dt_order_bp.get(tc['dt_intensity'], 0) - dt_order_bp.get(cc['dt_intensity'], 0))
    if dt_gap == 1:
        v = CONFIG['hp_dt_intensity_1gap']
        p += v
        d.append(f"跌停强度差1档-{v}")
    elif dt_gap == 2:
        v = CONFIG['hp_dt_intensity_2gap']
        p += v
        d.append(f"跌停强度差2档-{v}")

    # B0e 回撤比（跨档扣分 + 同档差异处理）
    hr_order_b = {'未回撤': 0, '小幅回撤': 1, '大幅回撤': 2}
    t_hr_b = hr_order_b.get(tc['height_retracement_category'], 1)
    c_hr_b = hr_order_b.get(cc['height_retracement_category'], 1)
    hr_gap_b = abs(t_hr_b - c_hr_b)

    if hr_gap_b == 1:
        # 跨1档但相对差≤20%时不扣分（处理边界案例）
        t_hr_v = tc['height_retracement']
        c_hr_v = cc['height_retracement']
        max_val_hr = max(abs(t_hr_v), abs(c_hr_v), 0.01)
        rel_diff_hr = abs(t_hr_v - c_hr_v) / max_val_hr
        if rel_diff_hr <= 0.20:
            d.append(f"回撤比跨1档但相对差{rel_diff_hr:.1%}≤20%(不扣分)")
        else:
            v = CONFIG['penalty_height_retrace_1']
            p += v
            d.append(f"回撤比跨1档(相对差{rel_diff_hr:.1%})-{v}")
    elif hr_gap_b == 0:
        t_hr_v = tc['height_retracement']
        c_hr_v = cc['height_retracement']
        abs_diff_b = abs(t_hr_v - c_hr_v)
        if abs_diff_b <= 0.01:
            # 绝对差≤1%，极相似
            v = CONFIG['bonus_height_retrace_same']
            b += v
            d.append(f"回撤比极相似(绝对差{abs_diff_b:.1%})+{v}")
        elif abs_diff_b <= 0.03:
            # 绝对差≤3%，不加不扣
            d.append(f"回撤比相近(绝对差{abs_diff_b:.1%}) 0")
        else:
            # 绝对差>3%，进入相对差逻辑
            max_val_b = max(abs(t_hr_v), abs(c_hr_v), 0.01)
            rel_diff_b = abs_diff_b / max_val_b
            if rel_diff_b <= 0.20:
                v = CONFIG['bonus_height_retrace_same']
                b += v
                d.append(f"回撤比同档极相似(相对差{rel_diff_b:.1%})+{v}")
            else:
                cap = CONFIG['penalty_height_retrace_same_cap']
                penalty_v = round(min((rel_diff_b - 0.20) / 0.30 * cap, cap))
                if penalty_v > 0:
                    p += penalty_v
                    d.append(f"回撤比同档大差距(相对差{rel_diff_b:.1%})-{penalty_v}")

    # B10断板次数
    if cc['break_count_category'] != tc['break_count_category']:
        v = round(CONFIG['penalty_break_count'] * bp_w)
        p += v
        d.append(f"断板次数-{v}")

    # B10b+c 紧凑档断板天数精细匹配（合并：断板天数和距D1本质同步，只判一次）
    scope_b = tc['research_scope']
    if scope_b == '紧凑':
        bd_match = tc['break_actual_days'] == cc['break_actual_days']
        d1_match = tc['cut_to_d1_days'] == cc['cut_to_d1_days']
        if bd_match and d1_match:
            v = CONFIG['bonus_b10b_match']
            b += v
            d.append(f"[紧凑]断板期天数一致({tc['break_actual_days']}天/{tc['cut_to_d1_days']}天)+{v}")
        else:
            v = CONFIG['penalty_b10b_mismatch']
            p += v
            d.append(f"[紧凑]断板期天数不一致(断板{tc['break_actual_days']}vs{cc['break_actual_days']}/距D1 {tc['cut_to_d1_days']}vs{cc['cut_to_d1_days']})-{v}")

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

    # B1 D1（v2新规则：精确+10、近似0、情绪相同-15、情绪不同-30）
    t_d1_sub = tc.get('break_d1_form', '无')
    c_d1_sub = cc.get('break_d1_form', '无')
    if t_d1_sub != '无' and c_d1_sub != '无':
        t_d1_pct = tc.get('break_d1_pct', 0)
        c_d1_pct = cc.get('break_d1_pct', 0)
        match_level = match_kline_v2(t_d1_sub, c_d1_sub, t_d1_pct, c_d1_pct)
        if match_level == '精确':
            v = round(CONFIG['b_d1_exact_bonus'] * d1_w)
            b += v
            d.append(f"D1精确+{v}")
        elif match_level == '近似':
            # 近似不加分也不扣分
            d.append(f"D1近似(0)")
        elif match_level == '情绪':
            v = round(CONFIG['b_d1_emotion_penalty'] * d1_w)
            p += v
            d.append(f"D1情绪-{v}")
        else:  # 不匹配
            v = round(CONFIG['b_d1_diff_emotion_penalty'] * d1_w)
            p += v
            d.append(f"D1不匹配-{v}")

    # B2 D2（v2新规则：D1的0.5倍）
    if tc['break_actual_days'] > 1:
        t_d2_sub = tc.get('break_d2_form', '无')
        c_d2_sub = cc.get('break_d2_form', '无')
        if t_d2_sub != '无' and c_d2_sub != '无':
            t_d2_pct = tc.get('break_d2_pct', 0)
            c_d2_pct = cc.get('break_d2_pct', 0)
            match_level = match_kline_v2(t_d2_sub, c_d2_sub, t_d2_pct, c_d2_pct)
            if match_level == '精确':
                v = CONFIG['b_d2_exact_bonus']
                b += v
                d.append(f"D2精确+{v}")
            elif match_level == '近似':
                d.append(f"D2近似(0)")
            elif match_level == '情绪':
                v = CONFIG['b_d2_emotion_penalty']
                p += v
                d.append(f"D2情绪-{v}")
            else:  # 不匹配
                v = CONFIG['b_d2_diff_emotion_penalty']
                p += v
                d.append(f"D2不匹配-{v}")

    # B3 D1触涨停（双方+5、单方-5，与E组对齐）
    if tc['break_d1_touched_zt'] and cc['break_d1_touched_zt']:
        v = round(CONFIG['bonus_touch_zt_match'] * d1_w)
        b += v
        d.append(f"D1触涨停双方+{v}")
    elif tc['break_d1_touched_zt'] != cc['break_d1_touched_zt']:
        v = round(CONFIG['hp_e_touch_one_side_penalty'] * d1_w)
        p += v
        d.append(f"D1触涨停单方-{v}")

    # B4 D1触跌停（双方+5、单方-5，与E组对齐）
    if tc['break_d1_touched_dt'] and cc['break_d1_touched_dt']:
        v = round(CONFIG['bonus_touch_dt_match'] * d1_w)
        b += v
        d.append(f"D1触跌停双方+{v}")
    elif tc['break_d1_touched_dt'] != cc['break_d1_touched_dt']:
        v = round(CONFIG['hp_e_touch_one_side_penalty'] * d1_w)
        p += v
        d.append(f"D1触跌停单方-{v}")

    # B波次
    wave_order = {'1波': 0, '2波': 1, '多波': 2}
    t_wo = wave_order.get(tc.get('wave_category', '1波'), 0)
    c_wo = wave_order.get(cc.get('wave_category', '1波'), 0)
    wave_gap = abs(t_wo - c_wo)
    if wave_gap == 1:
        v = round(CONFIG['penalty_wave_cross_1'] * bp_w)
        p += v
        d.append(f"波次跨1档-{v}")

    return p, b, d


# ============================================================
# M组评分：微型结构（v2新规则）
# ============================================================

def calc_micro_day_v2(t_day, c_day, base_score):
    """
    单天微型结构评分（v2新规则）
    返回: (penalty, bonus, detail_str)
    """
    ts = t_day.get('subdivision_v2', '无')
    cs = c_day.get('subdivision_v2', '无')

    if ts == '无' or cs == '无':
        return 0, 0, "数据缺失"

    # 传入pct判断假阴线/假阳线（一真一假降级为近似）
    t_pct = t_day.get('pct', 0)
    c_pct = c_day.get('pct', 0)
    match_level = match_kline_v2(ts, cs, t_pct, c_pct)

    if match_level == '精确':
        v = round(base_score * CONFIG['micro_exact_mult'])
        return 0, v, f"精确({ts})+{v}"
    elif match_level == '近似':
        v = round(base_score * CONFIG['micro_approx_mult'])
        return 0, v, f"近似({ts}vs{cs})+{v}"
    elif match_level == '情绪':
        v = round(base_score * CONFIG['micro_emotion_mult'])
        return v, 0, f"情绪({ts}vs{cs})-{v}"
    else:
        v = round(base_score * CONFIG['micro_mismatch_mult'])
        return v, 0, f"不匹配({ts}vs{cs})-{v}"


def calc_mcut_hard_penalty(t_mcut, c_mcut, scope):
    """
    M-cut硬匹配扣分（不叠加权重）
    返回: (penalty, penalized_positions)
    """
    t_cut = t_mcut[2].get('subdivision_v2', '无')
    c_cut = c_mcut[2].get('subdivision_v2', '无')
    t_d1 = t_mcut[1].get('subdivision_v2', '无')
    c_d1 = c_mcut[1].get('subdivision_v2', '无')

    if t_cut == '无' or c_cut == '无':
        return 0, []

    cut_match = match_kline_v2(t_cut, c_cut)
    cut_rank = {'精确': 0, '近似': 1, '情绪': 2, '不匹配': 3}.get(cut_match, 3)

    if t_d1 != '无' and c_d1 != '无':
        d1_match = match_kline_v2(t_d1, c_d1)
        d1_rank = {'精确': 0, '近似': 1, '情绪': 2, '不匹配': 3}.get(d1_match, 3)
    else:
        d1_match = '数据缺失'
        d1_rank = 1

    if scope == '紧凑':
        # 紧凑档切面日要求近似（精确/近似=0扣分，情绪/不匹配已在外层淘汰）
        # 这里只处理"达标但不完美"的扣分
        if cut_rank > 1:
            # 情绪/不匹配：理论上已被外层淘汰，防御性返回
            return [0, 0, 30, 45][cut_rank], [2]
        # 切面日达标（精确/近似），看前1天
        if d1_rank <= 1:
            return 0, []
        elif d1_rank == 2:
            return 15, [1]
        else:
            return 30, [1]

    elif scope == '标准':
        if cut_rank > 1:
            return [0, 0, 15, 30][cut_rank], [2]
        if d1_rank <= 2:
            return 0, []
        else:
            return 15, [1]

    elif scope == '宽泛':
        if cut_rank > 1:
            return [0, 0, 15, 30][cut_rank], [2]
        if d1_rank <= 1:
            return 0, []
        else:
            return 15, [1]

    return 0, []


def calc_mstart_hard_penalty(t_mstart, c_mstart, scope):
    """
    M-start硬匹配扣分
    返回: (扣分值, 被扣分的位置列表)
    位置编号: 0=前2天, 1=前1天, 2=首板
    """
    if scope == '宽泛':
        return 0, []  # 宽泛档不做硬匹配

    t_start = t_mstart[2].get('subdivision_v2', '无')
    c_start = c_mstart[2].get('subdivision_v2', '无')
    t_d1 = t_mstart[1].get('subdivision_v2', '无')
    c_d1 = c_mstart[1].get('subdivision_v2', '无')

    if t_start == '无' or c_start == '无':
        return 0, []

    start_match = match_kline_v2(t_start, c_start)
    start_rank = {'精确': 0, '近似': 1, '情绪': 2, '不匹配': 3}.get(start_match, 3)

    if scope == '紧凑':
        # 首板要求精确(0)，前1天要求近似(1)
        if start_rank > 0:
            penalty = [0, 15, 30, 45][start_rank]
            return penalty, [2]  # 首板被扣分
        # 首板精确，看前1天
        if t_d1 != '无' and c_d1 != '无':
            d1_match = match_kline_v2(t_d1, c_d1)
            d1_rank = {'精确': 0, '近似': 1, '情绪': 2, '不匹配': 3}.get(d1_match, 3)
            if d1_rank <= 1:
                return 0, []
            elif d1_rank == 2:
                return 15, [1]
            else:
                return 30, [1]
        return 0, []

    elif scope == '标准':
        # 首板要求近似(1)
        if start_rank > 1:
            penalty = [0, 0, 15, 30][start_rank]
            return penalty, [2]
        return 0, []

    return 0, []


def calc_mcut_score(tc, cc):
    """M-cut切面日微型结构评分"""
    p = b = 0
    d = []
    weight = CONFIG['mcut_group_weight']
    base_scores = [CONFIG['micro_base_day2'], CONFIG['micro_base_day1'], CONFIG['micro_base_day0']]
    labels = ['前2天', '前1天', '切面日']
    tm = tc['m_cut']
    cm = cc['m_cut']

    for i in range(3):
        dp, db, dd = calc_micro_day_v2(tm[i], cm[i], base_scores[i])
        dp_w = round(dp * weight)
        db_w = round(db * weight)
        p += dp_w
        b += db_w
        d.append(f"M-cut{labels[i]}:{dd}")

    return p, b, d


def calc_mstart_score(tc, cc):
    """M-start首板微型结构评分"""
    p = b = 0
    d = []
    scope = tc['research_scope']

    if scope == '紧凑':
        weight = CONFIG['mstart_group_weight_compact']
    elif scope == '标准':
        weight = CONFIG['mstart_group_weight_standard']
    else:
        weight = CONFIG['mstart_group_weight_wide']

    base_scores = [CONFIG['micro_base_day2'], CONFIG['micro_base_day1'], CONFIG['micro_base_day0']]
    labels = ['前2天', '前1天', '首板']
    tm = tc['m_start']
    cm = cc['m_start']

    for i in range(3):
        # 标准档首板（i=2）：如果A4已触发扣分，跳过不重复
        if i == 2 and scope == '标准':
            ts_first = tm[2].get('subdivision_v2', '无')
            cs_first = cm[2].get('subdivision_v2', '无')
            if ts_first != '无' and cs_first != '无':
                first_match_ms = match_kline_v2(ts_first, cs_first,
                                                tm[2].get('pct', 0), cm[2].get('pct', 0))
                if first_match_ms not in ('精确', '近似'):
                    d.append(f"M-start首板:已由A4处理(跳过)")
                    continue

        dp, db, dd = calc_micro_day_v2(tm[i], cm[i], base_scores[i])
        dp_w = round(dp * weight)
        db_w = round(db * weight)
        p += dp_w
        b += db_w
        d.append(f"M-start{labels[i]}:{dd}")

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

    # E2触涨停（双方触及+5、单方触及-5）
    if tc['cut_touched_zt'] and cc['cut_touched_zt']:
        b += CONFIG['bonus_touch_zt_match']  # +5
        d.append(f"触涨停双方+{CONFIG['bonus_touch_zt_match']}")
    elif tc['cut_touched_zt'] != cc['cut_touched_zt']:
        # 单方触及（一方有一方无）
        v = CONFIG['hp_e_touch_one_side_penalty']  # -5
        p += v
        d.append(f"触涨停单方-{v}")

    # E3触跌停（双方触及+5、单方触及-5）
    if tc['cut_touched_dt'] and cc['cut_touched_dt']:
        b += CONFIG['bonus_touch_dt_match']
        d.append(f"触跌停双方+{CONFIG['bonus_touch_dt_match']}")
    elif tc['cut_touched_dt'] != cc['cut_touched_dt']:
        v = CONFIG['hp_e_touch_one_side_penalty']
        p += v
        d.append(f"触跌停单方-{v}")

    # E4开盘涨幅
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
    elif op_gap == 0:
        t_op = tc['cut_open_pct']
        c_op = cc['cut_open_pct']
        abs_diff_op = abs(t_op - c_op)
        if abs_diff_op <= 0.01:
            v = CONFIG['bonus_open_pct_same']
            b += v
            d.append(f"开盘涨幅极相似(绝对差{abs_diff_op:.1%})+{v}")
        elif abs_diff_op <= 0.03:
            d.append(f"开盘涨幅相近(绝对差{abs_diff_op:.1%}) 0")
        else:
            max_val = max(abs(t_op), abs(c_op), 0.01)
            rel_diff = abs_diff_op / max_val
            if rel_diff <= 0.20:
                v = CONFIG['bonus_open_pct_same']
                b += v
                d.append(f"开盘涨幅同档极相似(相对差{rel_diff:.1%})+{v}")
            else:
                cap = CONFIG['penalty_open_pct_same_cap']
                pv = round(min((rel_diff - 0.20) / 0.30 * cap, cap))
                if pv > 0:
                    p += pv
                    d.append(f"开盘涨幅同档大差距(相对差{rel_diff:.1%})-{pv}")

    return p, b, d


# ============================================================
# 汇总评分 + 封顶
# ============================================================

def apply_group_caps(p, b, bonus_cap, penalty_cap, label, details_list):
    """
    对加权后的扣分p和加分b应用封顶（加分总额和扣分总额分别封顶）
    返回封顶后的 (p, b)
    """
    if b > bonus_cap:
        details_list.append(f"{label}加分封顶({b}→{bonus_cap})")
        b = bonus_cap
    if p > penalty_cap:
        details_list.append(f"{label}扣分封顶({p}→{penalty_cap})")
        p = penalty_cap
    return p, b


def calc_final_score(tc, cands, ap):
    mp = CONFIG['max_penalty_threshold']
    scope = tc['research_scope']
    a_w, b_w = get_scope_weights(scope)
    bonus_cap = CONFIG['cap_bonus_all']  # 加分封顶+20

    # 各组扣分封顶
    if scope == '紧凑':
        a_penalty_cap = CONFIG['cap_penalty_a_compact']
        b_penalty_cap = CONFIG['cap_penalty_b_compact']
        ms_penalty_cap = CONFIG['cap_penalty_mstart_compact']
    elif scope == '标准':
        a_penalty_cap = CONFIG['cap_penalty_a_standard']
        b_penalty_cap = CONFIG['cap_penalty_b_standard']
        ms_penalty_cap = CONFIG['cap_penalty_mstart_standard']
    else:
        a_penalty_cap = CONFIG['cap_penalty_a_wide']
        b_penalty_cap = CONFIG['cap_penalty_b_wide']
        ms_penalty_cap = CONFIG['cap_penalty_mstart_wide']
    mc_penalty_cap = CONFIG['cap_penalty_mcut']
    e_penalty_cap = CONFIG['cap_penalty_e']

    b_eliminated = 0
    scored = []
    for c in cands:
        # ===== A组（外部权重a_w）=====
        a_p, a_b, a_d = calc_a_score(tc, c)
        a_p_w = round(a_p * a_w)
        a_b_w = round(a_b * a_w)
        a_p_w, a_b_w = apply_group_caps(a_p_w, a_b_w, bonus_cap, a_penalty_cap, 'A组', a_d)

        # ===== B组（外部权重b_w）=====
        b_p, b_b, b_d = calc_b_score(tc, c)
        b_p_w = round(b_p * b_w)
        b_b_w = round(b_b * b_w)

        # 断板期原始加权扣分超阈值 → 淘汰（封顶前判断）
        if b_p_w > CONFIG['b_raw_penalty_eliminate']:
            b_eliminated += 1
            continue

        b_p_w, b_b_w = apply_group_caps(b_p_w, b_b_w, bonus_cap, b_penalty_cap, 'B组', b_d)

        # ===== M-cut（内部已应用×2.0权重）=====
        mc_p, mc_b, mc_d = calc_mcut_score(tc, c)
        mc_p, mc_b = apply_group_caps(mc_p, mc_b, bonus_cap, mc_penalty_cap, 'M-cut', mc_d)

        # ===== M-start（内部已应用×1.5/×1.0/×0.5权重）=====
        ms_p, ms_b, ms_d = calc_mstart_score(tc, c)
        ms_p, ms_b = apply_group_caps(ms_p, ms_b, bonus_cap, ms_penalty_cap, 'M-start', ms_d)

        # ===== E组（权重×2.0）=====
        e_p, e_b, e_d = calc_e_score(tc, c)
        e_p_w = round(e_p * 2.0)
        e_b_w = round(e_b * 2.0)
        e_p_w, e_b_w = apply_group_caps(e_p_w, e_b_w, bonus_cap, e_penalty_cap, 'E组', e_d)

        # ===== 汇总 =====
        # 硬匹配只做门槛，无扣分
        total_p = a_p_w + b_p_w + mc_p + ms_p + e_p_w
        total_b = a_b_w + b_b_w + mc_b + ms_b + e_b_w

        if (total_p - total_b) >= mp:
            continue

        det = []
        det.extend(a_d)
        det.extend(b_d)
        det.extend(mc_d)
        det.extend(ms_d)
        det.extend(e_d)

        c['individual_penalty'] = total_p
        c['individual_bonus'] = total_b
        c['penalty_details'] = det
        scored.append(c)

    if b_eliminated > 0:
        print(f"  B组原始扣分>{CONFIG['b_raw_penalty_eliminate']}淘汰：{b_eliminated}")
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
        gr = '高' if sc >= 80 else '中' if sc >= 60 else '低'
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
            '波次': c['wave_category'],
            '首日状态': c['first_day_state'],
            '启动位置': c['pre_rally_category'],
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
            '断板天数档': c['break_days_cat'],
            'D1形态': f"{c['break_d1_form']}({c['break_d1_emotion']})",
            'D2形态': f"{c['break_d2_form']}({c['break_d2_emotion']})",
            '断板次数': f"{c['break_count']}({c['break_count_category']})",
            '断板涨跌幅': f"{c['break_period_pct']:.2%}({c['break_period_pct_category']})",
            '密度': c['density_category'],
            '涨数': c['big_up_count'], '跌数': c['big_down_count'],
            '跌停强度': c['dt_intensity'],
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
    sv = '[严重]' if tc['is_severe_break'] else '普通'
    mc = tc['m_cut']
    ms = tc['m_start']
    print("\n" + "=" * 70)
    print(f"标的股信息（断板版 v2.0）")
    print("=" * 70)
    print(f"  代码：{tc['stock_code']}  名称：{tc['stock_name']}")
    print(f"  切面日：{str(tc['cut_date'])[:10]}")
    print(f"  研究范围：{tc['research_days']}天({tc['research_scope']})")
    print(f"  断板类型：{sv}  距D1:{tc['cut_to_d1_days']}天({tc['d1_distance_cat']})")
    print(f"  断板天数：{tc['break_actual_days']}天({tc['break_days_cat']})")
    print(f"  最大涨幅：{tc['max_rise']:.1%}({tc['max_rise_category']})")
    print(f"  高度回撤比：{tc['height_retracement']:.1%}({tc['height_retracement_category']})")
    waves_sorted = sorted([w['zt_count'] for w in tc['waves_info']], reverse=True)
    if len(waves_sorted) >= 2:
        wave_height_str = '+'.join(str(w) for w in waves_sorted)
        print(f"  连板高度：{wave_height_str}板({tc['height_category']})")
    else:
        print(f"  连板高度：{tc['board_height']}板({tc['height_category']})")
    print(f"  波次：{tc['wave_category']}（{tc['wave_count']}波，各波涨停数：{[w['zt_count'] for w in tc['waves_info']]}）")
    if tc.get('trimmed_pre_waves'):
        trim_info = [f"{t['zt_count']}板(间隔{t['interval_to_next']}天 后{t['next_wave_zt']}板)" for t in tc['trimmed_pre_waves']]
        print(f"  ⚠️ 已剔除前置小波：{', '.join(trim_info)}")
        raw_zts = [w['zt_count'] for w in tc['waves_info_before_trim']]
        print(f"     剔除前各波涨停数：{raw_zts}")
    print(f"  首日状态：{tc['first_day_state']}  启动位置：{tc['pre_rally_category']}")
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
    print(f"  M-cut：{mc[0]['form']}({mc[0]['subdivision_v2']}) → "
          f"{mc[1]['form']}({mc[1]['subdivision_v2']}) → "
          f"{mc[2]['form']}({mc[2]['subdivision_v2']})")
    print(f"  M-start：{ms[0]['form']}({ms[0]['subdivision_v2']}) → "
          f"{ms[1]['form']}({ms[1]['subdivision_v2']}) → "
          f"{ms[2]['form']}({ms[2]['subdivision_v2']})")
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
        search_end='20260601',
        top_n=50,
        output_excel=True
    )
