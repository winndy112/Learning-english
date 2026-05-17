"""
Chạy OAuth flow để lấy Google token mới.
Dùng khi GOOGLE_TOKEN_PICKLE_B64 trên Fly.io hết hạn.

Usage:
    python generate_token.py
"""
import os
import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

if not os.path.exists("credentials.json"):
    print("Lỗi: Không tìm thấy credentials.json")
    print("Tải về tại: Google Cloud Console → APIs & Services → Credentials → Download OAuth client")
    exit(1)

print("Đang mở trình duyệt để đăng nhập Google...")
flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.pickle", "wb") as f:
    pickle.dump(creds, f)

token_b64 = base64.b64encode(open("token.pickle", "rb").read()).decode()

print("\n✓ Đã lưu token.pickle")
print("\n" + "="*60)
print("Chạy lệnh sau để cập nhật Fly.io:")
print("="*60)
print(f"\nfly secrets set GOOGLE_TOKEN_PICKLE_B64={token_b64}\n")
