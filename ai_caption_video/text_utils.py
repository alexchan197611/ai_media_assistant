import re


SENTENCE_SPLIT_RE = re.compile(r"([^。！？!?；;\n]+[。！？!?；;]?|\n+)")


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def split_chinese_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for match in SENTENCE_SPLIT_RE.finditer(text):
        sentence = match.group(0).strip()
        if sentence and not sentence.isspace():
            sentences.append(sentence)
    return sentences


def parse_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,，\s]+", value)
    return [part.strip() for part in parts if part.strip()]

