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
import blue_ocean_hypothesizer
import report_generator

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE, "reports")


def run():
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    print("=== APP-Finder 运行 %s ===" % date_str)

    # 0. 需求驱动蓝海：HN/Reddit 用户主动表达的未满足需求（AI 抽取）
    blue_demands = blue_ocean_miner.mine()
    # 对蓝海需求做商店查重（多 search_query 交叉验证）+ AI 二次判断
    import keyword_translator
    for bd in blue_demands[:6]:
        # 兼容：AI 现在返回 search_queries(列表)，旧格式返回 search_query(单字符串)
        queries = bd.get("search_queries") or [bd.get("search_query", "")]
        queries = [q for q in queries if q]
        if not queries:
            continue
        # 多查询交叉查重：每个查询词都查，取中位数同类数（避免宽词误判红海/窄词误判蓝海）
        checks = []
        for en_sq in queries[:3]:  # 最多3个词
            zh_sq = keyword_translator.translate(en_sq) or en_sq
            try:
                sc = app_store_checker.check_dual(en_sq, zh_sq)
                checks.append(sc)
                print("[main] 蓝海查重 en='%s' -> 同类 %d 个" % (en_sq[:24], sc.get("total_similar", 0)))
            except Exception as e:
                print("[main] 蓝海查重失败: %s" % e)
        if checks:
            # 取中位数同类数（综合各查询词，避免单词偏差）
            totals = sorted(sc.get("total_similar", 0) for sc in checks)
            mid = totals[len(totals) // 2]
            bd["store_check"] = checks[0]  # 用第一个的详情展示
            bd["store_check"]["total_similar"] = mid  # 但同类数用中位数
            bd["store_check"]["_all_queries"] = [q for q in queries[:3]]
            # AI 二次判断
            is_bo, reason = blue_ocean_miner.judge_blue_ocean(bd, bd["store_check"])
            bd["is_blue_ocean"] = is_bo
            bd["judge_reason"] = reason
    # 蓝海判定：AI 二次判断 is_blue_ocean=true 优先
    blue_gaps = [bd for bd in blue_demands if bd.get("is_blue_ocean") is True]
    if not blue_gaps:
        blue_gaps = [bd for bd in blue_demands
                     if bd.get("store_check", {}).get("total_similar", 99) <= config.LOW_SUPPLY_THRESHOLD]
    print("[main] 需求驱动蓝海 %d 条，判定蓝海 %d 条" % (len(blue_demands), len(blue_gaps)))

    # 0B. 供给驱动蓝海：GitHub 近期高 star 新项目（非APP形态）= 需求被代码验证但未APP化
    supply_blue = []
    try:
        rising = github_searcher.fetch_rising_repos(max_results=15)
        non_app = [r for r in rising if github_searcher.is_non_app_form(r)]
        print("[main] 供给驱动：rising %d 个，非APP形态 %d 个" % (len(rising), len(non_app)))
        def _verify_supply(r):
            en_q = app_store_checker._build_query(r)
            zh_q = keyword_translator.translate(en_q) or en_q
            sc = app_store_checker.check_dual(en_q, zh_q)
            r["store_check"] = sc
            r["need"] = r.get("desc", "")[:80]
            r["audience"] = "GitHub 项目用户"
            r["why_gap"] = "该项目为 %s 形态，普通用户无法直接使用" % r.get("language", "代码")
            is_bo, reason = blue_ocean_miner.judge_blue_ocean(r, sc, force_ai=True)
            return r, is_bo, reason, sc.get("total_similar", 99)

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            for r, is_bo, reason, total in ex.map(_verify_supply, non_app[:6]):
                print("[main] 供给查重 '%s' -> 名义同类 %d 个" % (r["name"][:30], total))
                if is_bo:
                    r["is_blue_ocean"] = True
                    r["judge_reason"] = reason
                    supply_blue.append(r)
                    print("[main] 供给 '%s' AI判定蓝海" % r["name"][:24])
    except Exception as e:
        print("[main] 供给驱动蓝海失败: %s" % e)
    print("[main] 供给驱动蓝海候选 %d 条" % len(supply_blue))

    # 0C. 蓝海假设：AI 推理小众人群痛点 + 百度联想验证需求 + 商店查重验证供给
    #     不依赖 GitHub 仓库，不依赖被封社区；需求真实(有人在搜) + 供给不足(同类少) = 蓝海
    hypo_blue = []
    try:
        hypo_demands = blue_ocean_hypothesizer.mine(max_audiences=8)
        print("[main] 蓝海假设：需求验证通过 %d 条，开始供给验证 ..." % len(hypo_demands))

        def _verify_one(hd):
            """单个假设的供给验证：check_dual + force_ai 判断。返回 (hd, is_bo, reason, total)。"""
            zh_q = hd.get("store_query", "") or hd.get("search_verify_word", "") or hd.get("need", "")[:20]
            en_q = keyword_translator.translate(zh_q) or zh_q
            sc = app_store_checker.check_dual(en_q, zh_q)
            hd["store_check"] = sc
            total = sc.get("total_similar", 99)
            is_bo, reason = blue_ocean_miner.judge_blue_ocean(hd, sc, force_ai=True)
            return hd, is_bo, reason, total, zh_q

        # 并行供给验证（check_dual + judge_blue_ocean 都是网络调用，并行大幅加速）
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            for hd, is_bo, reason, total, zh_q in ex.map(_verify_one, hypo_demands[:10]):
                print("[main] 假设查重 '%s' -> 名义同类 %d 个" % (zh_q[:20], total))
                if is_bo:
                    hd["is_blue_ocean"] = True
                    hd["judge_reason"] = reason
                    hypo_blue.append(hd)
                    print("[main] 假设 '%s' 同类%d但AI判定蓝海" % (zh_q[:16], total))
                else:
                    print("[main] 假设 '%s' AI判定红海: %s" % (zh_q[:16], reason[:50]))
    except Exception as e:
        print("[main] 蓝海假设失败: %s" % e)
    print("[main] 蓝海假设验证通过 %d 条" % len(hypo_blue))

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
    demand_terms = query_translator.build_search_terms(demand_words)  # [(英文词, 原始需求词)]
    hot_terms = keyword_collector.all_keywords(hot)
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

    # 4.5 跨查询推广 APP 回扫
    all_checks = ([bd.get("store_check") for bd in blue_gaps if bd.get("store_check")]
                  + [r.get("store_check") for r in supply_blue if r.get("store_check")]
                  + [r.get("store_check") for r in analyzed if r.get("store_check")])
    removed_promos = app_store_checker.finalize_promotion_filter(all_checks)
    if removed_promos:
        print("[main] 过滤付费推广 APP %d 个: %s" % (len(removed_promos), ", ".join(removed_promos[:10])))

    # 5. 报告
    report = report_generator.generate(
        date_str,
        {"demands": demand_translated, "hot": hot_translated},
        analyzed, ai_results, demands=demands, blue_gaps=blue_gaps, supply_blue=supply_blue, hypo_blue=hypo_blue)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now(tz).strftime("%Y-%m-%d-%H%M")
    out_path = os.path.join(REPORTS_DIR, ts + ".md")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print("[main] 报告已写入: %s" % out_path)
    return True

if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
