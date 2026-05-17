import os
import pickle
import base64
import json
import logging
import urllib.request
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from datetime import datetime

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _update_fly_secret(creds: Credentials) -> None:
    """
    Cập nhật GOOGLE_TOKEN_PICKLE_B64 trên Fly.io khi refresh token thay đổi.
    Yêu cầu 2 env var: FLY_API_TOKEN và FLY_APP_NAME.
    """
    fly_token = os.environ.get("FLY_API_TOKEN")
    fly_app = os.environ.get("FLY_APP_NAME")
    if not fly_token or not fly_app:
        logger.warning("Refresh token đã thay đổi nhưng thiếu FLY_API_TOKEN hoặc FLY_APP_NAME — không thể tự cập nhật secret.")
        return

    new_b64 = base64.b64encode(pickle.dumps(creds)).decode()

    # Cập nhật in-memory để process hiện tại dùng luôn
    os.environ["GOOGLE_TOKEN_PICKLE_B64"] = new_b64

    query = """
    mutation($input: SetSecretsInput!) {
      setSecrets(input: $input) {
        release { id }
      }
    }
    """
    payload = json.dumps({
        "query": query,
        "variables": {
            "input": {
                "appId": fly_app,
                "secrets": [{"key": "GOOGLE_TOKEN_PICKLE_B64", "value": new_b64}]
            }
        }
    }).encode()

    req = urllib.request.Request(
        "https://api.fly.io/graphql",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {fly_token}"
        }
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info("Đã cập nhật GOOGLE_TOKEN_PICKLE_B64 lên Fly.io thành công.")
    except Exception as e:
        logger.error("Không thể cập nhật Fly.io secret: %s", e)


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
            old_refresh_token = creds.refresh_token
            try:
                creds.refresh(Request())
            except RefreshError as e:
                raise RuntimeError(
                    f"Google refresh token hết hạn hoặc bị thu hồi: {e}\n"
                    "Cần lấy token mới:\n"
                    "  1. Chạy local: python generate_token.py\n"
                    "  2. Lấy base64: python -c \"import pickle,base64; print(base64.b64encode(open('token.pickle','rb').read()).decode())\"\n"
                    "  3. Cập nhật Fly.io: fly secrets set GOOGLE_TOKEN_PICKLE_B64=<giá trị trên>"
                ) from e

            if token_b64:
                # Nếu refresh token thay đổi (Google rotate), cập nhật Fly.io secret
                if creds.refresh_token != old_refresh_token:
                    logger.info("Refresh token đã được Google rotate, đang cập nhật Fly.io secret...")
                    _update_fly_secret(creds)
            else:
                # Local: lưu lại file
                if os.path.exists("token.pickle"):
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