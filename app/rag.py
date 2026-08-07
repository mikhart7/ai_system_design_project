from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

FAQ_DIR = Path(__file__).resolve().parent.parent / "data" / "faq"


def _load_faq() -> dict[str, str]:
    if not FAQ_DIR.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in FAQ_DIR.glob("*.md")}


_docs = _load_faq()
_doc_ids = list(_docs.keys())
_vectorizer = TfidfVectorizer().fit(list(_docs.values()) or [" "])
_doc_vectors = _vectorizer.transform(list(_docs.values())) if _docs else None


def retrieve(text: str) -> tuple[str | None, str | None, float]:
    """Возвращает (doc_id, текст документа, similarity) для лучшего совпадения в FAQ."""
    if not _docs:
        return None, None, 0.0
    vec = _vectorizer.transform([text])
    sims = cosine_similarity(vec, _doc_vectors)[0]
    best_idx = int(sims.argmax())
    return _doc_ids[best_idx], _docs[_doc_ids[best_idx]], float(sims[best_idx])
