# -*- coding: utf-8 -*-
"""主入口：需求挖掘 -> 翻译 -> GitHub 搜索 -> 商店查重(看供给) -> AI 分析 -> 报告。

需求信号来源（按优先级）：
1. 百度联想词扩展的长尾需求（主）—— 用户持续在搜的解决方案
2. 百度热搜 + Google Trends（辅）—— 趋势参考
"""
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import demand_miner
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

    # 1. 需求挖掘（主）：百度联想词扩展长尾需求
    demands = demand_miner.mine()  # [(需求词, 来源种子词)]

    # 2. 热搜趋势（辅）
    hot = keyword_collector.collect()  # {"baidu":[...], "google":[...]}

    # 翻译：需求词（多已是中文，英文词翻译）+ 热搜词
    demand_words = [w for w, _ in demands]
    demand_translated = keyword_translator.translate_keywords(demand_words)
    hot_translated = {
        "baidu": keyword_translator.translate_keywords(hot["baidu"]),
        "google": keyword_translator.translate_keywords(hot["google"]),
    }
    print("[main] 翻译完成")

    # 3. GitHub 搜索：用需求词 + 热搜词合并搜索
    # 需求词太长（如「发票怎么开」）需提取核心词用于 GitHub 搜索
    search_words = _extract_search_terms(demand_words) + keyword_collector.all_keywords(hot)
    repos = github_searcher.search(search_words)
    if not repos:
        print("[main] 未获取到仓库，终止")
        return False
    analyzed = repo_analyzer.analyze(repos)

    # 4. AI 代码分析
    ai_results = {}
    if config.ENABLE_AI_ANALYSIS:
        topn = [r for r in analyzed if r["score"] >= config.MIN_REPORT_SCORE][:config.AI_CODE_ANALYZE_TOPN]
        print("[main] 对前 %d 个候选做 AI 代码分析 ..." % len(topn))
        for r in topn:
            res = ai_analyzer.deep_analyze(r)
            if res:
                ai_results[r["name"]] = res

    # 5. 报告
    report = report_generator.generate(
        date_str,
        {"demands": demand_translated, "hot": hot_translated},
        analyzed, ai_results, demands=demands)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, date_str + ".md")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print("[main] 报告已写入: %s" % out_path)
    return True


def _extract_search_terms(demand_words):
    """从需求词提取适合 GitHub 搜索的核心词。
    需求词多为「XX软件/XX工具/XX怎么XX」，提取主语部分。"""
    import re
    out = []
    for w in demand_words:
        # 去掉疑问/动作后缀，保留主语
        w = re.sub(r"(怎么|如何|为什么|怎么办|软件|工具|app|应用|下载|的|了|呢|吗).*$", "", w, flags=re.IGNORECASE)
        w = w.strip()
        if len(w) >= 2:
            out.append(w)
    return out


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
