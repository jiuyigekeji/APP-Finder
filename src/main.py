# -*- coding: utf-8 -*-
"""主入口：采集 -> 翻译 -> 搜索 -> 分析 -> 商店查重 -> AI 代码分析 -> 生成报告 -> 写盘。"""
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import keyword_collector
import keyword_translator
import github_searcher
import repo_analyzer
import ai_analyzer
import report_generator

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE, "reports")


def run():
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    print("=== APP-Finder 运行 %s ===" % date_str)

    grouped = keyword_collector.collect()
    # 分别翻译两个来源
    translated = {
        "baidu": keyword_translator.translate_keywords(grouped["baidu"]),
        "google": keyword_translator.translate_keywords(grouped["google"]),
    }
    print("[main] 关键词翻译完成")

    # GitHub 搜索用合并去重词
    all_kw = keyword_collector.all_keywords(grouped)
    repos = github_searcher.search(all_kw)
    if not repos:
        print("[main] 未获取到仓库，终止")
        return False
    analyzed = repo_analyzer.analyze(repos)

    ai_results = {}
    if config.ENABLE_AI_ANALYSIS:
        topn = [r for r in analyzed if r["score"] >= config.MIN_REPORT_SCORE][:config.AI_CODE_ANALYZE_TOPN]
        print("[main] 对前 %d 个候选做 AI 代码分析 ..." % len(topn))
        for r in topn:
            res = ai_analyzer.deep_analyze(r)
            if res:
                ai_results[r["name"]] = res

    report = report_generator.generate(date_str, translated, analyzed, ai_results)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, date_str + ".md")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print("[main] 报告已写入: %s" % out_path)
    return True


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
