from __future__ import annotations

import os
import pickle
import time
from multiprocessing import freeze_support
from pathlib import Path

import pandas as pd

import app as APP


PROJECT_DIR = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_DIR / "stock_cache"
TARGET_CACHE = CACHE_DIR / "case_library_break_v22.pkl"
OLD_CACHE = CACHE_DIR / "case_library_break_v21.pkl"


def load_name_map() -> dict[str, str]:
    if not OLD_CACHE.exists():
        return {}
    print(f"读取旧案例库名称映射: {OLD_CACHE}", flush=True)
    try:
        with OLD_CACHE.open("rb") as f:
            cases = pickle.load(f)
    except Exception as exc:
        print(f"旧案例库读取失败，名称将使用未知: {exc}", flush=True)
        return {}

    name_map: dict[str, str] = {}
    for case in cases:
        code = str(case.get("stock_code", "")).zfill(6)
        name = str(case.get("stock_name", "")).strip()
        if code and name:
            name_map[code] = name
    print(f"名称映射完成: {len(name_map)} 只", flush=True)
    return name_map


def load_cached_daily_data() -> dict[str, pd.DataFrame]:
    files = sorted(CACHE_DIR.glob("daily_*.pkl"))
    print(f"发现日线缓存文件: {len(files)} 个", flush=True)

    all_daily_data: dict[str, pd.DataFrame] = {}
    for idx, path in enumerate(files, 1):
        code = path.stem.replace("daily_", "").zfill(6)
        try:
            with path.open("rb") as f:
                df = pickle.load(f)
            if df is None or len(df) < 3:
                continue
            if "date" in df.columns:
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df[(df["date"] >= "2023-01-01") & (df["date"] <= "2026-06-01")]
            if len(df) >= 3:
                all_daily_data[code] = df
        except Exception as exc:
            print(f"跳过 {code}: {exc}", flush=True)

        if idx % 500 == 0 or idx == len(files):
            print(f"  已加载 {idx}/{len(files)} | 可用 {len(all_daily_data)}", flush=True)

    return all_daily_data


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    workers = max(1, min((os.cpu_count() or 2) - 1, 12))
    APP.CONFIG["cache_dir"] = str(CACHE_DIR)
    APP.CONFIG["case_library_cache"] = str(TARGET_CACHE)
    APP.CONFIG["worker_count"] = workers

    if TARGET_CACHE.exists():
        backup = TARGET_CACHE.with_suffix(f".bak_{time.strftime('%Y%m%d_%H%M%S')}.pkl")
        TARGET_CACHE.replace(backup)
        print(f"已备份旧 v22 案例库: {backup}", flush=True)

    name_map = load_name_map()
    all_daily_data = load_cached_daily_data()
    stock_info_df = pd.DataFrame(
        {
            "code": list(all_daily_data.keys()),
            "name": [name_map.get(code, "未知") for code in all_daily_data.keys()],
        }
    )

    print(
        f"开始生成 {TARGET_CACHE.name}: 股票 {len(all_daily_data)} 只，进程 {workers}",
        flush=True,
    )
    cases = APP.build_all_break_cases(all_daily_data, stock_info_df)

    if not TARGET_CACHE.exists():
        raise RuntimeError(f"生成失败: 未找到 {TARGET_CACHE}")

    with TARGET_CACHE.open("rb") as f:
        saved_cases = pickle.load(f)
    size_mb = TARGET_CACHE.stat().st_size / 1024 / 1024
    print(
        f"生成完成: {TARGET_CACHE} | 内存案例 {len(cases)} | 文件案例 {len(saved_cases)} | {size_mb:.1f} MB",
        flush=True,
    )


if __name__ == "__main__":
    freeze_support()
    main()
