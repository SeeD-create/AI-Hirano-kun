import os

# LINE Messaging API
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# Google Gemini
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = "gemini-3-flash-preview"

# アプリケーション設定
LINE_REPLY_MAX_LENGTH = 5000
CONVERSATION_HISTORY_MAX_TURNS = 10
CONVERSATION_HISTORY_TTL = 3600  # 秒 (1時間)
MAX_USERS_IN_MEMORY = 1000

# 画像出力設定
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_OUTPUT_DIR = os.path.join(_BASE_DIR, "generated_images")
FONT_DIR = os.path.join(_BASE_DIR, "fonts")
FONT_PATH = os.path.join(FONT_DIR, "NotoSansJP-Regular.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "NotoSansJP-Bold.ttf")
BASE_URL = os.environ.get("BASE_URL", "https://ai-hirano-kun.onrender.com")
IMAGE_CLEANUP_TTL = 300  # 秒 (5分)
