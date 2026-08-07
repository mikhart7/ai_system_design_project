import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\- ]{7,}\d")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "system:",
    "you are now",
    "disregard the above",
    "забудь предыдущие инструкции",
    "игнорируй инструкции",
]


def check_pii(text: str) -> list[str]:
    flags = []
    if EMAIL_RE.search(text):
        flags.append("email")
    if PHONE_RE.search(text):
        flags.append("phone")
    if CARD_RE.search(text):
        flags.append("card_number")
    return flags


def check_prompt_injection(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in INJECTION_PATTERNS if p in lowered]
