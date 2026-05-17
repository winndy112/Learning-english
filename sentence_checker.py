import json
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

_model = None

def init_gemini(api_key: str):
    global _model
    genai.configure(api_key=api_key)
    _model = genai.GenerativeModel("gemini-2.5-flash-lite")
    logger.info("Gemini initialized.")

def check_sentence(word: str, definition: str, sentence: str, pos: str | None = None) -> dict | None:
    """
    Dùng Gemini Flash kiểm tra câu của người dùng.
    Trả về dict:
      {
        "grammar_ok": bool,
        "usage_ok": bool,
        "score": int (0-10),
        "is_correct": bool (score >= 7),
        "feedback": str,
        "corrected": str | None
      }
    Trả về None nếu lỗi API.
    """
    if _model is None:
        logger.error("[sentence_checker] Gemini chưa được khởi tạo.")
        return None

    # Build the word-class context block
    if pos:
        pos_rule = (
            f'Word class: "{word}" is a *{pos}*. '
            f"The student MUST use it as a {pos}. "
            f"Using it as a different part of speech (e.g. verb instead of noun) is a usage error and should lower the score."
        )
        corrected_pos_rule = (
            f"The corrected sentence MUST use \"{word}\" (or a natural {pos} form of it) "
            f"as a {pos}, not as a different part of speech."
        )
    else:
        pos_rule = (
            f'Infer the part of speech of "{word}" from its definition. '
            f"If the student uses it as the wrong part of speech, treat that as a usage error."
        )
        corrected_pos_rule = (
            f"The corrected sentence MUST use \"{word}\" in its correct part of speech "
            f"(inferred from the definition), not swap it for a different word class."
        )

    prompt = f"""You are a strict but encouraging IELTS English teacher.

A student is practicing the vocabulary word: "{word}"
Word meaning: "{definition}"
{pos_rule}
Student's sentence: "{sentence}"

STEP 1 — Identify the grammatical role of "{word}" in the sentence BEFORE evaluating word class:
Look at how "{word}" (or its conjugated/inflected form) actually functions in the sentence:
- If it acts as the predicate verb of a main clause or relative clause (e.g. "ignites", "ignited", "is igniting") → it is used as a VERB. A word functioning as a verb will have a subject (noun/pronoun) performing or receiving the action.
- If it names a person/place/thing and acts as subject or object → NOUN.
- If it directly modifies a noun without a subject (e.g. "an igniting passion" as a pre-noun modifier with no clause subject) → ADJECTIVE.
- If it modifies a verb/adjective → ADVERB.
⚠️ IMPORTANT: Do NOT label a conjugated verb form as an adjective simply because it ends in "-ed" or "-ing". Always check the syntactic role: if there is a subject-verb relationship, it IS a verb.

Evaluate the sentence on THREE criteria:
1. Grammar: Is the sentence grammatically correct?
2. Usage: Is the word "{word}" used correctly and naturally in context?
3. Word class: Based on your Step 1 analysis, is "{word}" used as the correct part of speech?

Return ONLY valid JSON, no markdown, no extra text:
{{
  "grammar_ok": true or false,
  "usage_ok": true or false,
  "score": integer from 0 to 10,
  "feedback": "feedback in Vietnamese — explain what is good and what is wrong, including word-class errors if any",
  "corrected": "a corrected ENGLISH sentence IF and ONLY IF the sentence has real errors — must be in English, must be meaningfully different from the original, not just punctuation changes; set to null if the sentence is acceptable. IMPORTANT: the corrected sentence MUST still contain the vocabulary word '{word}' or one of its natural word-form variants. {corrected_pos_rule} Do NOT replace '{word}' with a completely different synonym."
}}

Scoring rules:
- 9-10: Perfect grammar, word used naturally and correctly as the right part of speech
- 7-8: Good attempt, only very minor stylistic issues
- 5-6: Understandable but has grammar errors or slightly unnatural word usage
- 3-4: Noticeable grammar errors OR word used with wrong meaning/context OR wrong part of speech
- 0-2: Severe grammar errors AND/OR word completely misused or used as entirely wrong word class

CRITICAL consistency rules — violating these is forbidden:
1. If score >= 7, then grammar_ok and usage_ok should both be true, and corrected MUST be null.
2. If corrected is not null, it MUST be substantively different from the original sentence (not just adding/removing punctuation). If the only fix is punctuation, set corrected to null instead.
3. If grammar_ok is true AND usage_ok is true, the score MUST be >= 7.
4. The feedback must be consistent with the score: if score >= 7, feedback should be mostly positive.

Be strict about grammar. Do not accept sentences with subject-verb agreement errors, wrong tense, or missing articles when required.
5. If corrected is not null, it MUST still include the word "{word}" or a natural word-form variant of it used as the correct part of speech. Never replace "{word}" with a completely different word/synonym in the corrected sentence."""

    try:
        response = _model.generate_content(prompt)
        raw = response.text.strip()

        # Xóa markdown code block nếu Gemini trả về
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        result["is_correct"] = result.get("score", 0) >= 7
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[sentence_checker] JSON parse error: {e} | raw: {raw!r}")
        return None
    except Exception as e:
        logger.error(f"[sentence_checker] Gemini API error: {e}")
        return None
