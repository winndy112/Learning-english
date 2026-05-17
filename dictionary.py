import requests
import re
import logging

logger = logging.getLogger(__name__)

def lookup_word(word: str) -> dict | None:
    """
    Tra nghĩa từ qua Free Dictionary API.
    Tự động tìm câu ví dụ từ nhiều nguồn nếu từ điển không có.
    Trả về dict: {definition, example, phonetic} hoặc None nếu không tìm thấy.
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data or not isinstance(data, list):
            return None

        entry = data[0]

        
        phonetic = entry.get("phonetic", "")
        if not phonetic:
            for p in entry.get("phonetics", []):
                if p.get("text"):
                    phonetic = p["text"]
                    break

        # ─── Definition (lấy cái đầu tiên có nội dung) ──────────────────
        definition = ""
        for meaning in entry.get("meanings", []):
            for defn in meaning.get("definitions", []):
                if defn.get("definition"):
                    definition = defn["definition"]
                    break
            if definition:
                break

        # ─── Example: tìm qua TẤT CẢ definitions ────────────────────────
        example = _find_example_from_api(entry, word)

        # ─── Fallback: tìm example từ nguồn bên ngoài ───────────────────
        if not example:
            example = _fetch_example_external(word)

        return {
            "phonetic": phonetic.strip("/").strip() if phonetic else "",
            "definition": definition,
            "example": example
        }

    except Exception as e:
        logger.error(f"[dictionary] Error looking up '{word}': {e}")
        return None


def _find_example_from_api(entry: dict, word: str) -> str:
    """
    Tìm câu ví dụ trong toàn bộ meanings/definitions của Free Dictionary API.
    Ưu tiên: example có chứa từ gốc > example bất kỳ.
    """
    all_examples = []

    for meaning in entry.get("meanings", []):
        for defn in meaning.get("definitions", []):
            ex = defn.get("example", "")
            if ex:
                all_examples.append(ex)

    if not all_examples:
        return ""

    # Ưu tiên example có chứa đúng từ đang tra
    for ex in all_examples:
        if word.lower() in ex.lower():
            return ex

    # Không có thì lấy cái đầu tiên
    return all_examples[0]


def _fetch_example_external(word: str) -> str:
    """
    Tìm câu ví dụ từ các nguồn bên ngoài khi Free Dictionary API không có.
    Thử lần lượt: Tatoeba → Web scraping sentencedict.com
    """
    # Nguồn 1: Tatoeba (kho câu ví dụ cộng đồng, miễn phí)
    example = _fetch_from_tatoeba(word)
    if example:
        return example

    # Nguồn 2: yoursentences / sentencedict
    example = _fetch_from_sentencedict(word)
    if example:
        return example

    # Nguồn 3: Wordnik examples (public, no key needed for basic)
    example = _fetch_from_wordnik(word)
    if example:
        return example

    return ""


def _fetch_from_tatoeba(word: str) -> str:
    """Lấy câu ví dụ từ Tatoeba API."""
    try:
        url = f"https://tatoeba.org/en/api_v0/search?from=eng&query={word}&to=none"
        headers = {"User-Agent": "IELTS-Vocab-Bot/1.0"}
        resp = requests.get(url, timeout=5, headers=headers)
        if resp.status_code != 200:
            return ""

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return ""

        # Lọc câu ngắn, dễ hiểu (10-120 ký tự) và chứa từ cần tra
        good_sentences = []
        for r in results:
            text = r.get("text", "")
            if (word.lower() in text.lower()
                    and 10 <= len(text) <= 120
                    and text[0].isupper()
                    and text[-1] in ".!?"):
                good_sentences.append(text)

        if good_sentences:
            # Ưu tiên câu ngắn gọn, dễ hiểu
            good_sentences.sort(key=len)
            return good_sentences[0]

        # Nếu không có câu "hoàn hảo", lấy câu đầu tiên chứa từ
        for r in results:
            text = r.get("text", "")
            if word.lower() in text.lower() and len(text) <= 150:
                return text

        return ""

    except Exception as e:
        logger.debug(f"[tatoeba] Error: {e}")
        return ""


def _fetch_from_sentencedict(word: str) -> str:
    """Lấy câu ví dụ từ sentencedict.com bằng web scraping."""
    try:
        url = f"https://sentencedict.com/{word}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, timeout=5, headers=headers)
        if resp.status_code != 200:
            return ""

        # Tìm câu ví dụ trong HTML (thường nằm trong <div id="all">)
        # Pattern: số thứ tự + dấu chấm + câu ví dụ
        sentences = re.findall(
            r'<div[^>]*>\s*\d+[.)]\s*(.+?)\s*</div>',
            resp.text,
            re.IGNORECASE
        )

        if not sentences:
            # Thử pattern khác
            sentences = re.findall(
                r'(?:^|\n)\s*\d+[.)]\s*([A-Z][^<\n]{10,120}[.!?])',
                resp.text
            )

        for s in sentences:
            # Clean HTML tags
            clean = re.sub(r'<[^>]+>', '', s).strip()
            if (word.lower() in clean.lower()
                    and 10 <= len(clean) <= 150
                    and clean[0].isupper()):
                return clean

        return ""

    except Exception as e:
        logger.debug(f"[sentencedict] Error: {e}")
        return ""


def _fetch_from_wordnik(word: str) -> str:
    """Lấy câu ví dụ từ Wordnik public API."""
    try:
        url = f"https://api.wordnik.com/v4/word.json/{word}/topExample"
        headers = {"User-Agent": "IELTS-Vocab-Bot/1.0"}
        resp = requests.get(url, timeout=5, headers=headers)
        if resp.status_code != 200:
            return ""

        data = resp.json()
        text = data.get("text", "")
        if text and word.lower() in text.lower() and len(text) <= 200:
            return text.strip()

        return ""

    except Exception as e:
        logger.debug(f"[wordnik] Error: {e}")
        return ""


# ─── Standalone example lookup ───────────────────────────────────────────────
def find_example_sentence(word: str) -> str:
    """
    Tìm câu ví dụ cho một từ từ nhiều nguồn.
    Dùng khi cần tìm example riêng (không cần lookup cả nghĩa).
    """
    # Thử Free Dictionary API trước
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list):
                example = _find_example_from_api(data[0], word)
                if example:
                    return example
    except Exception:
        pass

    # Thử các nguồn bên ngoài
    return _fetch_example_external(word)
