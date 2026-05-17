import logging
import asyncio
import random
import re
import time
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler, CallbackQueryHandler
)
from telegram.request import HTTPXRequest
from sheets import SheetsManager
from dictionary import lookup_word, find_example_sentence
from scheduler import setup_daily_reminder
from topic_classifier import classify_topic, classify_topic_with_confidence
from quiz_stats import record_answer, get_leaderboard, get_user_stats
from config import BOT_TOKEN, SPREADSHEET_ID, GEMINI_API_KEY
from sentence_checker import init_gemini, check_sentence

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

sheets = SheetsManager(SPREADSHEET_ID)

IELTS_TOPICS = [
    "environment", "technology", "health", "education", "crime",
    "society", "economy", "culture", "science", "media",
    "transport", "food", "travel", "work", "family",
    "government", "communication", "sports", "art", "housing"
]

TOPIC_EMOJIS = {
    "environment": "🌍", "technology": "💻", "health": "🏥", "education": "🎓",
    "crime": "🔒", "society": "👥", "economy": "💰", "culture": "🎭",
    "science": "🔬", "media": "📺", "transport": "🚗", "food": "🍕",
    "travel": "✈️", "work": "💼", "family": "👨‍👩‍👧‍👦", "government": "🏛️",
    "communication": "💬", "sports": "⚽", "art": "🎨", "housing": "🏠",
    "general": "📌"
}

# ─── Conversation states for /addword ────────────────────────────────────────
WORD_INPUT, MEANING_INPUT, PHONETIC_INPUT, EXAMPLE_INPUT, TOPIC_INPUT, OVERWRITE_CONFIRM = range(6)

# ─── Conversation states for /sentence ───────────────────────────────────────
SENTENCE_WAIT = 10
SENTENCE_PICK = 11  # Chọn từ khi có nhiều kết quả khớp

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🎓 *IELTS VOCAB BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Xin chào *{name}*! 👋\n\n"
        "Bot giúp bạn học từ vựng IELTS hiệu quả với các tính năng:\n\n"
        "- Thêm từ mới (tự động tra nghĩa)\n"
        "- Thêm từ thủ công (tùy chỉnh nghĩa, phonetic)\n"
        "- Tra nghĩa từ nhanh\n"
        "- Quản lý theo chủ đề IELTS\n"
        "- Quiz ôn tập từ vựng\n"
        "- Nhắc nhở ôn tập hàng ngày\n\n"
        " => Gõ /help để xem hướng dẫn chi tiết!"
    ).format(name=update.effective_user.first_name or "bạn")
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /help ────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        " *THÊM TỪ MỚI (tự động tra nghĩa): Bot tự tra từ điển và lưu vào cơ sở dữ liệu.*\n"
        "╭─────────────────────────╮\n"
        "│ `/add <từ>`             │\n"
        "│ `/add <từ> <chủ đề>`    │\n"
        "╰─────────────────────────╯\n"
        "  _VD:_ `/add meticulous`\n"
        "  _VD:_ `/add abundant environment`\n\n"
        " *THÊM TỪ THỦ CÔNG (nhập đầy đủ): Bot sẽ hỏi từng bước*\n"
        "╭─────────────────────────╮\n"
        "│ `/addword`              │\n"
        "╰─────────────────────────╯\n"
        "  1️⃣ Nhập từ tiếng Anh\n"
        "  2️⃣ Nhập nghĩa tiếng Việt\n"
        "  3️⃣ Nhập cách đọc (phonetic)\n"
        "  4️⃣ Nhập câu ví dụ\n"
        "  5️⃣ Chọn chủ đề IELTS\n\n"
        " *TRA TỪ (không lưu):*\n"
        "╭─────────────────────────╮\n"
        "│ `/lookup <từ>`          │\n"
        "╰─────────────────────────╯\n"
        "  _VD:_ `/lookup resilient`\n\n"
        " *LIST & SEARCH TỪ VỰNG:*\n"
        "╭───────────────────────────────────╮\n"
        "│ `/list`        — Tất cả từ        │\n"
        "│ `/topic <tên>` — Theo chủ đề      │\n"
        "│ `/topics`      — Danh sách chủ đề │\n"
        "│ `/search <từ>` — Tìm kiếm         │\n"
        "╰───────────────────────────────────╯\n\n"
        "🔹 *ÔN TẬP & QUIZ:*\n"
        "╭──────────────────────────────────────────╮\n"
        "│ `/quiz`          — 1 câu ngẫu nhiên      │\n"
        "│ `/quiz <number>` — Quiz theo số câu      │\n"
        "│ `/sentence`      — Đặt câu (Gemini chấm) │\n"
        "│ `/review`        — 5 từ ôn tập           │\n"
        "╰──────────────────────────────────────────╯\n\n"
        # "  _4 loại câu hỏi: Từ → Nghĩa, Nghĩa → Từ,_\n"
        # "  _Điền từ, Phiên âm→Từ_\n\n"

        "🔹 *THỐNG KÊ & BXH:*\n"
        "╭─────────────────────────────────────╮\n"
        "│ `/leaderboard`   — BXH quiz         │\n"
        "│ `/mystats`       — Stats cá nhân    │\n"
        "│ `/stats`         — Thống kê từ      │\n"
        "│ `/cancel`        — Hủy thao tác     │\n"
        "╰─────────────────────────────────────╯\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 Bot tự động gửi 5 từ ôn tập mỗi ngày lúc *8:00 sáng*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /add (auto lookup) ──────────────────────────────────────────────────────
async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "*HOW TO USE:*\n"
            "• `/add <word>` — Add word (auto lookup)\n"
            "• `/add <word> <topic>` — Add word with topic\n\n"
            "Or use `/addword` to add word manually.",
            parse_mode="Markdown"
        )
        return

    word = context.args[0].lower().strip()
    user_specified_topic = context.args[1].lower().strip() if len(context.args) > 1 else None

    # Validate topic if user specified one
    if user_specified_topic:
        if user_specified_topic not in IELTS_TOPICS and user_specified_topic != "general":
            await update.message.reply_text(
                f"Topic *{user_specified_topic}* is not in the list.\n"
                f"Use `/topics` to see available topics.\n"
                f"Bot will auto-classify the topic.",
                parse_mode="Markdown"
            )
            user_specified_topic = None  # Let auto-classify handle it

    # Check duplicate
    if sheets.word_exists(word):
        await update.message.reply_text(f"*{word}* is already in the list!", parse_mode="Markdown")
        return

    # Lookup
    await update.message.reply_text(f"Looking up *{word}*...", parse_mode="Markdown")
    result = lookup_word(word)

    if not result:
        await update.message.reply_text(
            f"Could not find *{word}* in the dictionary.\n"
            f"Use `/addword` to add it manually!",
            parse_mode="Markdown"
        )
        return

    # Auto-classify topic if not specified
    if user_specified_topic:
        topic = user_specified_topic
        auto_classified = False
    else:
        topic, confidence = classify_topic_with_confidence(word, result.get("definition", ""))
        auto_classified = True

    # Save to sheet
    added_by = update.effective_user.first_name or "Unknown"
    sheets.add_word(word, result["definition"], result["example"], result["phonetic"], topic, added_by)

    # Reply
    phonetic = f" /{result['phonetic']}/" if result.get("phonetic") else ""
    definition = result.get("definition") or "_(no meaning)_"
    example = result.get("example") or "_(no example)_"

    # Topic line with auto-classify indicator
    if auto_classified and topic != "general":
        topic_line = f"*Topic:* {topic} _(auto-classified - {int(confidence*100)}%)_"
    elif auto_classified:
        topic_line = f"*Topic:* general _(default)_"
    else:
        topic_line = f"*Topic:* {topic}"

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  *WORD ADDED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Word:* {word}{phonetic}\n"
        f"*Meaning:* {definition}\n"
        f"*Example:* _{example}_\n"
        f"{topic_line}\n"
        f"*Added by:* {added_by}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /addword (manual, conversation flow) ────────────────────────────────────
