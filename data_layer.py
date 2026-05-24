"""
数据接入层：包装 app.py，复用已有 akshare 缓存与算法函数。
- 通过 importlib 动态加载同级目录的 app.py，避免与 klinesm/app.py 冲突
- 捕获 hard_filter_with_downgrade 的 print 日志为结构化数据
- 不写 Excel、不输出 stdout，只返回 dict 给前端
"""
from __future__ import annotations

import io
import os
import re
import sys
import contextlib
import importlib.util
from pathlib import Path
from typing import Any

import pandas as pd

_HERE = Path(__file__).resolve().parent
_APP_PATH = _HERE / "app.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("matcher_app_v17", str(_APP_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["matcher_app_v17"] = mod
    # 同时以真实模块名 "app" 注册，便于多进程 spawn 子进程能 pickle 还原其内的函数。
    # Windows + Streamlit 下，子进程 import 的是这个名字。
    sys.modules["app"] = mod
    spec.loader.exec_module(mod)
    return mod


APP = _load_app_module()
CONFIG = APP.CONFIG
# Windows + Streamlit 下 multiprocessing.Pool 会因子进程无法 import 动态加载的
# matcher_app_v17 模块而死锁；强制单进程构建案例库以保证可用性。
CONFIG["worker_count"] = 1

# Streamlit 启动 CWD 未必是项目目录，必须把相对路径转成绝对路径，
# 否则 ./stock_cache/case_library_break_v20.pkl 找不到 → 触发全量重建 → 卡死。
def _abs(p: str) -> str:
    if not p:
        return p
    return p if os.path.isabs(p) else str((_APP_PATH.parent / p).resolve())

CONFIG["cache_dir"] = _abs(CONFIG.get("cache_dir", "./stock_cache/"))
if CONFIG.get("case_library_cache"):
    CONFIG["case_library_cache"] = _abs(CONFIG["case_library_cache"])
# app.py 在 import 时已用相对路径调过 makedirs，这里补一次绝对路径的 makedirs
os.makedirs(CONFIG["cache_dir"], exist_ok=True)


def list_cached_stocks(start_date: str, end_date: str) -> list[str]:
    """扫描缓存目录，列出已缓存的股票代码。
    新算法 (app.py v2.0+) 用 daily_{code}.pkl；为兼容旧文件名亦扫描 daily_{code}_{start}_{end}.pkl。
    """
    cache_dir = CONFIG.get("cache_dir", "./stock_cache/")
    if not os.path.isabs(cache_dir):
        cache_dir = str((_APP_PATH.parent / cache_dir).resolve())
    if not os.path.isdir(cache_dir):
        return []
    pat_new = re.compile(r"^daily_(\d{6})\.pkl$")
    pat_old = re.compile(rf"^daily_(\d{{6}})_{re.escape(start_date)}_{re.escape(end_date)}\.pkl$")
    codes = []
    for fn in os.listdir(cache_dir):
        m = pat_new.match(fn) or pat_old.match(fn)
        if m:
            codes.append(m.group(1))
    return sorted(set(codes))


def load_stock_list():
    return APP.get_main_board_stock_list()


