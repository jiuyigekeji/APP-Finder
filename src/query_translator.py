# -*- coding: utf-8 -*-
"""需求词 → GitHub 英文搜索词 映射。

GitHub 是英文社区，用中文需求词（如「录音转换成文字」）直接搜命中率极低。
本模块把中文需求意图映射到英文技术搜索词：
  「录音转换成文字」→ speech to text / ASR / audio transcription
  「pdf转换成word」  → pdf to word converter / document converter

对于非中文需求词（英文/日文等），先翻译成中文意图再映射，保证跨语言一致。
"""
import re

import config
import keyword_translator

# 需求意图正则 → 英文 GitHub 搜索词（按优先级，命中即用）
# 每个 value 是 [英文词1, 英文词2]，用于多次搜索提高召回
DEMAND_QUERY_MAP = [
    # 文档转换
    (r"pdf.*word|word.*pdf", ["pdf to word converter", "document converter"]),
    (r"pdf.*excel|excel.*pdf", ["pdf to excel", "table extraction pdf"]),
    (r"pdf.*图片|图片.*pdf", ["pdf to image", "image to pdf"]),
    (r"pdf.*压缩", ["pdf compressor", "compress pdf"]),
    (r"pdf.*编辑|编辑.*pdf", ["pdf editor", "edit pdf"]),
    (r"pdf.*识别|ocr", ["pdf ocr", "ocr"]),
    # 语音/音频
    (r"录音.*文字|语音.*文字|语音转文|录音转文|音频转文", ["speech to text", "audio transcription", "ASR"]),
    (r"文字.*语音|语音合成|朗读|配音|tts", ["text to speech", "TTS", "voice clone"]),
    (r"语音.*翻译|实时翻译|同声传译", ["realtime translation", "speech translation"]),
    (r"录音|音频.*下载", ["audio recorder", "audio download"]),
    (r"音乐.*下载|歌曲.*下载", ["music downloader", "audio download"]),
    # 图像/视频
    (r"图片.*文字|图片.*识别|截图.*文字|文字.*识别", ["ocr image to text", "text recognition"]),
    (r"图片.*生成|ai.*画图|画图.*ai|头像.*生成", ["image generation", "stable diffusion", "ai avatar"]),
    (r"图片.*压缩", ["image compressor", "compress image"]),
    (r"图片.*去背|抠图|去水印|去背景", ["background remover", "watermark remover"]),
    (r"视频.*下载|下载.*视频", ["video downloader", "youtube downloader"]),
    (r"视频.*字幕|字幕.*生成|加字幕", ["subtitle generator", "auto subtitle"]),
    (r"视频.*压缩", ["video compressor", "compress video"]),
    (r"截图", ["screenshot tool", "screenshot annotation"]),
    # PPT/办公
    (r"ppt.*生成|ppt.*制作|一键.*ppt|幻灯片.*生成", ["ppt generator", "slide generation", "pptx generator"]),
    (r"ppt.*模板", ["ppt template", "slides template"]),
    (r"markdown.*微信|md.*微信|公众号.*排版", ["markdown to wechat", "wechat formatter"]),
    # 查询类
    (r"成绩.*查询|查询.*成绩", ["score query", "result checker"]),
    (r"发票.*查询|发票.*真伪", ["invoice verifier", "invoice ocr"]),
    (r"社保.*查询", ["social security query"]),
    (r"快递.*查询|物流.*查询", ["express tracking", "logistics tracking"]),
    # 学习/教育
    (r"背单词|单词.*记忆", ["vocabulary", "flashcard", "spaced repetition"]),
    (r"错题", ["wrong answer book", "exam review"]),
    (r"公式.*计算|计算.*公式", ["formula calculator", "math engine"]),
    # 健康/生活
    (r"喝水.*提醒|喝水.*记录", ["water reminder", "hydration tracker"]),
    (r"冥想|正念", ["meditation", "mindfulness"]),
    (r"睡眠.*记录|睡眠.*分析", ["sleep tracker", "sleep analysis"]),
    (r"健身.*计划|运动.*记录", ["workout tracker", "fitness log"]),
    (r"减肥.*方法|减肥.*计划", ["weight loss", "calorie tracker"]),
    # 笔记/效率
    (r"笔记.*软件|记笔记|日记.*软件|写日记", ["note taking", "markdown notes", "journal app"]),
    (r"番茄钟|专注.*计时", ["pomodoro", "focus timer"]),
    (r"习惯.*打卡|习惯.*养成", ["habit tracker"]),
    # 文件/工具
    (r"文件.*管理|文件.*清理", ["file manager", "disk cleaner"]),
    (r"文件.*恢复|恢复.*文件", ["file recovery", "data recovery"]),
    (r"二维码.*生成|二维码.*识别", ["qr code generator", "qr scanner"]),
]


def _to_chinese(word):
    """非中文词先翻译成中文，统一走中文意图映射。"""
    if re.search(r"[\u4e00-\u9fa5]", word):
        return word
    zh = keyword_translator.translate(word)
    return zh if zh and zh != word else word


def translate_to_github_query(demand_word):
    """把需求词映射为英文 GitHub 搜索词列表。

    返回 [英文词...]；无匹配时回退到：翻译成英文后用原词。
    """
    zh = _to_chinese(demand_word)
    for pattern, queries in DEMAND_QUERY_MAP:
        if re.search(pattern, zh, re.IGNORECASE):
            return queries
    # 无匹配：若是英文直接用，否则翻译成英文
    if re.fullmatch(r"[\x00-\x7f]+", demand_word):
        return [demand_word]
    en = keyword_translator.translate(demand_word)
    # translate 返回的是中文翻译，这里我们需要英文，反过来用原词或翻译
    return [demand_word] if not en else [demand_word]


def build_search_terms(demand_words):
    """批量转换。返回 [(github英文词, 原始需求词)] 用于搜索与追溯。"""
    out = []
    seen = set()
    for w in demand_words:
        for gq in translate_to_github_query(w):
            if gq.lower() not in seen:
                seen.add(gq.lower())
                out.append((gq, w))
    return out


if __name__ == "__main__":
    tests = ["pdf转换成word", "录音转换成文字", "英语四级成绩查询", "ppt一键生成", "喝水提醒"]
    for t in tests:
        print(t, "->", translate_to_github_query(t))
