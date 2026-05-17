import logging
from datetime import time, date
from telegram.ext import Application
from sheets import SheetsManager
from config import GROUP_CHAT_ID

logger = logging.getLogger(__name__)

def setup_daily_reminder(app: Application, sheets: SheetsManager):
    """
    Gửi 5 từ ngẫu nhiên vào group mỗi ngày lúc 11:00 sáng (giờ VN = UTC+7).
    JobQueue dùng UTC nên set lúc 4:00 UTC = 11:00 GMT+7.
    """
    job_queue = app.job_queue

    job_queue.run_daily(
        callback=send_daily_words,
        time=time(hour=4, minute=0),   # 4:00 UTC = 11:00 VN
        data={"sheets": sheets},
        name="daily_vocab"
    )
    logger.info("Daily reminder scheduled at 11:00 VN time.")

async def send_daily_words(context):
    sheets: SheetsManager = context.job.data["sheets"]
    words = sheets.get_random_words(5)

    if not words:
        return

    today = date.today().strftime("%d/%m/%Y")
    lines = [
        f"*TỪ VỰNG HÔM NAY — {today}*",
    ]

    for i, row in enumerate(words, 1):
        word       = row.get("word", "")
        phonetic   = row.get("phonetic", "")
        definition = row.get("definition", "_(chưa có nghĩa)_")
        example    = row.get("example", "")
        topic      = row.get("topic", "")

        phonetic_str = f" `/{phonetic}/`" if phonetic else ""
        topic_str    = f" \\[{topic}\\]" if topic else ""

        lines.append(f"{i}. *{word}*{phonetic_str}{topic_str}")
        lines.append(f"   📖 _{definition}_")
        if example:
            lines.append(f"   💬 _{example}_")
        lines.append("")

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text="\n".join(lines),
        parse_mode="Markdown"
    )

