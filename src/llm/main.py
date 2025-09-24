#!/usr/bin/env python3
"""
Generate a varied set Y of 'date ideas in Madrid' using the OpenAI API.

Features
- Structured Outputs (JSON Schema) to force a list of strings
- Multiple high-temperature batches for breadth
- Canonicalized hard de-duplication
- Embedding-based MMR reranking for diversity vs. history
- Deterministic option via `seed` (if supported by your model)

Prereqs
  pip install openai numpy

Env
  export OPENAI_API_KEY=...
  # Optional overrides:
  export MODEL_CHAT=gpt-4o-mini-2024-07-18
  export MODEL_EMBED=text-embedding-3-small
"""

import os
import time
import json
import math
import random
from typing import List, Dict, Tuple
import numpy as np
from openai import OpenAI

# ---------- Config ----------
MODEL_CHAT = os.getenv("MODEL_CHAT", "gpt-4o-mini-2024-07-18")
MODEL_EMBED = os.getenv("MODEL_EMBED", "text-embedding-3-small")

# Target size and batch settings
TARGET_K = 40          # total unique ideas to emit
ROUND_N = 8            # choices per API call (breadth)
MAX_ROUNDS = 20        # upper bound in case diversity is hard
TEMPERATURE = 1.2
TOP_P = 0.95
USE_SEED = False       # set True if your chosen chat model supports seed
BASE_SEED = 12345

# MMR / diversity knobs
MMR_LAMBDA = 0.65      # higher favors novelty vs. relevance to prompt
CHUNK_TOPK = 10        # pick up to this many per round after rerank

client = OpenAI()

SCHEMA = {
    "name": "candidates_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 140
                },
                "minItems": 8,
                "maxItems": 32,
                "description": "Distinct, concrete date ideas in Madrid, Spain."
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You output only JSON that conforms to the provided JSON Schema. "
    "Return diverse, specific date ideas in Madrid, Spain. "
    "Each idea must be actionable, concrete, and distinct. "
    "Avoid duplicates, near-duplicates, boilerplate, or generic advice. "
    "Avoid numbered lists or extra narration. Strict JSON only."
)

USER_PROMPT_TEMPLATE = """\
Task: propose fresh date ideas for Madrid.
Constraints:
- Focus on specific venues, neighborhoods, time windows, and twists (e.g., 'golden-hour rooftop at ... with ...', 'off-peak museum wing + tapas crawl in ...', 'night kayak on ... if seasonal', etc.).
- Prefer affordable to mid-range. Include a few seasonal or time-bound picks.
- Exclude anything already seen in the blocklist below.
Blocklist (canonicalized, lowercase): {blocklist}
Return 12–20 ideas.
"""

# ---------- Utilities ----------
def canon(s: str) -> str:
    """Canonicalize a string for de-dup (lowercase, collapse spaces, strip punctuation-like chars)."""
    t = s.strip().lower()
    # lightweight punctuation squash
    for ch in ",.;:!?\n\t\"'`()[]{}|/\\@#$%^&*~":
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    return t

def embed(texts: List[str]) -> np.ndarray:
    """Get embeddings as a 2D numpy array [n, d]."""
    if not texts:
        return np.zeros((0, 1536), dtype=np.float32)
    resp = client.embeddings.create(model=MODEL_EMBED, input=texts)
    vecs = [d.embedding for d in resp.data]
    # Normalize for cosine similarity efficiency
    X = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
    return X / norms

def cosine_max_to_set(C: np.ndarray, H: np.ndarray) -> np.ndarray:
    """For each vector in C, get its max cosine similarity to any vector in H. If H empty, returns zeros."""
    if C.shape[0] == 0:
        return np.zeros((0,), dtype=np.float32)
    if H.shape[0] == 0:
        return np.zeros((C.shape[0],), dtype=np.float32)
    # Cosine since both are normalized
    sims = C @ H.T
    return sims.max(axis=1)

