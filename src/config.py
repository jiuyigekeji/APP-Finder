"""配置文件：关键词来源、过滤阈值、评分权重等。"""
import os

BAIDU_HOT_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss"

SEED_KEYWORDS = [
    "AI agent", "LLM", "RAG", "voice clone", "image generation", "realtime translation",
    "short video", "productivity", "notes", "expense tracker", "habit tracker", "pomodoro",
    "fitness", "meditation", "learning", "vocabulary", "ebook", "podcast",
]

MAX_KEYWORDS = 12

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MIN_STARS = 50
MAX_STARS = 20000
CREATED_WITHIN_DAYS = 90
PER_KEYWORD_REPOS = 5
MAX_REPOS_TO_ANALYZE = 20

APP_FRIENDLY_LANGUAGES = {
    "Python", "JavaScript", "TypeScript", "Kotlin", "Swift",
    "Dart", "Java", "Go", "Rust",
}
APP_FRIENDLY_TOPICS = {
    "ai", "llm", "chatbot", "translation", "tts", "stt", "ocr",
    "image-generation", "summary", "rag", "agent", "automation",
    "productivity", "notes", "todo", "fitness", "finance",
}
NON_APP_KEYWORDS = {
    "kubernetes", "docker-compose", "microservice", "etcd",
    "self-hosted server", "saas platform", "infrastructure",
    "database engine", "ci/cd", "load balancer",
}
APP_KEYWORDS = {
    "mobile", "app", "android", "ios", "wechat", "miniprogram", "client",
    "frontend", "ui", "user", "personal", "daily", "reminder",
}

W_STARS = 15
W_LANGUAGE = 20
W_TOPICS = 20
W_APP_README = 25
W_NON_APP_PENALTY = -30
W_FRESHNESS = 10
W_SINGLE_PURPOSE = 15

MIN_REPORT_SCORE = 40

ENABLE_AI_ANALYSIS = os.environ.get("ENABLE_AI_ANALYSIS", "false").lower() == "true"
AI_API_BASE = os.environ.get("AI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-1.5-flash")

# ===== 应用商店查重 =====
APPLE_SEARCH_API = "https://itunes.apple.com/search"
# 各商店无官方免费搜索 API，用 Google 站内搜索间接取证
STORE_SITE_DOMAINS = {
    "google_play": "play.google.com",
    "huawei": "appgallery.huawei.com",
    "xiaomi": "app.mi.com",
    "vivo": "appstore.vivo.com.cn",
}
GOOGLE_SEARCH_URL = "https://www.google.com/search"
STORE_CHECK_TIMEOUT = 10
# 是否对非 Apple 商店启用 Google 站内搜索间接取证（默认关闭：不稳定且慢）
ENABLE_GOOGLE_SITE_SEARCH = os.environ.get("ENABLE_GOOGLE_SITE_SEARCH", "false").lower() == "true"
# 每个候选最多检查多少个商店
MAX_STORES_PER_REPO = 6
# Google 站内搜索时用的查询语言
SEARCH_COUNTRY = "cn"

# APP 分类映射：关键词 -> 商店标准分类
# 参考 Apple App Store / Google Play 主分类
CATEGORY_KEYWORD_MAP = {
    "效率": ["productivity", "notes", "todo", "task", "reminder", "habit", "pomodoro", "calendar"],
    "工具": ["tool", "utility", "converter", "calculator", "scanner", "qr", "file"],
    "社交": ["social", "chat", "community", "forum", "dating", "messaging"],
    "通讯": ["call", "sms", "voip", "walkie", "contact"],
    "教育": ["learning", "education", "course", "flashcard", "vocabulary", "language", "study"],
    "图书": ["ebook", "reader", "book", "novel", "manga"],
    "新闻": ["news", "rss", "feed", "headline"],
    "生活": ["life", "weather", "clock", "alarm", "recipe", "cook", "shopping"],
    "健康健美": ["fitness", "health", "workout", "meditation", "sleep", "diet", "weight"],
    "财务": ["finance", "expense", "budget", "accounting", "money", "bank", "stock", "crypto"],
    "摄影与录像": ["photo", "camera", "video", "filter", "edit", "collage", "selfie"],
    "音乐": ["music", "audio", "lyric", "podcast", "player", "tuner"],
    "娱乐": ["entertainment", "game", "fun", "joke", "meme", "tarot"],
    "医疗": ["medical", "symptom", "medicine", "doctor", "pharmacy"],
    "旅游": ["travel", "map", "navigation", "trip", "hotel", "flight", "transit"],
    "导航": ["gps", "navigation", "compass", "parking"],
    "美食佳饮": ["food", "drink", "restaurant", "recipe", "delivery"],
    "商务": ["business", "crm", "invoice", "contract", "meeting"],
    "图形和设计": ["design", "draw", "sketch", "mockup", "ui", "font"],
    "AI/Chatbot": ["ai", "llm", "chatbot", "gpt", "agent", "rag", "assistant"],
    "图像生成": ["image-generation", "stable-diffusion", "midjourney", "draw ai", "avatar"],
    "语音/翻译": ["translation", "translate", "tts", "stt", "voice", "speech", "subtitle"],
    "开发者工具": ["developer", "devtools", "regex", "json", "api", "ssh", "terminal"],
}
# 商店分类名对应表（Apple -> Google -> 国内商店通用名近似）
CATEGORY_DISPLAY = "推荐分类"

