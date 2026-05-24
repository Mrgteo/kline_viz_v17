"""离线预构建断板版 v2.0 案例库（case_library_break_v20.pkl）。

为什么需要：
- viz_app.py 首次执行匹配时会触发 build_all_break_cases。
- 该函数走 multiprocessing.Pool。在 Streamlit 进程下，Windows spawn 子进程
  无法还原动态加载的 matcher_app_v17 模块，会导致 Pool.map 永远卡住，
  前端表现就是「执行匹配...」转圈不返回。
- 单独以 `python prebuild_case_library.py` 在普通终端运行时，主模块是
  __main__/app，子进程可正常 spawn，多进程能正常完成。
- 构建完成后会生成 stock_cache/case_library_break_v20.pkl，
  之后 viz_app 启动时直接命中缓存，秒级返回。
"""
from __future__ import annotations

import time

import app as APP


def main():
    print("=== 预构建断板 v2.0 案例库 ===")
    t0 = time.time()
    si = APP.get_main_board_stock_list()
    print(f"主板股票列表: {len(si)} 只")

    cfg = APP.CONFIG
    # 用项目默认区间；如需调整可改 viz_app 侧边栏后再重跑此脚本
    start_date = "20230101"
    end_date = "20260519"
    print(f"加载日 K（区间 {start_date} ~ {end_date}）...")
    ad = APP.batch_download_daily_data(si, start_date, end_date)
    print(f"日 K 加载完成: {len(ad)} 只 / {time.time() - t0:.1f}s")

    print("构建案例库...")
    cases = APP.build_all_break_cases(ad, si)
    print(f"完成: {len(cases)} 个案例 / 总耗时 {time.time() - t0:.1f}s")
    print(f"已写入: {cfg.get('case_library_cache')}")


if __name__ == "__main__":
    main()
