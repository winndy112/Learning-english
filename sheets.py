import os
import pickle
import base64
import json
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_credentials():
    """
    Lấy Google credentials theo thứ tự ưu tiên:
    1. GOOGLE_TOKEN_PICKLE_B64 env var (cho Fly.io / cloud)
    2. token.pickle file (cho local dev)
    3. Chạy OAuth flow lần đầu (cho local dev)
    """
    creds = None

    # ── 1. Từ env var (base64-encoded token.pickle) ──────────────────────
    token_b64 = os.environ.get("GOOGLE_TOKEN_PICKLE_B64")
    if token_b64:
        creds = pickle.loads(base64.b64decode(token_b64))

    # ── 2. Từ file local ─────────────────────────────────────────────────
    elif os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)

    # ── Refresh nếu hết hạn ──────────────────────────────────────────────
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Lưu lại token đã refresh (chỉ khi dùng file local)
            if not token_b64 and os.path.exists("token.pickle"):
                with open("token.pickle", "wb") as f:
                    pickle.dump(creds, f)

    # ── 3. Chạy OAuth flow lần đầu (chỉ dùng local) ─────────────────────
    if not creds or not creds.valid:
        if os.path.exists("credentials.json"):
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)
        else:
            raise RuntimeError(
                "Không tìm thấy Google credentials!\n"
                "  • Fly.io: fly secrets set GOOGLE_TOKEN_PICKLE_B64=xxx\n"
                "  • Local: đặt file credentials.json vào thư mục project"
            )

    return creds

class SheetsManager:
    def __init__(self, spreadsheet_id: str):
        creds = get_credentials()
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(spreadsheet_id).sheet1
        self._ensure_headers()

    def _ensure_headers(self):
        headers = self.sheet.row_values(1)
        if not headers:
            self.sheet.append_row(["word", "phonetic", "definition", "example", "topic", "added_by", "date"])

    def add_word(self, word, definition, example, phonetic, topic, added_by):
        row = [word, phonetic, definition, example, topic,
               added_by, datetime.now().strftime("%Y-%m-%d %H:%M")]
        self.sheet.append_row(row)

    def update_word(self, word, definition, example, phonetic, topic, added_by):
        col = self.sheet.col_values(1)
        for i, val in enumerate(col):
            if val.lower() == word.lower():
                row_num = i + 1
                self.sheet.update(f'A{row_num}:G{row_num}', [[
                    word, phonetic, definition, example, topic,
                    added_by, datetime.now().strftime("%Y-%m-%d %H:%M")
                ]])
                return
        raise ValueError(f"Word '{word}' not found in sheet")

    def word_exists(self, word):
        col = self.sheet.col_values(1)
        return word.lower() in [w.lower() for w in col]

    def get_all_words(self):
        return self.sheet.get_all_records()

    def get_words_by_topic(self, topic):
        records = self.sheet.get_all_records()
        return [r for r in records if r.get("topic", "").lower() == topic.lower()]

    def get_random_words(self, n=5):
        import random
        records = self.sheet.get_all_records()
        if not records:
            return []
        return random.sample(records, min(n, len(records)))