# ===== 关键词翻译 =====
# 优先级：AI API（若启用） -> LibreTranslate 公共实例 -> 原文不翻译
LIBRETRANSLATE_URL = "https://libretranslate.com/translate"
# Google 翻译非官方端点（免费无 key，稳定），作为主翻译源
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
LIBRETRANSLATE_TIMEOUT = 8

# ===== Google Play 查重 =====
# 使用 google-play-scraper（免费无 key）。仓库内核心文件较少时也可直连。
ENABLE_GOOGLE_PLAY = True
GOOGLE_PLAY_TIMEOUT = 12

# ===== 国内商店搜索页抓取 =====
# 各商店搜索 URL 模板，{q} 为 url 编码后的查询词
STORE_SEARCH_URLS = {
    "huawei": "https://so.appgallery.huawei.com/search/{q}",
    "xiaomi": "https://app.mi.com/search/all?keywords={q}",
    "vivo": "https://developer.vivo.com.cn/middleware/searchApp/{q}",
}
STORE_SCRAPE_TIMEOUT = 10
ENABLE_CN_STORE_SCRAPE = True  # 国内商店抓取开关，失败回退为"未知"

# ===== AI 代码分析 =====
# 拉取仓库核心源码文件数与大小上限
AI_REPO_FILES_MAX = 6
AI_REPO_FILE_MAX_CHARS = 4000
AI_CODE_ANALYZE_TOPN = 5  # 对前 N 个候选做 AI 代码分析

# ===== 关键词预筛（GitHub 搜索前过滤，节省配额、提升候选质量）=====
# 命中以下正则的词跳过 GitHub 搜索（多为纯人名/赛事/娱乐，GitHub 无对应仓库）
KEYWORD_SKIP_PATTERNS = [
    r"\s+vs\.?\s+",        # 赛事对阵: "senegal vs iraq", "挪威vs法国"
    r"vs\.?\s+\S+",
    r"获.*奖",              # 获奖新闻: "杨紫获白玉兰奖最佳女主"
    r"最佳(男|女)",         # 最佳男主/女主
    r"出生|逝世|去世|身亡",  # 人物生死
    r"结婚|离婚|出轨|分手",  # 娱乐八卦
    r"预告|官宣|定档|开播",  # 影视宣发
    r"^[A-Z][a-z]+ [A-Z][a-z]+$",  # 纯英文人名: "Tom Dundon"
    r"cricket|football|soccer|nba|world cup",  # 体育
]
# 种子科技词：当有效词不足时，补充这些词保证候选数量
TECH_SEED_KEYWORDS = [
    "AI agent", "LLM", "RAG", "chatbot", "TTS", "OCR",
    "笔记", "记账", "番茄钟", "习惯打卡", "冥想", "背单词",
    "语音转文字", "图像生成", "实时翻译", "电子书", "播客",
]

# ===== 需求挖掘（替代热搜作为主需求来源）=====
# 百度搜索联想词接口：输入种子词，返回用户真实在搜的长尾需求
BAIDU_SUGGEST_URL = "https://suggestion.baidu.com/su?action=opensearch&ie=UTF-8&wd={kw}"
# 领域种子词：覆盖常青需求领域，从中扩展长尾需求
DEMAND_SEED_DOMAINS = [
    # 效率/工具
    "手机", "电脑", "文件", "图片", "视频", "PDF", "截图", "扫描", "录音", "翻译",
    # 健康/生活
    "健身", "减肥", "睡眠", "记账", "日记", "喝水", "冥想",
    # 学习/教育
    "背单词", "英语", "公式", "考试", "笔记", "错题",
    # 财务/办公
    "发票", "报销", "合同", "工资", "社保",
    # AI/创作
    "AI", "写作", "配音", "画图", "PPT",
]
# 每个种子词取多少个联想词
SUGGEST_PER_SEED = 10
# 需求挖掘最多取多少个种子词（控制请求量）
MAX_DEMAND_SEEDS = 15
# 联想词长度过滤：太短通常是泛词，太长通常是具体事件
DEMAND_MIN_LEN = 4
DEMAND_MAX_LEN = 25
# 供给缺口判定：商店同类数 <= 此值视为「供给不足」（洼地信号）
LOW_SUPPLY_THRESHOLD = 3

# ===== 红海品类排除 =====
# 这些品类需求大但已饱和，不再适合小团队做 APP
# 命中关键词（需求词/仓库描述/topics）或分类（商店返回）即排除
RED_OCEAN_KEYWORDS = [
    "记账", "账本", "记帐", "理财账本", "家庭账本",
    "计算器", "科学计算器", "全能计算器", "高级计算器",
    "日历", "天气", "时钟", "闹钟",
    "手电筒", "二维码", "扫描识别",
    "清理", "杀毒", "加速", "省电",
    "输入法", "壁纸", "主题", "桌面",
    "音乐播放器", "视频播放器", "文件管理器",
    "便签", "备忘录",
]
# 商店分类命中即排除（与 CATEGORY_KEYWORD_MAP 的分类名一致）
RED_OCEAN_CATEGORIES = [
    "财务",  # 记账类多归此
    # 注：计算器多归「工具」，过于宽泛，不整体排除工具类，改用关键词排除
]