async def addword_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start manual word addition flow"""
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  *ADD WORD MANUALLY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "You will enter each field step by step.\n"
        "Type /cancel at any time to abort.\n\n"
        "*Step 1:* Enter the English word:",
        parse_mode="Markdown"
    )
    return WORD_INPUT

async def addword_get_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive English word"""
    word = update.message.text.strip().lower()

    if not word.isalpha() and not " " in word:
        await update.message.reply_text("Please enter a valid English word (letters only):")
        return WORD_INPUT

    # Check duplicate
    if sheets.word_exists(word):
        context.user_data["new_word"] = word
        keyboard = [[
            InlineKeyboardButton("✅ Yes, overwrite", callback_data="overwrite_yes"),
            InlineKeyboardButton("❌ No, keep", callback_data="overwrite_no"),
        ]]
        await update.message.reply_text(
            f"⚠️ *{word}* is already in the list.\n"
            f"Do you want to overwrite it?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return OVERWRITE_CONFIRM

    context.user_data["new_word"] = word

    # Suggest looking up from dictionary
    result = lookup_word(word)
    if result and result.get("definition"):
        context.user_data["lookup_result"] = result
        await update.message.reply_text(
            f"Found in dictionary:\n"
            f"_{result['definition']}_\n\n"
            f"*Step 2:* Enter the meaning.\n"
            f"Type `auto` to use the dictionary meaning above:",
            parse_mode="Markdown"
        )
    else:
        context.user_data["lookup_result"] = None
        await update.message.reply_text(
            f"Word: *{word}*\n\n"
            f"*Step 2:* Enter the meaning:",
            parse_mode="Markdown"
        )
    return MEANING_INPUT

async def addword_get_meaning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive word meaning"""
    text = update.message.text.strip()
    word = context.user_data.get("new_word", "")

    if text.lower() == "auto" and context.user_data.get("lookup_result"):
        meaning = context.user_data["lookup_result"]["definition"]
        context.user_data["new_meaning"] = meaning
        await update.message.reply_text(
            f"Using dictionary meaning.\n\n"
            f"*Step 3:* Enter the phonetic\n"
            f"_e.g.: məˈtɪkjʊləs_\n"
            f"Type `auto` to use dictionary phonetic\n"
            f"Type `skip` to skip:",
            parse_mode="Markdown"
        )
    else:
        context.user_data["new_meaning"] = text
        lookup = context.user_data.get("lookup_result")
        phonetic_hint = ""
        if lookup and lookup.get("phonetic"):
            phonetic_hint = f"\nType `auto` to use: /{lookup['phonetic']}/"

        await update.message.reply_text(
            f"Meaning: _{text}_\n\n"
            f"*Step 3:* Enter the phonetic\n"
            f"_e.g.: məˈtɪkjʊləs_{phonetic_hint}\n"
            f"Type `skip` to skip:",
            parse_mode="Markdown"
        )
    return PHONETIC_INPUT

async def addword_get_phonetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive phonetic"""
    text = update.message.text.strip()

    if text.lower() == "skip":
        context.user_data["new_phonetic"] = ""
    elif text.lower() == "auto" and context.user_data.get("lookup_result"):
        context.user_data["new_phonetic"] = context.user_data["lookup_result"].get("phonetic", "")
    else:
        # Clean up phonetic input - remove surrounding slashes if present
        phonetic = text.strip("/").strip()
        context.user_data["new_phonetic"] = phonetic

    phonetic_display = context.user_data["new_phonetic"]
    if phonetic_display:
        await update.message.reply_text(
            f"Phonetic: /{phonetic_display}/\n\n"
            f"*Step 4:* Enter an example sentence\n"
            f"Type `auto` to fetch an example automatically\n"
            f"Type `skip` to skip:",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"Phonetic skipped.\n\n"
            f"*Step 4:* Enter an example sentence\n"
            f"Type `auto` to fetch an example automatically\n"
            f"Type `skip` to skip:",
            parse_mode="Markdown"
        )
    return EXAMPLE_INPUT

async def addword_get_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive example sentence"""
    text = update.message.text.strip()

    if text.lower() == "skip":
        context.user_data["new_example"] = ""
    elif text.lower() == "auto":
        # Try lookup result first
        example = ""
        if context.user_data.get("lookup_result"):
            example = context.user_data["lookup_result"].get("example", "")
        # If not found, search externally
        if not example:
            word = context.user_data.get("new_word", "")
            await update.message.reply_text(f"Searching for an example for *{word}*...", parse_mode="Markdown")
            example = find_example_sentence(word)
        context.user_data["new_example"] = example
    else:
        context.user_data["new_example"] = text

    # Build topic selection keyboard
    keyboard = []
    row = []
    for i, topic in enumerate(IELTS_TOPICS):
        row.append(InlineKeyboardButton(topic, callback_data=f"topic_{topic}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    # Add "general" option
    keyboard.append([InlineKeyboardButton("general (default)", callback_data="topic_general")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    example_display = context.user_data.get("new_example", "")
    if example_display:
        msg = f"Example: _{example_display}_\n\n"
    else:
        msg = "Example skipped.\n\n"

    await update.message.reply_text(
        msg +
        "*Step 5:* Select an IELTS topic:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return TOPIC_INPUT

async def addword_select_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select topic from inline keyboard"""
    query = update.callback_query
    await query.answer()

    topic = query.data.replace("topic_", "")
    word = context.user_data.get("new_word", "")
    meaning = context.user_data.get("new_meaning", "")
    phonetic = context.user_data.get("new_phonetic", "")
    example = context.user_data.get("new_example", "")
    added_by = query.from_user.first_name or "Unknown"

    # Save to sheet
    if context.user_data.get("overwriting"):
        sheets.update_word(word, meaning, example, phonetic, topic, added_by)
        action = "WORD UPDATED"
    else:
        sheets.add_word(word, meaning, example, phonetic, topic, added_by)
        action = "WORD ADDED"

    # Build confirmation
    phonetic_str = f" /{phonetic}/" if phonetic else ""
    meaning_str = meaning or "_(none)_"
    example_str = f"_{example}_" if example else "_(none)_"

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  *{action}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Word:* {word}{phonetic_str}\n"
        f"*Meaning:* {meaning_str}\n"
        f"*Example:* {example_str}\n"
        f"*Topic:* {topic}\n"
        f"*Added by:* {added_by}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(text, parse_mode="Markdown")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def addword_confirm_overwrite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    word = context.user_data.get("new_word", "")

    if query.data == "overwrite_no":
        await query.edit_message_text(
            "OK, kept the existing entry.\nEnter a different word:",
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return WORD_INPUT

    # overwrite_yes — mark flag and proceed to meaning step
    context.user_data["overwriting"] = True
    result = lookup_word(word)
    if result and result.get("definition"):
        context.user_data["lookup_result"] = result
        await query.edit_message_text(
            f"Overwriting *{word}*.\n\n"
            f"Found in dictionary:\n_{result['definition']}_\n\n"
            f"Enter the new meaning, or type `auto` to use the above:",
            parse_mode="Markdown"
        )
    else:
        context.user_data["lookup_result"] = None
        await query.edit_message_text(
            f"Overwriting *{word}*.\n\nEnter the new meaning:",
            parse_mode="Markdown"
        )
    return MEANING_INPUT


async def addword_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel word addition flow"""
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Use `/addword` to start again.", parse_mode="Markdown")
    return ConversationHandler.END

# ─── /lookup (tra nghĩa nhanh, không lưu) ───────────────────────────────────
async def lookup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ *Cách dùng:* `/lookup <từ>`\n"
            "_VD:_ `/lookup resilient`",
            parse_mode="Markdown"
        )
        return

    word = context.args[0].lower().strip()
    await update.message.reply_text(f"🔍 Đang tra *{word}*...", parse_mode="Markdown")

    result = lookup_word(word)
    if not result:
        await update.message.reply_text(f"❌ Không tìm thấy *{word}* trên từ điển.", parse_mode="Markdown")
        return

    phonetic = f"/{result['phonetic']}/" if result.get("phonetic") else "_(không có)_"
    definition = result.get("definition") or "_(không có)_"
    example = result.get("example") or "_(không có)_"

    # Check if word already saved
    saved = "✅ Đã có trong kho từ" if sheets.word_exists(word) else "💡 Dùng `/add {word}` để lưu vào kho từ"

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🔍 *TRA TỪ: {word.upper()}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔊 *Phiên âm:* {phonetic}\n"
        f"📖 *Nghĩa:* {definition}\n"
        f"💬 *Ví dụ:* _{example}_\n\n"
        f"{saved}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /search ─────────────────────────────────────────────────────────────────
async def search_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ *Cách dùng:* `/search <từ khóa>`\n"
            "_VD:_ `/search envir`",
            parse_mode="Markdown"
        )
        return

    keyword = " ".join(context.args).lower().strip()
    all_words = sheets.get_all_words()
    results = [
        w for w in all_words
        if keyword in w.get("word", "").lower()
        or keyword in w.get("definition", "").lower()
        or keyword in w.get("topic", "").lower()
    ]

    if not results:
        await update.message.reply_text(f"📭 Không tìm thấy kết quả cho *{keyword}*.", parse_mode="Markdown")
        return

    lines = [f"🔎 *Kết quả tìm kiếm: \"{keyword}\"* ({len(results)} từ)\n"]
    for i, row in enumerate(results[:15], 1):
        word = row.get("word", "")
        definition = row.get("definition", "")[:50]
        topic = row.get("topic", "general")
        emoji = TOPIC_EMOJIS.get(topic, "📌")
        lines.append(f"{i}. *{word}* {emoji}[{topic}]\n   _{definition}_\n")

    if len(results) > 15:
        lines.append(f"\n_...và {len(results) - 15} từ khác._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── QUIZ SYSTEM ─────────────────────────────────────────────────────────────
# Lưu câu hỏi quiz trong memory (key = question_id)
_quiz_questions = {}

# Các loại câu hỏi
QUIZ_TYPES = ["word_to_def", "def_to_word", "fill_blank", "phonetic_to_word"]

QUIZ_TYPE_NAMES = {
    "word_to_def": "📖 Từ → Nghĩa",
    "def_to_word": "🔤 Nghĩa → Từ",
    "fill_blank": "✏️ Điền từ",
    "phonetic_to_word": "🔊 Phiên âm → Từ",
    "make_sentence": "✍️ Đặt câu"
}


def _pick_question_type(words: list) -> str:
    """
    Chọn loại câu hỏi ngẫu nhiên dựa trên dữ liệu có sẵn.
    """
    available = ["word_to_def", "def_to_word"]  # Luôn có

    # fill_blank cần ít nhất 1 từ có example
    if any(w.get("example", "") for w in words):
        available.append("fill_blank")

    # phonetic_to_word cần ít nhất 4 từ có phonetic
    words_with_phonetic = [w for w in words if w.get("phonetic", "")]
    if len(words_with_phonetic) >= 4:
        available.append("phonetic_to_word")

    return random.choice(available)


def _build_quiz_question(words: list, used_words: set = None, force_type: str = None) -> dict | None:
    """
    Tạo 1 câu hỏi quiz với loại đa dạng.
    Trả về dict chứa thông tin câu hỏi hoặc None.
    """
    if used_words is None:
        used_words = set()

    words_with_def = [w for w in words if w.get("definition", "") and w.get("word", "") not in used_words]
    all_with_def = [w for w in words if w.get("definition", "")]

    if len(words_with_def) < 1 or len(all_with_def) < 4:
        return None

    # Chọn loại câu hỏi
    q_type = force_type or _pick_question_type(words_with_def)

    # Chọn từ đúng
    if q_type == "fill_blank":
        # Cần từ có example
        candidates = [w for w in words_with_def if w.get("example", "")]
        if not candidates:
            q_type = "word_to_def"  # Fallback
            candidates = words_with_def
        correct = random.choice(candidates)
    elif q_type == "phonetic_to_word":
        # Cần từ có phonetic
        candidates = [w for w in words_with_def if w.get("phonetic", "")]
        if len(candidates) < 1:
            q_type = "word_to_def"  # Fallback
            correct = random.choice(words_with_def)
        else:
            correct = random.choice(candidates)
    else:
        correct = random.choice(words_with_def)

    correct_word = correct.get("word", "")
    correct_def = correct.get("definition", "")
    correct_phonetic = correct.get("phonetic", "")
    correct_example = correct.get("example", "")

    # Chọn 3 đáp án sai
    if q_type == "phonetic_to_word":
        other_pool = [w for w in all_with_def if w.get("word", "") != correct_word and w.get("phonetic", "")]
        if len(other_pool) < 3:
            other_pool = [w for w in all_with_def if w.get("word", "") != correct_word]
    else:
        other_pool = [w for w in all_with_def if w.get("word", "") != correct_word]

    if len(other_pool) < 3:
        return None

    wrong = random.sample(other_pool, 3)

    # Tạo options tùy loại
    if q_type in ("word_to_def",):
        # Câu hỏi: cho từ, chọn nghĩa
        options = [correct] + wrong
        random.shuffle(options)
        correct_idx = next(i for i, o in enumerate(options) if o.get("word") == correct_word)
        question_text = f"Từ *{correct_word}* có nghĩa là gì?"
        option_texts = [o.get("definition", "")[:80] for o in options]

    elif q_type == "def_to_word":
        # Câu hỏi: cho nghĩa, chọn từ
        options = [correct] + wrong
        random.shuffle(options)
        correct_idx = next(i for i, o in enumerate(options) if o.get("word") == correct_word)
        # Cắt ngắn definition nếu quá dài
        display_def = correct_def[:120] + "..." if len(correct_def) > 120 else correct_def
        question_text = f"Nghĩa sau thuộc từ nào?\n\n📖 _{display_def}_"
        option_texts = [o.get("word", "") for o in options]

    elif q_type == "fill_blank":
        # Câu hỏi: điền từ vào chỗ trống
        options = [correct] + wrong
        random.shuffle(options)
        correct_idx = next(i for i, o in enumerate(options) if o.get("word") == correct_word)
        # Tạo câu có chỗ trống
        blank_sentence = re.sub(
            re.escape(correct_word),
            "______",
            correct_example,
            flags=re.IGNORECASE,
            count=1
        )
        if "______" not in blank_sentence:
            # Từ không xuất hiện trong câu ví dụ (dạng biến thể), chuyển sang word_to_def
            q_type = "word_to_def"
            question_text = f"Từ *{correct_word}* có nghĩa là gì?"
            option_texts = [o.get("definition", "")[:80] for o in options]
        else:
            # KHÔNG bọc blank_sentence trong _..._ để tránh xung đột Markdown với ______
            question_text = f"Điền từ vào chỗ trống:\n\n💬 {blank_sentence}"
            option_texts = [o.get("word", "") for o in options]

    elif q_type == "phonetic_to_word":
        # Câu hỏi: cho phiên âm, chọn từ
        options = [correct] + wrong
        random.shuffle(options)
        correct_idx = next(i for i, o in enumerate(options) if o.get("word") == correct_word)
        question_text = f"Phiên âm /{correct_phonetic}/ thuộc từ nào?"
        option_texts = [o.get("word", "") for o in options]

    else:
        return None

    # Tạo question ID ngắn gọn
    qid = uuid.uuid4().hex[:8]

    question_data = {
        "qid": qid,
        "type": q_type,
        "correct_word": correct_word,
        "correct_def": correct_def,
        "correct_example": correct_example,
        "correct_idx": correct_idx,
        "question_text": question_text,
        "option_texts": option_texts,
        "options": options,
        "created_at": time.time(),
        "answered_by": {}  # user_id -> {selected, time, correct}
    }

    # Lưu vào memory
    _quiz_questions[qid] = question_data

    # Cleanup old questions (giữ 100 gần nhất)
    if len(_quiz_questions) > 100:
        oldest = sorted(_quiz_questions.keys(), key=lambda k: _quiz_questions[k]["created_at"])[:50]
        for k in oldest:
            del _quiz_questions[k]

    return question_data


async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = sheets.get_all_words()
    words_with_def = [w for w in words if w.get("definition", "")]

    if len(words_with_def) < 4:
        await update.message.reply_text(
            "📭 Cần ít nhất *4 từ có nghĩa* trong kho để tạo quiz.\n"
            "Dùng `/add` hoặc `/addword` để thêm từ!",
            parse_mode="Markdown"
        )
        return

    # Số câu hỏi
    total_questions = 1
    if context.args:
        try:
            total_questions = int(context.args[0])
            total_questions = max(1, min(total_questions, 20))
        except ValueError:
            await update.message.reply_text(
                "❌ *Cách dùng:*\n"
                "• `/quiz` — 1 câu ngẫu nhiên\n"
                "• `/quiz 5` — 5 câu hỏi\n"
                "• `/quiz 10` — 10 câu (tối đa 20)",
                parse_mode="Markdown"
            )
            return

    total_questions = min(total_questions, len(words_with_def))

    question = _build_quiz_question(words)
    if not question:
        await update.message.reply_text("📭 Không đủ từ để tạo quiz!", parse_mode="Markdown")
        return

    is_group = update.effective_chat.type in ("group", "supergroup")

    session = {
        "total": total_questions,
        "current": 1,
        "score": 0,
        "used_words": {question["correct_word"]},
        "answers": [],
        # group scoreboard: {uid: {"name": str, "points": int, "times": [float]}}
        "group_scores": {}
    }

    # Group dùng chat_data để tất cả members share cùng session
    if is_group:
        context.chat_data["quiz_session"] = session
    else:
        context.user_data["quiz_session"] = session

    await _send_quiz_question(update.message, question, 1, total_questions)


async def _send_quiz_question(target, question: dict, current: int, total: int):
    """
    Gửi 1 câu hỏi quiz.
    Đáp án encode qua question_id trong callback_data.
    """
    labels = ["A", "B", "C", "D"]
    qid = question["qid"]
    q_type = question["type"]
    type_name = QUIZ_TYPE_NAMES.get(q_type, "🧠 Quiz")

    # Build options text
    option_lines = []
    for i, text in enumerate(question["option_texts"]):
        display = text[:80]
        if q_type in ("def_to_word", "fill_blank", "phonetic_to_word"):
            option_lines.append(f"*{labels[i]}.* {display}")
        else:
            option_lines.append(f"*{labels[i]}.* _{display}_")

    # Callback: qz_{qid}_{selected}
    keyboard = []
    row = []
    for i in range(4):
        row.append(InlineKeyboardButton(labels[i], callback_data=f"qz_{qid}_{i}"))
    keyboard.append(row)

    # Header
    if total > 1:
        header = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🧠 *QUIZ* ({current}/{total}) — {type_name}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    else:
        header = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  {type_name}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    msg_text = header + question["question_text"] + "\n\n" + "\n\n".join(option_lines)

    if hasattr(target, 'reply_text'):
        await target.reply_text(msg_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif hasattr(target, 'send_message'):
        await target.send_message(text=msg_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def _build_group_scoreboard(group_scores: dict) -> str:
    """Tạo bảng điểm group từ group_scores dict."""
    if not group_scores:
        return ""
    medals = ["🥇", "🥈", "🥉"]
    sorted_users = sorted(
        group_scores.items(),
        key=lambda x: (-x[1]["points"], sum(x[1]["times"]) / len(x[1]["times"]) if x[1]["times"] else 999)
    )
    lines = []
    for i, (uid, info) in enumerate(sorted_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        pts = info["points"]
        avg_t = round(sum(info["times"]) / len(info["times"]), 1) if info["times"] else 0
        lines.append(f"{medal} *{info['name']}* — {pts} điểm | TB {avg_t}s")
    return "\n".join(lines)


def _rebuild_question_message(question: dict, current: int, total: int) -> str:
    """Tái tạo nội dung message câu hỏi (dùng khi cần edit để thêm danh sách đã trả lời)."""
    labels = ["A", "B", "C", "D"]
    q_type = question["type"]
    type_name = QUIZ_TYPE_NAMES.get(q_type, "🧠 Quiz")

    option_lines = []
    for i, txt in enumerate(question["option_texts"]):
        display = txt[:80]
        if q_type in ("def_to_word", "fill_blank", "phonetic_to_word"):
            option_lines.append(f"*{labels[i]}.* {display}")
        else:
            option_lines.append(f"*{labels[i]}.* _{display}_")

    if total > 1:
        header = f"━━━━━━━━━━━━━━━━━━━━━━━━\n  🧠 *QUIZ* ({current}/{total}) — {type_name}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        header = f"━━━━━━━━━━━━━━━━━━━━━━━━\n  {type_name}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    return header + question["question_text"] + "\n\n" + "\n\n".join(option_lines)


async def _advance_group_quiz(chat_data: dict, message, all_words: list):
    """Chuyển sang câu hỏi tiếp theo trong group quiz."""
    session = chat_data.get("quiz_session")
    if not session:
        return

    current = session["current"]
    total = session["total"]
    used_words = session["used_words"]
    group_scores = session["group_scores"]

    if current >= total:
        # Kết thúc quiz — gửi scoreboard
        scoreboard = _build_group_scoreboard(group_scores)
        answered_count = sum(1 for a in session["answers"] if a.get("any_correct"))
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏆 *KẾT QUẢ QUIZ GROUP*\n"
            f"  {total} câu hỏi\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if scoreboard:
            text += scoreboard
        else:
            text += "_Không ai trả lời đúng câu nào_ 😅"
        text += "\n\nDùng `/quiz 5` để chơi lại!"
        await message.reply_text(text, parse_mode="Markdown")
        chat_data.pop("quiz_session", None)
        return

    # Câu tiếp theo
    next_q = _build_quiz_question(all_words, used_words)
    if not next_q:
        scoreboard = _build_group_scoreboard(group_scores)
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏆 *KẾT QUẢ QUIZ GROUP*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        ) + (scoreboard or "_Không ai trả lời đúng_")
        await message.reply_text(text, parse_mode="Markdown")
        chat_data.pop("quiz_session", None)
        return

    session["current"] += 1
    session["used_words"].add(next_q["correct_word"])
    chat_data["quiz_session"] = session

    await asyncio.sleep(1.5)
    await _send_quiz_question(message, next_q, session["current"], total)


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    username = user.first_name or "Unknown"

    # Parse: qz_{qid}_{selected}
    parts = query.data.split("_")
    if len(parts) < 3:
        await query.answer("❌ Lỗi quiz!", show_alert=True)
        return

    qid = parts[1]
    selected = int(parts[2])

    question = _quiz_questions.get(qid)
    if not question:
        await query.answer("⏰ Câu hỏi đã hết hạn! Dùng /quiz để tạo mới.", show_alert=True)
        return

    correct_idx = question["correct_idx"]
    correct_word = question["correct_word"]
    correct_def = question["correct_def"]
    q_type = question["type"]
    labels = ["A", "B", "C", "D"]
    is_correct = (selected == correct_idx)
    response_time = time.time() - question["created_at"]

    uid_str = str(user_id)
    if uid_str in question["answered_by"]:
        prev = question["answered_by"][uid_str]
        prev_result = "✅ Đúng" if prev["correct"] else "❌ Sai"
        await query.answer(f"Bạn đã trả lời rồi! ({prev_result} — {prev['time']}s)", show_alert=True)
        return

    # Ghi lại câu trả lời vào question
    question["answered_by"][uid_str] = {
        "name": username,
        "selected": selected,
        "correct": is_correct,
        "time": round(response_time, 1)
    }

    # Lưu stats toàn cục
    record_answer(user_id, username, is_correct, response_time, q_type)

    is_group = query.message.chat.type in ("group", "supergroup")

    # ── GROUP MODE ──────────────────────────────────────────────────────────
    if is_group:
        session = context.chat_data.get("quiz_session", {})
        current = session.get("current", 1)
        total = session.get("total", 1)
        group_scores = session.get("group_scores", {})

        # Cộng điểm và lưu thời gian
        if is_correct:
            if uid_str not in group_scores:
                group_scores[uid_str] = {"name": username, "points": 0, "times": []}
            group_scores[uid_str]["name"] = username
            group_scores[uid_str]["points"] += 1
            group_scores[uid_str]["times"].append(round(response_time, 1))
            session["group_scores"] = group_scores
            context.chat_data["quiz_session"] = session

        # Toast thông báo
        time_str = f"{response_time:.1f}s"
        if is_correct:
            await query.answer(f"✅ Chính xác! +1 điểm ({time_str})", show_alert=False)
        else:
            await query.answer(
                f"❌ Sai! Đáp án: {labels[correct_idx]}\n{correct_word}: {correct_def[:80]}",
                show_alert=True
            )

        # Rebuild message + thêm danh sách đã trả lời (theo thứ tự)
        answered = question["answered_by"]
        answer_lines = []
        for order_uid, info in answered.items():
            icon = "✅" if info["correct"] else "❌"
            pts = f" +1" if info["correct"] else ""
            answer_lines.append(f"{icon} *{info['name']}*{pts} — {info['time']}s")

        q_text = _rebuild_question_message(question, current, total)
        updated_text = q_text + "\n\n👥 *Đã trả lời:*\n" + "\n".join(answer_lines)

        # Thêm nút "Tiếp ▶" nếu multi-question (người khởi tạo hoặc bất kỳ ai có thể bấm)
        keyboard_rows = []
        row = [InlineKeyboardButton(labels[i], callback_data=f"qz_{qid}_{i}") for i in range(4)]
        keyboard_rows.append(row)
        if total > 1:
            keyboard_rows.append([InlineKeyboardButton(f"▶ Câu tiếp ({current}/{total})", callback_data=f"qznext_{qid}")])

        try:
            await query.edit_message_text(
                updated_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_rows)
            )
        except Exception:
            pass

        # Nếu chỉ 1 câu → kết thúc ngay
        if total <= 1:
            # Ghi lại câu này rồi gửi scoreboard
            session["answers"].append({"any_correct": any(i["correct"] for i in answered.values())})
            context.chat_data["quiz_session"] = session
            await asyncio.sleep(2)
            all_words = sheets.get_all_words()
            await _advance_group_quiz(context.chat_data, query.message, all_words)

        return

    # ── PRIVATE MODE ────────────────────────────────────────────────────────
    session = context.user_data.get("quiz_session", {})
    total = session.get("total", 1)
    current = session.get("current", 1)
    score = session.get("score", 0)
    used_words = session.get("used_words", set())
    answers = session.get("answers", [])

    if is_correct:
        score += 1

    answers.append({
        "word": correct_word,
        "is_correct": is_correct,
        "selected": labels[selected],
        "correct": labels[correct_idx],
        "time": round(response_time, 1),
        "type": q_type
    })

    time_str = f"⏱ {response_time:.1f}s"

    if total <= 1 or current >= total:
        if total <= 1:
            if is_correct:
                text = (
                    f"✅ *CHÍNH XÁC!* 🎉 {time_str}\n\n"
                    f"*{correct_word}*: _{correct_def}_\n\n"
                    f"Dùng `/quiz` hoặc `/quiz 5` để chơi tiếp!"
                )
            else:
                correct_example_q = question.get("correct_example", "")
                example_line = f"\n💬 _{correct_example_q}_" if q_type == "fill_blank" and correct_example_q else ""
                text = (
                    f"❌ *SAI RỒI!* {time_str}\n\n"
                    f"Bạn chọn: *{labels[selected]}* ❌\n"
                    f"Đáp án đúng: *{labels[correct_idx]}* ✅\n\n"
                    f"*{correct_word}*: _{correct_def}_"
                    f"{example_line}\n\n"
                    f"Dùng `/quiz` để thử lại!"
                )
        else:
            pct = int(score / total * 100)
            grade = "🏆 XUẤT SẮC!" if pct >= 90 else "🌟 GIỎI!" if pct >= 70 else "👍 KHÁ!" if pct >= 50 else "💪 CẦN CỐ GẮNG THÊM!"
            total_time = sum(a.get("time", 0) for a in answers)
            avg_time = total_time / len(answers) if answers else 0
            summary_lines = [
                f"  {'✅' if a['is_correct'] else '❌'} *{a['word']}* — {a.get('time',0)}s"
                for a in answers
            ]
            text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  📊 *KẾT QUẢ QUIZ*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 *Điểm:* {score}/{total} ({pct}%)\n"
                f"{grade}\n"
                f"⏱ *Tổng:* {total_time:.1f}s (TB: {avg_time:.1f}s)\n\n"
                f"📋 *Chi tiết:*\n" +
                "\n".join(summary_lines) + "\n\n"
                f"Dùng `/quiz {total}` để chơi lại!\n"/
                f"Dùng `/leaderboard` để xem BXH!"
            )

        await query.edit_message_text(text, parse_mode="Markdown")
        context.user_data.pop("quiz_session", None)

    else:
        if is_correct:
            result_text = f"✅ *Câu {current}:* ĐÚNG! *{correct_word}* — {time_str}"
        else:
            correct_example_q = question.get("correct_example", "")
            if q_type == "fill_blank" and correct_example_q:
                result_text = (
                    f"❌ *Câu {current}:* SAI! *{correct_word}* — {time_str}\n"
                    f"Đáp án: *{labels[correct_idx]}* ({correct_word})\n"
                    f"💬 _{correct_example_q[:120]}_"
                )
            else:
                result_text = (
                    f"❌ *Câu {current}:* SAI! *{correct_word}* — {time_str}\n"
                    f"Đáp án: *{labels[correct_idx]}* — _{correct_def[:80]}_"
                )

        await query.edit_message_text(result_text, parse_mode="Markdown")

        used_words.add(correct_word)
        all_words = sheets.get_all_words()
        next_question = _build_quiz_question(all_words, used_words)

        if not next_question:
            pct = int(score / current * 100)
            await query.message.reply_text(
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n  📊 *KẾT QUẢ QUIZ*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 *Điểm:* {score}/{current} ({pct}%)\n_(Hết từ)_\n\nDùng `/add` để thêm từ mới!",
                parse_mode="Markdown"
            )
            context.user_data.pop("quiz_session", None)
            return

        context.user_data["quiz_session"] = {
            "total": total, "current": current + 1, "score": score,
            "used_words": used_words, "answers": answers, "group_scores": {}
        }
        await asyncio.sleep(1.2)
        await _send_quiz_question(query.message, next_question, current + 1, total)


# ─── /sentence (đặt câu với từ ngẫu nhiên hoặc từ cụ thể, Gemini chấm) ───────

def _send_sentence_prompt(word_data: dict) -> str:
    """Tạo text prompt để yêu cầu người dùng đặt câu với từ word_data."""
    word = word_data.get("word", "")
    definition = word_data.get("definition", "")
    phonetic = word_data.get("phonetic", "")
    example = word_data.get("example", "")
    topic = word_data.get("topic", "general")
    emoji = TOPIC_EMOJIS.get(topic, "📌")
    phonetic_str = f" /{phonetic}/" if phonetic else ""
    example_str = f"\n💬 _{example}_" if example else ""
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  ✍️ *ĐẶT CÂU VỚI TỪ SAU*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *{word}*{phonetic_str} {emoji}[{topic}]\n"
        f"📖 _{definition}_{example_str}\n\n"
        "Hãy đặt *1 câu tiếng Anh* sử dụng từ trên.\n"
        "Gõ /cancel để bỏ qua."
    )


async def sentence_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GEMINI_API_KEY:
        await update.message.reply_text(
            "❌ Chưa cấu hình Gemini API key.\n"
            "Thêm `gemini_api_key` vào file `credentials.json`.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    words = sheets.get_all_words()
    words_with_def = [w for w in words if w.get("definition", "")]
    if not words_with_def:
        await update.message.reply_text(
            "📭 Chưa có từ nào trong kho!\nDùng `/add` để thêm từ.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # ── Nếu người dùng chỉ định từ: /sentence <word> ──
    if context.args:
        query_word = " ".join(context.args).lower().strip()
        # Tìm khớp chính xác trước
        exact = [w for w in words_with_def if w.get("word", "").lower() == query_word]
        if exact:
            word_data = exact[0]
            context.user_data["sentence_word"] = word_data
            context.user_data["sentence_start_time"] = time.time()
            await update.message.reply_text(_send_sentence_prompt(word_data), parse_mode="Markdown")
            return SENTENCE_WAIT

        # Tìm khớp một phần (contains)
        partial = [w for w in words_with_def if query_word in w.get("word", "").lower()]
        if not partial:
            await update.message.reply_text(
                f"❌ Không tìm thấy từ *{query_word}* trong kho từ vựng.\n"
                "Dùng `/sentence` để luyện với từ ngẫu nhiên, hoặc `/add` để thêm từ mới.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if len(partial) == 1:
            word_data = partial[0]
            context.user_data["sentence_word"] = word_data
            context.user_data["sentence_start_time"] = time.time()
            await update.message.reply_text(_send_sentence_prompt(word_data), parse_mode="Markdown")
            return SENTENCE_WAIT

        # Nhiều kết quả → cho người dùng chọn (tối đa 8)
        candidates = partial[:8]
        keyboard = [
            [InlineKeyboardButton(w["word"], callback_data=f"sw_{w['word']}")]
            for w in candidates
        ]
        context.user_data["sentence_candidates"] = {w["word"]: w for w in candidates}
        await update.message.reply_text(
            f"🔍 Tìm thấy *{len(candidates)}* từ khớp với *{query_word}*. Chọn từ muốn luyện:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SENTENCE_PICK

    # ── Không có args → từ ngẫu nhiên ──
    word_data = random.choice(words_with_def)
    context.user_data["sentence_word"] = word_data
    context.user_data["sentence_start_time"] = time.time()
    await update.message.reply_text(_send_sentence_prompt(word_data), parse_mode="Markdown")
    return SENTENCE_WAIT


async def sentence_pick_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người dùng bấm chọn từ từ inline keyboard."""
    query = update.callback_query
    await query.answer()
    chosen_word = query.data[len("sw_"):]
    candidates = context.user_data.get("sentence_candidates", {})
    word_data = candidates.get(chosen_word)
    if not word_data:
        await query.edit_message_text("❌ Không tìm thấy từ. Dùng /sentence để thử lại.")
        return ConversationHandler.END

    context.user_data["sentence_word"] = word_data
    context.user_data["sentence_start_time"] = time.time()
    context.user_data.pop("sentence_candidates", None)
    await query.edit_message_text(_send_sentence_prompt(word_data), parse_mode="Markdown")
    return SENTENCE_WAIT


async def sentence_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"[sentence_receive] called by {update.effective_user.id} in chat {update.effective_chat.id}")
    sentence = update.message.text.strip()
    word_data = context.user_data.get("sentence_word", {})
    start_time = context.user_data.get("sentence_start_time", time.time())
    response_time = time.time() - start_time

    word = word_data.get("word", "")
    definition = word_data.get("definition", "")
    pos = word_data.get("pos") or None          # e.g. "noun", "verb", "adjective"; None if not in sheet
    user = update.effective_user
    user_id = user.id
    username = user.first_name or "Unknown"

    # Kiểm tra câu có chứa từ (hoặc biến thể) không — dùng prefix match để chấp nhận
    # các dạng như struggling/struggled/struggles cho "struggle"
    word_pattern = re.compile(re.escape(word), re.IGNORECASE)
    if not word_pattern.search(sentence):
        await update.message.reply_text(
            f"⚠️ Câu của bạn không chứa từ *{word}* (hoặc dạng biến thể của nó)!\n"
            "Hãy đặt lại câu có sử dụng từ đó.",
            parse_mode="Markdown"
        )
        return SENTENCE_WAIT

    await update.message.reply_text("⏳ Đang chấm bài...", parse_mode="Markdown")
    logger.info(f"[sentence_receive] calling Gemini for word='{word}', pos='{pos}', sentence='{sentence[:50]}'")

    result = check_sentence(word, definition, sentence, pos=pos)

    if result is None:
        await update.message.reply_text(
            "❌ Lỗi khi kết nối Gemini. Thử lại sau!",
            parse_mode="Markdown"
        )
        context.user_data.pop("sentence_word", None)
        context.user_data.pop("sentence_start_time", None)
        return ConversationHandler.END

    score = result.get("score", 0)
    is_correct = result.get("is_correct", False)
    grammar_ok = result.get("grammar_ok", False)
    usage_ok = result.get("usage_ok", False)
    feedback = result.get("feedback", "")
    corrected = result.get("corrected")

    # Ghi stats
    record_answer(user_id, username, is_correct, response_time, "make_sentence")

    # Build icons
    grammar_icon = "✅" if grammar_ok else "❌"
    usage_icon = "✅" if usage_ok else "❌"
    score_icon = "🏆" if score >= 9 else "🌟" if score >= 7 else "👍" if score >= 5 else "💪"

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  ✍️ *KẾT QUẢ ĐẶT CÂU*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Câu của bạn:*\n_{sentence}_\n\n"
        f"{grammar_icon} *Grammar:* {'Đúng' if grammar_ok else 'Có lỗi'}\n"
        f"{usage_icon} *Dùng từ:* {'Chính xác' if usage_ok else 'Chưa đúng'}\n"
        f"{score_icon} *Điểm:* {score}/10"
        f" {'(+1 điểm quiz!)' if is_correct else ''}\n\n"
        f"💬 *Nhận xét:*\n{feedback}"
    )

    if corrected:
        text += f"\n\n✏️ *Gợi ý sửa:*\n_{corrected}_"

    text += "\n\nDùng `/sentence` để luyện từ tiếp theo!"

    await update.message.reply_text(text, parse_mode="Markdown")

    context.user_data.pop("sentence_word", None)
    context.user_data.pop("sentence_start_time", None)
    return ConversationHandler.END


