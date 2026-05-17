"""
Quản lý thống kê quiz — lưu kết quả, leaderboard, tracking người chơi.
Dữ liệu lưu vào file JSON cục bộ.
"""
import json
import os
import time
from datetime import datetime
from collections import defaultdict

STATS_FILE = os.path.join(os.path.dirname(__file__), "quiz_stats.json")


def _load_stats() -> dict:
    """Load stats từ file JSON."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"users": {}, "questions": []}
    return {"users": {}, "questions": []}


def _save_stats(data: dict):
    """Lưu stats vào file JSON."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


def record_answer(user_id: int, username: str, correct: bool, response_time: float, question_type: str):
    """
    Ghi lại kết quả trả lời của 1 user.
    
    Args:
        user_id: Telegram user ID
        username: Tên hiển thị
        correct: Đúng hay sai
        response_time: Thời gian trả lời (giây)
        question_type: Loại câu hỏi (word_to_def, def_to_word, fill_blank, phonetic_to_word)
    """
    stats = _load_stats()
    uid = str(user_id)

    if uid not in stats["users"]:
        stats["users"][uid] = {
            "name": username,
            "total": 0,
            "correct": 0,
            "streak": 0,
            "best_streak": 0,
            "total_time": 0.0,
            "fastest": None,
            "by_type": {}
        }

    user = stats["users"][uid]
    user["name"] = username  # Update name in case it changed
    user["total"] += 1
    user["total_time"] += response_time

    if correct:
        user["correct"] += 1
        user["streak"] += 1
        if user["streak"] > user["best_streak"]:
            user["best_streak"] = user["streak"]
        if user["fastest"] is None or response_time < user["fastest"]:
            user["fastest"] = round(response_time, 1)
    else:
        user["streak"] = 0

    # Track by question type
    if question_type not in user["by_type"]:
        user["by_type"][question_type] = {"total": 0, "correct": 0}
    user["by_type"][question_type]["total"] += 1
    if correct:
        user["by_type"][question_type]["correct"] += 1

    # Lưu log câu hỏi (giới hạn 500 entries gần nhất)
    stats["questions"].append({
        "user_id": uid,
        "username": username,
        "correct": correct,
        "time": round(response_time, 1),
        "type": question_type,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    if len(stats["questions"]) > 500:
        stats["questions"] = stats["questions"][-500:]

    _save_stats(stats)


def get_leaderboard(top_n: int = 10) -> list[dict]:
    """
    Lấy bảng xếp hạng top N người chơi.
    Xếp theo: accuracy → total correct → fastest time.
    """
    stats = _load_stats()
    users = []
    for uid, data in stats["users"].items():
        if data["total"] == 0:
            continue
        accuracy = data["correct"] / data["total"] * 100
        avg_time = data["total_time"] / data["total"] if data["total"] > 0 else 0
        users.append({
            "user_id": uid,
            "name": data["name"],
            "total": data["total"],
            "correct": data["correct"],
            "accuracy": round(accuracy, 1),
            "avg_time": round(avg_time, 1),
            "fastest": data.get("fastest"),
            "streak": data.get("best_streak", 0),
            "current_streak": data.get("streak", 0)
        })

    # Sort: accuracy desc → correct desc → avg_time asc
    users.sort(key=lambda x: (-x["accuracy"], -x["correct"], x["avg_time"]))
    return users[:top_n]


def get_user_stats(user_id: int) -> dict | None:
    """Lấy thống kê cá nhân."""
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats["users"]:
        return None

    data = stats["users"][uid]
    if data["total"] == 0:
        return None

    accuracy = data["correct"] / data["total"] * 100
    avg_time = data["total_time"] / data["total"]

    return {
        "name": data["name"],
        "total": data["total"],
        "correct": data["correct"],
        "accuracy": round(accuracy, 1),
        "avg_time": round(avg_time, 1),
        "fastest": data.get("fastest"),
        "best_streak": data.get("best_streak", 0),
        "current_streak": data.get("streak", 0),
        "by_type": data.get("by_type", {})
    }


def reset_stats():
    """Reset toàn bộ thống kê."""
    _save_stats({"users": {}, "questions": []})
