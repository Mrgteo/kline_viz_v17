from __future__ import annotations

import pickle
import shutil
import time
from pathlib import Path

import pandas as pd

import data_layer as dl


PROJECT_DIR = Path(r"C:\Users\KaiPanLa\Desktop\File\Code\kline_viz_v17")
CACHE_DIR = PROJECT_DIR / "stock_cache"
POOL_DIR = CACHE_DIR / "recommend_pool_v22"
CASE_LIBRARY = CACHE_DIR / "case_library_break_v22.pkl"
START_DATE = "20230101"
END_DATE = "20260601"

RECOMMEND_POOL = [
    ("601991", "大唐发电", "2026-05-15", "高位断板反抽"),
    ("002421", "达实智能", "2026-05-28", "高位断板反抽"),
    ("002918", "蒙娜丽莎", "2026-05-20", "高位断板A杀"),
    ("601991", "大唐发电", "2026-05-20", "高位异动大跌"),
    ("002081", "金螳螂", "2026-05-18", "人气股多波"),
    ("002342", "巨力索具", "2026-01-19", "中位断板止跌"),
    ("002342", "巨力索具", "2026-01-21", "中位断板反抽"),
    ("600439", "瑞贝卡", "2024-10-31", "低位断板反包"),
    ("002114", "罗平", "2025-12-01", "低位断板反抽"),
    ("000066", "中国长城", "2026-05-11", "低位断板止跌"),
]


def reset_pool_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if POOL_DIR.exists():
        if not str(POOL_DIR.resolve()).lower().startswith(str(CACHE_DIR.resolve()).lower()):
            raise RuntimeError(f"Refuse to delete outside cache dir: {POOL_DIR}")
        shutil.rmtree(POOL_DIR)
    POOL_DIR.mkdir(parents=True, exist_ok=True)


def load_daily_cache() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    start_ts = pd.to_datetime(START_DATE, format="%Y%m%d")
    end_ts = pd.to_datetime(END_DATE, format="%Y%m%d")
    name_map = {code: name for code, name, _date, _label in RECOMMEND_POOL}
    all_daily_data: dict[str, pd.DataFrame] = {}

    files = sorted(CACHE_DIR.glob("daily_*.pkl"))
    print(f"发现日线缓存: {len(files)} 个", flush=True)
    for idx, path in enumerate(files, 1):
        code = path.stem.replace("daily_", "").zfill(6)
        try:
            with path.open("rb") as f:
                df = pickle.load(f)
            if df is None or len(df) == 0 or "date" not in df.columns:
                continue
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].reset_index(drop=True)
            if len(df) >= 3:
                all_daily_data[code] = df
        except Exception as exc:
            print(f"跳过 {code}: {exc}", flush=True)
        if idx % 500 == 0 or idx == len(files):
            print(f"  已加载 {idx}/{len(files)} | 可用 {len(all_daily_data)}", flush=True)

    stock_info = pd.DataFrame(
        {
            "code": list(all_daily_data.keys()),
            "name": [name_map.get(code, "未知") for code in all_daily_data.keys()],
        }
    )
    return all_daily_data, stock_info


def main() -> None:
    if not CASE_LIBRARY.exists():
        raise FileNotFoundError(f"缺少案例库: {CASE_LIBRARY}")

    dl.CONFIG["cache_dir"] = str(CACHE_DIR)
    dl.APP.CONFIG["cache_dir"] = str(CACHE_DIR)
    dl.CONFIG["case_library_cache"] = str(CASE_LIBRARY)
    dl.APP.CONFIG["case_library_cache"] = str(CASE_LIBRARY)

    reset_pool_dir()
    all_daily_data, stock_info = load_daily_cache()
    print(f"加载 v22 案例库: {CASE_LIBRARY}", flush=True)
    case_library = dl.load_case_library(all_daily_data, stock_info)
    print(f"案例库案例数: {len(case_library)}", flush=True)

    ok = failed = 0
    t0 = time.time()
    for idx, (code, name, cut_date, label) in enumerate(RECOMMEND_POOL, 1):
        out_path = POOL_DIR / f"{code}_{cut_date}.pkl"
        try:
            print(
                f"[{idx:02d}/{len(RECOMMEND_POOL)}] 生成 {label}: {code} {name} {cut_date}",
                flush=True,
            )
            result = dl.match(code, cut_date, all_daily_data, stock_info, case_library, top_n=None)
            with out_path.open("wb") as f:
                pickle.dump(result, f)
            full_count = len(result.get("ranked_full") or [])
            print(f"  OK -> {out_path.name} | ranked_full={full_count}", flush=True)
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"  FAIL {code} {cut_date}: {exc}", flush=True)

    print(f"推荐池 v22 生成完成: 成功 {ok} / 失败 {failed} | {time.time() - t0:.1f}s", flush=True)
    if failed:
        raise RuntimeError(f"推荐池存在失败项: {failed}")


if __name__ == "__main__":
    main()
