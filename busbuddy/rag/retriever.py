from pathlib import Path
from typing import Dict, List
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from busbuddy.config import KNOWLEDGE_BASE_DIR

SAMPLE_POLICIES = {
    "cancellation_and_refund_policy.txt": (
        "BusBuddy Simulated Cancellation & Refund Policy:\n"
        "1. More than 24 hours before departure: 90% refund of base fare (10% cancellation fee).\n"
        "2. Between 12 hours and 24 hours before departure: 75% refund of base fare.\n"
        "3. Between 2 hours and 12 hours before departure: 50% refund of base fare.\n"
        "4. Less than 2 hours before departure: No refund is permitted.\n"
        "5. Refunds are credited back to the original UPI/card payment source within 3 to 5 working days."
    ),
    "luggage_and_boarding_policy.txt": (
        "BusBuddy Simulated Luggage & Boarding Policy:\n"
        "1. Each passenger is allowed up to 15 kg of check-in luggage and 1 cabin backpack (up to 7 kg) free of charge.\n"
        "2. Passengers must arrive at the boarding point at least 15 minutes before scheduled departure.\n"
        "3. A digital m-ticket on mobile along with a valid government photo ID (Aadhaar, PAN, Driving License, or Passport) is mandatory."
    ),
    "coupon_terms_and_conditions.txt": (
        "BusBuddy Coupon Terms & Conditions:\n"
        "1. Only one coupon code can be applied per ticket booking.\n"
        "2. Percentage discounts are strictly subject to the maximum discount cap specified on the coupon.\n"
        "3. Route-specific coupons (such as BLR200) apply only to the exact source-destination pair and eligible bus category.\n"
        "4. Expired coupons or bookings below the minimum fare threshold are automatically rejected by the billing engine."
    ),
}


def ensure_knowledge_base() -> List[Path]:
    """Create sample policy documents if the knowledge_base folder is empty."""
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(KNOWLEDGE_BASE_DIR.glob("*.txt"))
    if not existing:
        for filename, content in SAMPLE_POLICIES.items():
            (KNOWLEDGE_BASE_DIR / filename).write_text(content, encoding="utf-8")
    return sorted(KNOWLEDGE_BASE_DIR.glob("*.txt"))


class TravelFAQRetriever:
    """FAISS + SentenceTransformers semantic retriever for travel policies."""

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chunks: List[Dict[str, str]] = []
        self.index = None
        self._build_index()

    def _build_index(self):
        files = ensure_knowledge_base()
        for file_path in files:
            text = file_path.read_text(encoding="utf-8").strip()
            # Split into paragraph/rule chunks
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
            for para in paragraphs:
                self.chunks.append({"source": file_path.name, "text": para})

        if not self.chunks:
            return

        texts = [c["text"] for c in self.chunks]
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings.astype(np.float32))

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """Retrieve top_k semantically similar policy rules with similarity scores."""
        if not self.index or not self.chunks:
            return []

        q_emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(q_emb)
        scores, indices = self.index.search(q_emb.astype(np.float32), top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score > 0.25:
                results.append({
                    "source": self.chunks[idx]["source"],
                    "text": self.chunks[idx]["text"],
                    "score": round(float(score), 3),
                })
        return results


_retriever_instance = None


def get_retriever() -> TravelFAQRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = TravelFAQRetriever()
    return _retriever_instance


def query_travel_faq(question: str) -> Dict:
    """Retrieve grounded policy snippets for a travel FAQ query."""
    retriever = get_retriever()
    matches = retriever.search(question, top_k=3)
    if not matches:
        return {
            "found": False,
            "answer": "This information is unavailable in the BusBuddy travel policy knowledge base.",
            "sources": [],
        }
    return {
        "found": True,
        "matches": matches,
        "sources": list({m["source"] for m in matches}),
    }