async def sentence_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("sentence_word", None)
    context.user_data.pop("sentence_start_time", None)
    await update.message.reply_text(
        "Đã hủy. Dùng `/sentence` để thử lại!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─── /leaderboard ────────────────────────────────────────────────────────────
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb = get_leaderboard(10)
    if not lb:
        await update.message.reply_text(
            "📭 Chưa có dữ liệu quiz.\nDùng `/quiz` để bắt đầu chơi!",
            parse_mode="Markdown"
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🏆 *BẢNG XẾP HẠNG QUIZ*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    for i, u in enumerate(lb):
        medal = medals[i] if i < 3 else f"{i+1}."
        streak_str = f" 🔥{u['streak']}" if u['streak'] >= 3 else ""
        fastest = f" ⚡{u['fastest']}s" if u.get('fastest') else ""
        lines.append(
            f"{medal} *{u['name']}*\n"
            f"    ✅ {u['correct']}/{u['total']} ({u['accuracy']}%)"
            f" | ⏱ TB {u['avg_time']}s{fastest}{streak_str}"
        )

    # Stats cá nhân
    user_stats = get_user_stats(update.effective_user.id)
    if user_stats:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(
            f"📊 *Bạn:* {user_stats['correct']}/{user_stats['total']} "
            f"({user_stats['accuracy']}%) | TB {user_stats['avg_time']}s"
        )
        if user_stats['current_streak'] >= 2:
            lines.append(f"🔥 Streak hiện tại: {user_stats['current_streak']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── /mystats ────────────────────────────────────────────────────────────────
async def mystats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_stats = get_user_stats(update.effective_user.id)
    if not user_stats:
        await update.message.reply_text(
            "📭 Bạn chưa chơi quiz lần nào.\nDùng `/quiz` để bắt đầu!",
            parse_mode="Markdown"
        )
        return

    # By type breakdown
    type_lines = []
    for t, data in user_stats.get("by_type", {}).items():
        t_name = QUIZ_TYPE_NAMES.get(t, t)
        pct = int(data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
        type_lines.append(f"  {t_name}: {data['correct']}/{data['total']} ({pct}%)")

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📊 *THỐNG KÊ CỦA BẠN*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *{user_stats['name']}*\n\n"
        f"✅ *Đúng:* {user_stats['correct']}/{user_stats['total']} ({user_stats['accuracy']}%)\n"
        f"⏱ *TB thời gian:* {user_stats['avg_time']}s\n"
        f"⚡ *Nhanh nhất:* {user_stats.get('fastest', 'N/A')}s\n"
        f"🔥 *Streak tốt nhất:* {user_stats['best_streak']}\n"
        f"🔥 *Streak hiện tại:* {user_stats['current_streak']}\n"
    )

    if type_lines:
        text += "\n📋 *Theo loại câu hỏi:*\n" + "\n".join(type_lines)

    text += "\n\nDùng `/leaderboard` để xem BXH!"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Group quiz: nút Tiếp ▶ ──────────────────────────────────────────────────
async def quiz_next_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nút ▶ Câu tiếp trong group quiz."""
    query = update.callback_query
    await query.answer("➡️ Chuyển câu tiếp theo...", show_alert=False)

    is_group = query.message.chat.type in ("group", "supergroup")
    session = context.chat_data.get("quiz_session") if is_group else None
    if not session:
        await query.answer("❌ Không có quiz session!", show_alert=True)
        return

    # Lấy qid từ callback data: qznext_{qid}
    qid = query.data[len("qznext_"):]
    question = _quiz_questions.get(qid)
    if question:
        answered = question.get("answered_by", {})
        session["answers"].append({"any_correct": any(i["correct"] for i in answered.values())})
        context.chat_data["quiz_session"] = session

    all_words = sheets.get_all_words()
    await _advance_group_quiz(context.chat_data, query.message, all_words)

# ─── /list ────────────────────────────────────────────────────────────────────

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = sheets.get_all_words()
    if not words:
        await update.message.reply_text(
            "📭 Chưa có từ nào trong danh sách.\nDùng `/add` hoặc `/addword` để thêm!",
            parse_mode="Markdown"
        )
        return

    # Show last 20
    recent = words[-20:]
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📚 *DANH SÁCH TỪ VỰNG*\n"
        f"  Tổng: {len(words)} từ | Hiển thị: {len(recent)} gần nhất\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for i, row in enumerate(reversed(recent), 1):
        word = row.get("word", "")
        phonetic = row.get("phonetic", "")
        definition = row.get("definition", "")[:50]
        if len(row.get("definition", "")) > 50:
            definition += "..."
        topic = row.get("topic", "general")
        emoji = TOPIC_EMOJIS.get(topic, "📌")

        phonetic_str = f" /{phonetic}/" if phonetic else ""
        lines.append(f"{i}. *{word}*{phonetic_str} {emoji}[{topic}]\n   _{definition}_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /topic ───────────────────────────────────────────────────────────────────
async def filter_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "*Cách dùng:* `/topic <chủ đề>`\n"
            "_VD:_ `/topic environment`\n\n"
            "Dùng `/topics` để xem danh sách chủ đề.",
            parse_mode="Markdown"
        )
        return

    topic = context.args[0].lower().strip()
    words = sheets.get_words_by_topic(topic)

    if not words:
        await update.message.reply_text(f"📭 Không có từ nào thuộc chủ đề *{topic}*.", parse_mode="Markdown")
        return

    emoji = TOPIC_EMOJIS.get(topic, "📌")
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  {emoji} *CHỦ ĐỀ: {topic.upper()}*\n"
        f"  Tổng: {len(words)} từ\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for i, row in enumerate(words, 1):
        word = row.get("word", "")
        phonetic = row.get("phonetic", "")
        definition = row.get("definition", "")[:60]
        if len(row.get("definition", "")) > 60:
            definition += "..."
        example = row.get("example", "")

        phonetic_str = f" /{phonetic}/" if phonetic else ""
        lines.append(f"{i}. *{word}*{phonetic_str}")
        lines.append(f"   📖 _{definition}_")
        if example:
            lines.append(f"   💬 _{example[:80]}_")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /topics ──────────────────────────────────────────────────────────────────
async def list_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Count words per topic
    all_words = sheets.get_all_words()
    topic_counts = {}
    for w in all_words:
        t = w.get("topic", "general")
        topic_counts[t] = topic_counts.get(t, 0) + 1

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📚 *CHỦ ĐỀ IELTS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for topic in IELTS_TOPICS:
        emoji = TOPIC_EMOJIS.get(topic, "📌")
        count = topic_counts.get(topic, 0)
        count_str = f" ({count} từ)" if count > 0 else ""
        lines.append(f"{emoji} {topic}{count_str}")

    # General
    gen_count = topic_counts.get("general", 0)
    if gen_count > 0:
        lines.append(f"\n📌 general ({gen_count} từ)")

    lines.append(f"\n📊 *Tổng:* {len(all_words)} từ")
    lines.append("\nDùng `/topic <tên>` để lọc từ theo chủ đề.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /review ─────────────────────────────────────────────────────────────────
async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = sheets.get_random_words(5)
    if not words:
        await update.message.reply_text("📭 Chưa có từ nào để ôn tập!", parse_mode="Markdown")
        return

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📖 *ÔN TẬP TỪ VỰNG*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for i, row in enumerate(words, 1):
        word = row.get("word", "")
        phonetic = row.get("phonetic", "")
        definition = row.get("definition", "_(chưa có nghĩa)_")
        example = row.get("example", "")
        topic = row.get("topic", "general")
        emoji = TOPIC_EMOJIS.get(topic, "📌")

        phonetic_str = f" /{phonetic}/" if phonetic else ""
        lines.append(f"{i}. *{word}*{phonetic_str} {emoji}[{topic}]")
        lines.append(f"   📖 _{definition}_")
        if example:
            lines.append(f"   💬 _{example}_")
        lines.append("")

    lines.append("_Dùng `/quiz` để kiểm tra kiến thức!_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /stats ──────────────────────────────────────────────────────────────────
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_words = sheets.get_all_words()
    total = len(all_words)

    if total == 0:
        await update.message.reply_text("📭 Chưa có từ nào. Bắt đầu thêm từ đi!", parse_mode="Markdown")
        return

    # Count by topic
    topic_counts = {}
    added_by_counts = {}
    for w in all_words:
        t = w.get("topic", "general")
        topic_counts[t] = topic_counts.get(t, 0) + 1
        a = w.get("added_by", "Unknown")
        added_by_counts[a] = added_by_counts.get(a, 0) + 1

    # Top topics
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    topic_lines = []
    for t, c in sorted_topics:
        emoji = TOPIC_EMOJIS.get(t, "📌")
        bar = "█" * min(c, 15)
        topic_lines.append(f"  {emoji} {t}: {bar} {c}")

    # Top contributors
    sorted_users = sorted(added_by_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    user_lines = [f"  🥇 {u}: {c} từ" if i == 0 else f"  {'🥈' if i == 1 else '🥉' if i == 2 else '  '} {u}: {c} từ" for i, (u, c) in enumerate(sorted_users)]

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📊 *THỐNG KÊ TỪ VỰNG*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Tổng từ vựng:* {total}\n"
        f"📂 *Số chủ đề:* {len(topic_counts)}\n"
        f"👥 *Người đóng góp:* {len(added_by_counts)}\n\n"
        "🏆 *Top chủ đề:*\n" +
        "\n".join(topic_lines) + "\n\n"
        "👑 *Top đóng góp:*\n" +
        "\n".join(user_lines)
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if GEMINI_API_KEY:
        init_gemini(GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY chưa được cấu hình. /sentence sẽ không hoạt động.")

    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    # Conversation handler for /sentence
    sentence_conv = ConversationHandler(
        entry_points=[CommandHandler("sentence", sentence_start)],
        states={
            SENTENCE_PICK: [
                CallbackQueryHandler(sentence_pick_word, pattern=r"^sw_"),
                CommandHandler("cancel", sentence_cancel),
            ],
            SENTENCE_WAIT: [
                CommandHandler("cancel", sentence_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sentence_receive),
            ],
        },
        fallbacks=[CommandHandler("cancel", sentence_cancel)],
    )

    # Conversation handler for /addword
    cancel_handler = CommandHandler("cancel", addword_cancel)
    addword_conv = ConversationHandler(
        entry_points=[CommandHandler("addword", addword_start)],
        states={
            WORD_INPUT: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, addword_get_word)],
            OVERWRITE_CONFIRM: [cancel_handler, CallbackQueryHandler(addword_confirm_overwrite, pattern=r"^overwrite_")],
            MEANING_INPUT: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, addword_get_meaning)],
            PHONETIC_INPUT: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, addword_get_phonetic)],
            EXAMPLE_INPUT: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, addword_get_example)],
            TOPIC_INPUT: [cancel_handler, CallbackQueryHandler(addword_select_topic, pattern=r"^topic_")],
        },
        fallbacks=[cancel_handler],
    )

    app.add_handler(sentence_conv)
    app.add_handler(addword_conv)
    app.add_handler(CommandHandler("cancel", addword_cancel))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_word))
    app.add_handler(CommandHandler("lookup", lookup_cmd))
    app.add_handler(CommandHandler("list", list_words))
    app.add_handler(CommandHandler("topic", filter_topic))
    app.add_handler(CommandHandler("topics", list_topics))
    app.add_handler(CommandHandler("search", search_word))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("review", review_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("mystats", mystats_cmd))

    # Quiz callbacks
    app.add_handler(CallbackQueryHandler(quiz_answer, pattern=r"^qz_"))
    app.add_handler(CallbackQueryHandler(quiz_next_handler, pattern=r"^qznext_"))

    # Setup daily reminder
    setup_daily_reminder(app, sheets)

    logger.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
