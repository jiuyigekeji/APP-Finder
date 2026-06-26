"""主入口：采集 -> 搜索 -> 分析 -> 生成报告 -> 写盘。"""
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import keyword_collector
import github_searcher
import repo_analyzer
import ai_analyzer
import report_generator

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE, "reports")


def run():
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    print("=== Android APP Finder 运行 %s ===" % date_str)

    keywords = keyword_collector.collect()
    repos = github_searcher.search(keywords)
    if not repos:
        print("[main] 未获取到仓库，终止")
        return False
    analyzed = repo_analyzer.analyze(repos)

    ai_results = {}
    if config.ENABLE_AI_ANALYSIS:
        for r in analyzed[:5]:
            res = ai_analyzer.deep_analyze(r)
            if res:
                ai_results[r["name"]] = res

    report = report_generator.generate(date_str, keywords, analyzed, ai_results)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, date_str + ".md")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print("[main] 报告已写入: %s" % out_path)
    return True


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