def load_daily_data(stock_list, start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
    """纯缓存快路：直接读 daily_{code}.pkl 切片返回，绝不触发 akshare 增量下载。
    完整刷新由侧边栏「下载数据」按钮 → download_daily_data_with_progress 负责。
    """
    import pickle as _pkl
    cache_dir = CONFIG["cache_dir"]
    start_ts = pd.to_datetime(start_date, format="%Y%m%d")
    end_ts = pd.to_datetime(end_date, format="%Y%m%d")
    out: dict[str, pd.DataFrame] = {}
    for _, row in stock_list.iterrows():
        code = row["code"]
        fp = os.path.join(cache_dir, f"daily_{code}.pkl")
        if not os.path.exists(fp):
            continue
        try:
            with open(fp, "rb") as f:
                df = _pkl.load(f)
            if df is None or len(df) == 0:
                continue
            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
            sliced = df[mask].reset_index(drop=True)
            if len(sliced) > 0:
                out[code] = sliced
        except Exception:
            continue
    return out


def download_daily_data_with_progress(stock_list, start_date: str, end_date: str,
                                      progress_cb=None) -> dict:
    """逐只下载并通过 progress_cb(done, total, code, status) 回调进度。
    status: 'cache' / 'ok' / 'fail'
    """
    import os
    import time
    # 新算法 (app.py v2.0+) 使用 daily_{code}.pkl，首次运行需迁移旧版区间命名缓存
    if hasattr(APP, "_migrate_old_cache"):
        try:
            APP._migrate_old_cache()
        except Exception:
            pass
    all_data = {}
    total = len(stock_list)
    success = failed = from_cache = 0
    cache_dir = CONFIG.get("cache_dir", "./stock_cache/")
    for i, row in stock_list.iterrows():
        code = row["code"]
        # 新算法 (app.py v2.0+) 用 daily_{code}.pkl；旧版同步兼容
        cf_new = os.path.join(cache_dir, f"daily_{code}.pkl")
        cf_old = os.path.join(cache_dir, f"daily_{code}_{start_date}_{end_date}.pkl")
        cached = os.path.exists(cf_new) or os.path.exists(cf_old)
        df = APP.get_daily_data(code, start_date, end_date,
                                max_retries=CONFIG["max_retries"])
        status = "fail"
        if df is not None and len(df) > 0:
            all_data[code] = df
            success += 1
            if cached:
                from_cache += 1
                status = "cache"
            else:
                status = "ok"
        else:
            failed += 1
        if progress_cb is not None:
            progress_cb(i + 1, total, code, status,
                        success=success, failed=failed, from_cache=from_cache)
        if not cached:
            time.sleep(CONFIG["request_interval"])
    return {"data": all_data, "success": success, "failed": failed,
            "from_cache": from_cache, "total": total}


def load_case_library(all_daily_data, stock_info_df):
    return APP.build_all_break_cases(all_daily_data, stock_info_df)


def precompute_rows(stock_code: str, all_daily_data: dict) -> list[dict]:
    if stock_code not in all_daily_data:
        return []
    return APP.precompute_stock_data(all_daily_data[stock_code].copy())


def build_target(stock_code: str, cut_date_str: str, all_daily_data, stock_info_df):
    """构造标的断板案例。"""
    return APP.build_target_break_case(stock_code, cut_date_str, all_daily_data, stock_info_df)


_FILTER_LINE_RE = re.compile(
    r"^\s*(?P<label>[^\uff1a:]+)[\uff1a:]\s*(?P<count>\d+)(?:\s*[\uff08(]-?(?P<penalty>\d+)[\uff09)])?"
)


def parse_filter_log(text: str) -> list[dict]:
    """解析 hard_filter_with_downgrade 的 print 日志为结构化条目。
    支持中英文标点。每一行如：
      "  回撤比(未回撤)：1234"
      "  距D1降1档([1天, 2~3天])：800（-20）"
    """
    steps = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _FILTER_LINE_RE.match(line)
        if not m:
            continue
        label = m.group("label").strip()
        count = int(m.group("count"))
        penalty = int(m.group("penalty")) if m.group("penalty") else 0
        steps.append({"label": label, "count": count, "penalty": penalty, "raw": line})
    return steps


def match(stock_code: str, cut_date_str: str, all_daily_data, stock_info_df,
          case_library, top_n: int | None = None) -> dict:
    """执行完整匹配流程，返回结构化结果。
    返回:
      {
        target_case: dict,
        ranked: list[dict],          # 已含 final_score / penalty_details
        filter_log: list[dict],      # 硬过滤每步剩余数 + 扣分
        a_penalty: int,
        target_rows: list[dict],     # 标的 K 线明细（用于绘图）
      }
    """
    if top_n is None:
        top_n = CONFIG["top_n"]

    target_case = build_target(stock_code, cut_date_str, all_daily_data, stock_info_df)
    target_rows = precompute_rows(stock_code, all_daily_data)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cands, a_penalty = APP.hard_filter_with_downgrade(target_case, case_library)
    filter_log = parse_filter_log(buf.getvalue())

    scored = APP.calc_final_score(target_case, cands, a_penalty) if cands else []
    ranked = APP.apply_distance_score(target_case, scored) if scored else []

    return {
        "target_case": target_case,
        "ranked": ranked[:top_n] if top_n else ranked,
        "ranked_full": ranked,
        "filter_log": filter_log,
        "a_penalty": a_penalty,
        "target_rows": target_rows,
    }


def get_candidate_rows(case: dict, all_daily_data: dict) -> list[dict]:
    """根据 case 取出该股票从 seq_start 到 cut_date 附近的 rows。"""
    code = case["stock_code"]
    if code not in all_daily_data:
        return []
    rows = APP.precompute_stock_data(all_daily_data[code].copy())
    return rows


def get_mcut_compare_payload(target_case: dict, cand_case: dict) -> dict:
    """为前端渲染 M-cut 3 天窗口对比标注做数据准备。
    返回 {target: [...3天], cand: [...3天], total_penalty, total_bonus}。
    每天 dict: {label, day_offset, t_sub, c_sub, t_emo, c_emo,
               t_form, c_form, color, badge_text, day_score, day_diff_kind}
    color: 'match' / 'approx' / 'emotion' / 'mismatch' / 'none'
    """
    if not target_case or not cand_case:
        return {"target": [], "cand": [], "total_penalty": 0, "total_bonus": 0}
    tm = target_case.get("m_cut") or []
    cm = cand_case.get("m_cut") or []
    if len(tm) < 3 or len(cm) < 3:
        return {"target": [], "cand": [], "total_penalty": 0, "total_bonus": 0}

    scope = target_case.get("research_scope", "标准")
    decay = APP.get_d1_decay(target_case.get("cut_to_d1_days", 0))
    base = APP.CONFIG["micro_mismatch_penalty"]

    labels = ["前2天", "前1天", "切面日"]
    out_t, out_c = [], []
    total_p = total_b = 0
    for i, label in enumerate(labels):
        day_offset = 2 - i
        w = APP.get_mcut_weight(scope, day_offset)
        ts, cs = tm[i]["subdivision"], cm[i]["subdivision"]
        te, ce = tm[i]["emotion"], cm[i]["emotion"]
        tf, cf = tm[i].get("form", ""), cm[i].get("form", "")

        if ts == "无" and cs == "无":
            kind, color = "none", "#94a3b8"
            day_score = round(APP.CONFIG["micro_both_none_bonus"] * decay * w)
            badge = f"双方无 +{day_score}"
            total_b += day_score
            day_score_signed = day_score
        elif ts == "无" or cs == "无":
            kind, color = "missing", "#fb923c"
            v = round(base * 0.3 * w)
            badge = f"一方无 -{v}"
            total_p += v
            day_score_signed = -v
        elif APP.match_subdivision(ts, cs):
            kind, color = "match", "#10b981"
            v = round(APP.CONFIG["micro_exact_bonus"] * w)
            badge = f"精确匹配 +{v}"
            total_b += v
            day_score_signed = v
        elif APP.match_approx(ts, cs):
            kind, color = "approx", "#3b82f6"
            v = round(APP.CONFIG["micro_approx_penalty"] * w)
            badge = f"近似 -{v}"
            total_p += v
            day_score_signed = -v
        elif APP.match_emotion(te, ce):
            kind, color = "emotion", "#a78bfa"
            v = round(APP.CONFIG["micro_emotion_penalty"] * w)
            badge = f"情绪同 -{v}"
            total_p += v
            day_score_signed = -v
        else:
            kind, color = "mismatch", "#ef4444"
            v = round(APP.CONFIG["micro_mismatch_penalty"] * w)
            badge = f"不匹配 -{v}"
            total_p += v
            day_score_signed = -v

        out_t.append({
            "label": label, "day_offset": day_offset,
            "form": tf, "subdivision": ts, "emotion": te,
            "color": color, "diff_kind": kind,
            "badge_text": badge, "day_score": day_score_signed, "weight": w,
        })
        out_c.append({
            "label": label, "day_offset": day_offset,
            "form": cf, "subdivision": cs, "emotion": ce,
            "color": color, "diff_kind": kind,
            "badge_text": badge, "day_score": day_score_signed, "weight": w,
        })

    return {"target": out_t, "cand": out_c,
            "total_penalty": total_p, "total_bonus": total_b}


def find_segments_and_breaks(stock_code: str, cut_date_str: str, all_daily_data):
    """重新跑 find_break_sequences 拿到 segments / break_periods，用于绘图标注。"""
    rows = precompute_rows(stock_code, all_daily_data)
    cut_date = pd.to_datetime(cut_date_str)
    cut_idx = next((i for i, r in enumerate(rows) if pd.Timestamp(r["date"]) == cut_date), None)
    if cut_idx is None:
        return rows, None, None, None
    for seq in APP.find_break_sequences(rows):
        if seq["seq_start"] <= cut_idx <= seq["seq_end"] and cut_idx >= seq["break_periods"][0][0]:
            return rows, seq["seq_start"], seq["segments"], seq["break_periods"]
    return rows, None, None, None
