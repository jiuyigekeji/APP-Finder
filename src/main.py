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
import blue_ocean_miner
import app_store_checker
import query_translator
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

    # 0. 蓝海挖掘：HN 用户主动表达的未满足需求（AI 抽取）
    blue_demands = blue_ocean_miner.mine()
    # 对蓝海需求做商店查重（海外用英文，国内用中文）+ AI 二次判断
    import keyword_translator
    for bd in blue_demands[:6]:
        en_sq = bd.get("search_query", "")
        if not en_sq:
            continue
        # 翻译成中文供国内商店查重
        zh_sq = keyword_translator.translate(en_sq) or en_sq
        try:
            bd["store_check"] = app_store_checker.check_dual(en_sq, zh_sq)
            print("[main] 蓝海查重 en='%s' zh='%s' -> 同类 %d 个" % (en_sq[:20], zh_sq[:20], bd["store_check"].get("total_similar", 0)))
        except Exception as e:
            print("[main] 蓝海查重失败: %s" % e)
        # AI 二次判断：看到现有 APP 后判断是否真满足细分需求
        if bd.get("store_check"):
            is_bo, reason = blue_ocean_miner.judge_blue_ocean(bd, bd["store_check"])
            bd["is_blue_ocean"] = is_bo
            bd["judge_reason"] = reason
    # 蓝海判定：AI 二次判断 is_blue_ocean=true 优先
    blue_gaps = [bd for bd in blue_demands if bd.get("is_blue_ocean") is True]
    if not blue_gaps:
        blue_gaps = [bd for bd in blue_demands
                     if bd.get("store_check", {}).get("total_similar", 99) <= config.LOW_SUPPLY_THRESHOLD]
    print("[main] 蓝海需求 %d 条，AI 判定蓝海 %d 条" % (len(blue_demands), len(blue_gaps)))

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

    # 3. GitHub 搜索：需求词经 query_translator 映射为英文技术词
    #    （github_searcher 会记录每个仓库命中的英文词，报告里追溯到原始需求词）
    demand_terms = query_translator.build_search_terms(demand_words)  # [(英文词, 原始需求词)]
    hot_terms = keyword_collector.all_keywords(hot)
    # search 接受 [(query, origin)] 或 [query]，origin 用于追溯
    search_input = [(gq, origin) for gq, origin in demand_terms] + [(w, w) for w in hot_terms]
    repos = github_searcher.search(search_input)
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
            else:
                print("[main] AI 分析 '%s' 未返回结果" % r["name"])

    # 5. 报告
    report = report_generator.generate(
        date_str,
        {"demands": demand_translated, "hot": hot_translated},
        analyzed, ai_results, demands=demands, blue_gaps=blue_gaps)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    # 文件名精确到分钟，永不覆盖
    ts = datetime.now(tz).strftime("%Y-%m-%d-%H%M")
    out_path = os.path.join(REPORTS_DIR, ts + ".md")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print("[main] 报告已写入: %s" % out_path)
    return True


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