def mmr_select(
    candidates: List[str],
    prompt_anchor_vec: np.ndarray,
    cand_vecs: np.ndarray,
    hist_vecs: np.ndarray,
    k: int,
    lam: float = 0.65,
) -> List[str]:
    """
    MMR variant:
      score = lam * relevance_to_prompt - (1 - lam) * similarity_to_history
    relevance_to_prompt ≈ cosine to anchor (prompt embedding).
    similarity_to_history ≈ max cosine to history set.
    """
    if not candidates:
        return []

    # Compute relevance to prompt as cosine to anchor
    # If anchor absent, use zeros -> neutral
    if prompt_anchor_vec is None or prompt_anchor_vec.size == 0:
        rel = np.zeros((len(candidates),), dtype=np.float32)
    else:
        rel = (cand_vecs @ prompt_anchor_vec.reshape(-1, 1)).ravel()

    repel = cosine_max_to_set(cand_vecs, hist_vecs)
    score = lam * rel - (1.0 - lam) * repel

    idx = np.argsort(-score)[:k]
    return [candidates[i] for i in idx]

def parse_candidates_from_choice(choice) -> List[str]:
    """
    Chat Completions + Structured Outputs returns JSON text in message.content.
    We parse and extract the 'candidates' list.
    """
    content = choice.message.content
    if isinstance(content, list):
        # Some SDKs may return a list of content parts; join as text if needed
        text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
    else:
        text = content or ""
    try:
        obj = json.loads(text)
        arr = obj.get("candidates", [])
        return [s for s in arr if isinstance(s, str)]
    except Exception:
        return []

# ---------- Main generator ----------
def generate_date_ideas_madrid(
    target_k: int = TARGET_K,
    round_n: int = ROUND_N,
    max_rounds: int = MAX_ROUNDS,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    mmr_lambda: float = MMR_LAMBDA,
    per_round_pick: int = CHUNK_TOPK,
    use_seed: bool = USE_SEED,
    base_seed: int = BASE_SEED,
) -> List[str]:
    H_set = set()                # canonicalized history
    H_list: List[str] = []       # original strings
    hist_vecs = np.zeros((0, 1536), dtype=np.float32)

    # Anchor: embed the task itself for a weak 'relevance' signal
    anchor_text = "diverse concrete date ideas in Madrid, Spain with venues, times, seasonal twists"
    anchor_vec = embed([anchor_text])[0:1]
    if anchor_vec.shape[0] == 0:
        anchor_vec = None

    for t in range(max_rounds):
        blocklist = list(sorted(H_set))[:256]  # keep prompt short
        user_prompt = USER_PROMPT_TEMPLATE.format(blocklist=blocklist)

        params = dict(
            model=MODEL_CHAT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": SCHEMA},
            n=round_n,
            temperature=temperature,
            top_p=top_p,
        )
        if use_seed:
            # Only some chat models support 'seed'. Safe to include behind a flag.
            params["seed"] = base_seed + t

        resp = client.chat.completions.create(**params)

        # Collect raw candidates across choices
        raw: List[str] = []
        for ch in resp.choices:
            raw.extend(parse_candidates_from_choice(ch))

        # Hard de-dup vs H
        fresh = []
        for s in raw:
            c = canon(s)
            if c and c not in H_set:
                fresh.append(s)

        # Rerank for novelty and prompt relevance
        if fresh:
            C_vecs = embed(fresh)
            pick = mmr_select(
                candidates=fresh,
                prompt_anchor_vec=anchor_vec[0] if anchor_vec is not None else None,
                cand_vecs=C_vecs,
                hist_vecs=hist_vecs,
                k=min(per_round_pick, len(fresh)),
                lam=mmr_lambda,
            )
        else:
            pick = []

        # Update history
        for s in pick:
            c = canon(s)
            if c not in H_set:
                H_set.add(c)
                H_list.append(s)

        # Update vectors for history incrementally
        if pick:
            hist_add = embed(pick)
            hist_vecs = np.vstack([hist_vecs, hist_add]) if hist_vecs.size else hist_add

        # Done?
        if len(H_list) >= target_k:
            return H_list[:target_k]

        # Small jitter to decorrelate successive rounds batch inference matters
        time.sleep(0.2)

    return H_list[:target_k]

# ---------- CLI ----------
if __name__ == "__main__":
    ideas = generate_date_ideas_madrid()
    print(json.dumps({"date_ideas_madrid": ideas}, ensure_ascii=False, indent=2))
