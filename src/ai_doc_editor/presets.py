"""Named instruction templates. A user instruction, if given, is appended to the preset."""

from __future__ import annotations

PRESETS: dict[str, str] = {
    "proofread": (
        "Fix spelling, grammar and punctuation mistakes. Do not rephrase correct text and do not "
        "change names, numbers, dates or terminology."
    ),
    "formalize": (
        "Rewrite in a formal, professional business tone. Keep the meaning, facts, names and "
        "numbers. Keep each segment about the same length."
    ),
    "translate_en": (
        "Translate every segment into English. Keep names, numbers, codes, e-mail addresses and "
        "URLs unchanged. Keep the translation as short as natural English allows."
    ),
    "translate_ru": (
        "Translate every segment into Russian. Keep names, numbers, codes, e-mail addresses and "
        "URLs unchanged. Keep the translation as short as natural Russian allows."
    ),
    "anonymize": (
        "Replace personal data with placeholders: full or short names of people with [NAME], "
        "phone numbers with [PHONE], e-mail addresses with [EMAIL], postal addresses with "
        "[ADDRESS], personal ID and tax numbers with [ID]. Do not change company names or "
        "anything else."
    ),
}


def build_instruction(preset: str | None, instruction: str | None) -> str:
    parts = []
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; choose one of {sorted(PRESETS)}")
        parts.append(PRESETS[preset])
    if instruction and instruction.strip():
        parts.append(instruction.strip())
    if not parts:
        raise ValueError("give an instruction or a preset")
    return "\n".join(parts)
