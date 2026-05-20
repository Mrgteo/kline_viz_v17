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
    spec.loader.exec_module(mod)
    return mod


APP = _load_app_module()
CONFIG = APP.CONFIG


def list_cached_stocks(start_date: str, end_date: str) -> list[str]:
    """扫描缓存目录，列出已缓存的股票代码（区间一致才计入）。"""
    cache_dir = CONFIG.get("cache_dir", "./stock_cache/")
    if not os.path.isabs(cache_dir):
        cache_dir = str((_APP_PATH.parent / cache_dir).resolve())
    if not os.path.isdir(cache_dir):
        return []
    pat = re.compile(rf"^daily_(\d{{6}})_{re.escape(start_date)}_{re.escape(end_date)}\.pkl$")
    codes = []
    for fn in os.listdir(cache_dir):
        m = pat.match(fn)
        if m:
            codes.append(m.group(1))
    return sorted(set(codes))


def load_stock_list():
    return APP.get_main_board_stock_list()


def load_daily_data(stock_list, start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
    return APP.batch_download_daily_data(stock_list, start_date, end_date)


def download_daily_data_with_progress(stock_list, start_date: str, end_date: str,
                                      progress_cb=None) -> dict:
    """逐只下载并通过 progress_cb(done, total, code, status) 回调进度。
    status: 'cache' / 'ok' / 'fail'
    """
    import os
    import time
    all_data = {}
    total = len(stock_list)
    success = failed = from_cache = 0
    cache_dir = CONFIG.get("cache_dir", "./stock_cache/")
    for i, row in stock_list.iterrows():
        code = row["code"]
        cf = os.path.join(cache_dir, f"daily_{code}_{start_date}_{end_date}.pkl")
        cached = os.path.exists(cf)
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
