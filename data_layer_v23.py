"""
数据接入层 v2.3：包装 app1.py（K线相似度匹配 v2.3 连板版）。

设计目标：与 data_layer.py 接口完全同形（同名同参数），
让 viz_app.py 仅通过侧边栏切换 `_dl_v17` / `_dl_v23` 即可，
不破坏 v1.7 已有调用路径。

差异点：
- v2.3 案例没有"断板期 / D1 / D2 / D3"概念；
  find_segments_and_breaks 返回 (rows, seq_start, [(seq_start, seq_end)], None)。
- v2.3 没有 precompute_stock_data；本模块在此基于
  identify_zt_days + classify_special_board 自行拼出 list[dict]。
- 过滤流程为 pre_filter → hard_filter → conditional_filter → final_score → distance；
  print 日志结构兼容 data_layer.py 的 _FILTER_LINE_RE 正则。
"""
from __future__ import annotations

import io
import os
import re
import sys
import contextlib
import importlib.util
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_APP_PATH = _HERE / "app1.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("matcher_app_v23", str(_APP_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["matcher_app_v23"] = mod
    spec.loader.exec_module(mod)
    return mod


APP = _load_app_module()
CONFIG = APP.CONFIG


# ============== 缓存扫描 ==============
def list_cached_stocks(start_date: str, end_date: str) -> list[str]:
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


# ============== 股票列表 / 日 K ==============
def load_stock_list():
    return APP.get_main_board_stock_list()


def load_daily_data(stock_list, start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
    return APP.batch_download_daily_data(stock_list, start_date, end_date)


def download_daily_data_with_progress(stock_list, start_date: str, end_date: str,
                                      progress_cb=None) -> dict:
    """逐只下载并通过 progress_cb 回调进度（同 data_layer.py 行为）。"""
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


# ============== 案例库 ==============
def load_case_library(all_daily_data, stock_info_df):
    return APP.build_all_cases(all_daily_data, stock_info_df)


# ============== K 线行 / 标的 ==============
def _df_to_rows(daily_df: pd.DataFrame) -> list[dict]:
    """把 identify_zt_days 后的 DataFrame 转成 list[dict]，含 form 字段。
    form 对涨停日 = classify_special_board 结果；其他日为空。
    """
    rows: list[dict] = []
    n = len(daily_df)
    for i in range(n):
        r = daily_df.iloc[i]
        form = ""
        if bool(r.get("is_zt", False)):
            try:
                form = APP.classify_special_board(daily_df, i)
            except Exception:
                form = ""
        rows.append({
            "date": pd.Timestamp(r["date"]),
            "open": float(r["open"]),
            "close": float(r["close"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "volume": float(r["volume"]),
            "is_zt": bool(r.get("is_zt", False)),
            "form": form,
        })
    return rows


def precompute_rows(stock_code: str, all_daily_data: dict) -> list[dict]:
    if stock_code not in all_daily_data:
        return []
    daily_df = APP.identify_zt_days(all_daily_data[stock_code].copy())
    return _df_to_rows(daily_df)


def build_target(stock_code: str, cut_date_str: str, all_daily_data, stock_info_df):
    return APP.build_target_case(stock_code, cut_date_str, all_daily_data, stock_info_df)


# ============== 日志解析（与 data_layer.py 同款正则） ==============
_FILTER_LINE_RE = re.compile(
    r"^\s*(?P<label>[^\uff1a:]+)[\uff1a:]\s*(?P<count>\d+)(?:\s*[\uff08(]-?(?P<penalty>\d+)[\uff09)])?"
)


def parse_filter_log(text: str) -> list[dict]:
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


# ============== 匹配 ==============
def match(stock_code: str, cut_date_str: str, all_daily_data, stock_info_df,
          case_library, top_n: int | None = None) -> dict:
    """执行 v2.3 匹配流程，返回与 data_layer.match 同形 dict。"""
    if top_n is None:
        top_n = CONFIG["top_n"]

    target_case = build_target(stock_code, cut_date_str, all_daily_data, stock_info_df)
    target_rows = precompute_rows(stock_code, all_daily_data)

    buf = io.StringIO()
    cands: list = []
    cp: dict = {"board_strength": 0}
    scored: list = []
    ranked: list = []
    with contextlib.redirect_stdout(buf):
        cands = APP.pre_filter(target_case, case_library)
        if cands:
            cands = APP.hard_filter(target_case, cands)
        if cands:
            cands, cp = APP.conditional_filter(target_case, cands)
        if cands:
            scored = APP.calculate_final_score(target_case, cands, cp)
        if scored:
            ranked = APP.apply_distance_and_final_score(target_case, scored)
    filter_log = parse_filter_log(buf.getvalue())

    ranked_top = ranked[:top_n] if top_n else ranked
    return {
        "target_case": target_case,
        "ranked": ranked_top,
        "ranked_full": ranked,
        "filter_log": filter_log,
        "a_penalty": 0,
        "target_rows": target_rows,
    }


def get_candidate_rows(case: dict, all_daily_data: dict) -> list[dict]:
    return precompute_rows(case["stock_code"], all_daily_data)


def find_segments_and_breaks(stock_code: str, cut_date_str: str, all_daily_data):
    """v2.3 没有断板期；找到包含 cut_idx 的连续涨停段，返回
    (rows, seq_start, [(seq_start, seq_end)], None)。
    若 cut_idx 不在任何涨停段内，返回 (rows, None, None, None)。
    """
    rows = precompute_rows(stock_code, all_daily_data)
    if not rows:
        return rows, None, None, None
    cut_ts = pd.Timestamp(cut_date_str)
    cut_idx = next((i for i, r in enumerate(rows) if r["date"] == cut_ts), None)
    if cut_idx is None or not rows[cut_idx]["is_zt"]:
        return rows, None, None, None
    seq_start = cut_idx
    while seq_start > 0 and rows[seq_start - 1]["is_zt"]:
        seq_start -= 1
    seq_end = cut_idx
    while seq_end < len(rows) - 1 and rows[seq_end + 1]["is_zt"]:
        seq_end += 1
    return rows, seq_start, [(seq_start, seq_end)], None
