# ─── CẤU HÌNH BOT ────────────────────────────────────────────────────────────
# Đọc từ environment variables (an toàn cho deployment)
# Nếu chạy local, tạo file .env rồi dùng python-dotenv

import os
import json

# ─── Load .env file nếu có (chỉ dùng khi dev local) ──────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv không bắt buộc trên production

# ─── Đọc config từ environment variables ──────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ─── Validate ────────────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN chưa được cấu hình!\n"
        "  • Local: tạo file .env với BOT_TOKEN=xxx\n"
        "  • Fly.io: fly secrets set BOT_TOKEN=xxx"
    )
