#!/usr/bin/env python3
"""
Generate a varied set of contextual suggestions using the OpenAI API.

Features
- Structured Outputs (JSON Schema) to force a list of strings
- Multiple high-temperature batches for breadth
- Canonicalized hard de-duplication
- Embedding-based MMR reranking for diversity vs. history
- Deterministic option via `seed` (if supported by your model)
- Configurable context for any type of suggestions

Prereqs
  pip install openai numpy

Env
  export OPENAI_API_KEY=...
  # Optional overrides:
  export MODEL_CHAT=gpt-4o-mini-2024-07-18
  export MODEL_EMBED=text-embedding-3-small

Usage:
  python main.py "date ideas in Madrid"
  python main.py "healthy breakfast recipes"
  python main.py "creative writing prompts for sci-fi stories"
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
MODEL_CHAT = os.getenv("MODEL_CHAT", "gpt-5-nano")
MODEL_EMBED = os.getenv("MODEL_EMBED", "text-embedding-3-small")

# Target size and batch settings
TARGET_K = 20 # total unique ideas to emit
ROUND_N = 5            # choices per API call (breadth)
MAX_ROUNDS = 20        # upper bound in case diversity is hard
TEMPERATURE = 1.2
TOP_P = 0.95
USE_SEED = True # set True if your chosen chat model supports seed
BASE_SEED = 12345

# MMR / diversity knobs
MMR_LAMBDA = 0.8      # higher favors novelty vs. relevance to prompt
CHUNK_TOPK = 10        # pick up to this many per round after rerank

# Logprob scoring weights
ALPHA = 0.3           # weight for logprob score (confidence)
BETA = 0.2            # weight for rarity bonus
LAM = 0.5             # weight for diversity (1 - lam for similarity penalty)

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
                    "maxLength": 140 # expand for whatever longer context
                },
                "minItems": 8,
                "maxItems": 32,
                "description": "Distinct, concrete suggestions for the given context."
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    },
}

def get_system_prompt(context: str) -> str:
    return (
        "You output only JSON that conforms to the provided JSON Schema. "
        f"Return diverse, specific suggestions for: {context}. "
        "Each suggestion must be actionable, concrete, and distinct. "
        "Avoid duplicates, near-duplicates, boilerplate, or generic advice. "
        "Avoid numbered lists or extra narration. Strict JSON only."
    )

def get_user_prompt_template(context: str) -> str:
    return f"""\
Task: propose fresh suggestions for {context}.
Constraints:
- Focus on specific, actionable, and detailed suggestions with relevant context and specifics.
- Provide concrete, implementable ideas that are distinct from each other.
- Include variety in approach, timing, or method where applicable.
- Exclude anything already seen in the blocklist below.
Blocklist (canonicalized, lowercase): {{blocklist}}
Return 12–20 suggestions.
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
    logprob_scores: List[float] = None,
    rarity_scores: List[float] = None,
    alpha: float = 0.3,
    beta: float = 0.2,
) -> List[str]:
    """
    Enhanced MMR variant:
      score = lam * relevance_to_prompt - (1 - lam) * similarity_to_history + alpha * logprob_score + beta * rarity_score
    relevance_to_prompt ≈ cosine to anchor (prompt embedding).
    similarity_to_history ≈ max cosine to history set.
    logprob_score ≈ model confidence in the generation.
    rarity_score ≈ inverse frequency bonus for diverse selections.
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

    # Base MMR score
    score = lam * rel - (1.0 - lam) * repel

    # Add logprob confidence score
    if logprob_scores:
        logprob_array = np.array(logprob_scores[:len(candidates)], dtype=np.float32)
        # Normalize logprobs (they are typically negative, so we make them positive and normalize)
        if len(logprob_array) > 0:
            min_logprob = np.min(logprob_array)
            max_logprob = np.max(logprob_array)
            if max_logprob > min_logprob:
                normalized_logprobs = (logprob_array - min_logprob) / (max_logprob - min_logprob)
            else:
                normalized_logprobs = np.ones_like(logprob_array)
            score += alpha * normalized_logprobs

    # Add rarity bonus
    if rarity_scores:
        rarity_array = np.array(rarity_scores[:len(candidates)], dtype=np.float32)
        score += beta * rarity_array

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

def extract_logprobs_from_choice(choice) -> float:
    """
    Extract average logprob from a choice for confidence scoring.
    Returns the average logprob across all tokens in the response.
    """
    if not hasattr(choice, 'logprobs') or not choice.logprobs or not choice.logprobs.content:
        return 0.0

    logprobs = [token.logprob for token in choice.logprobs.content if token.logprob is not None]
    return np.mean(logprobs) if logprobs else 0.0

def compute_rarity_scores(candidates: List[str], all_candidates: List[str]) -> List[float]:
    """
    Compute rarity bonus for candidates based on frequency in the batch.
    Less frequent candidates get higher scores.
    """
    if not candidates or not all_candidates:
        return [0.0] * len(candidates)

    # Count frequency of each candidate (canonicalized)
    freq_count = {}
    for cand in all_candidates:
        canonical = canon(cand)
        freq_count[canonical] = freq_count.get(canonical, 0) + 1

    # Compute rarity scores (inverse frequency)
    rarity_scores = []
    total_candidates = len(all_candidates)
    for cand in candidates:
        canonical = canon(cand)
        frequency = freq_count.get(canonical, 1)
        # Higher rarity score for less frequent items
        rarity_score = math.log(total_candidates / frequency) if frequency > 0 else 0.0
        rarity_scores.append(rarity_score)

    # Normalize to 0-1 range
    if rarity_scores:
        min_score, max_score = min(rarity_scores), max(rarity_scores)
        if max_score > min_score:
            rarity_scores = [(s - min_score) / (max_score - min_score) for s in rarity_scores]

    return rarity_scores

# ---------- Main generator ----------
def generate_contextual_suggestions(
    context: str,
    target_k: int = TARGET_K,
    round_n: int = ROUND_N,
    max_rounds: int = MAX_ROUNDS,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    mmr_lambda: float = MMR_LAMBDA,
    per_round_pick: int = CHUNK_TOPK,
    use_seed: bool = USE_SEED,
    base_seed: int = BASE_SEED,
    alpha: float = ALPHA,
    beta: float = BETA,
    lam: float = LAM,
) -> List[str]:
    H_set = set()                # canonicalized history
    H_list: List[str] = []       # original strings
    hist_vecs = np.zeros((0, 1536), dtype=np.float32)

    # Anchor: embed the task itself for a weak 'relevance' signal
    anchor_text = f"diverse concrete suggestions for {context} with specific details and actionable advice"
    anchor_vec = embed([anchor_text])[0:1]
    if anchor_vec.shape[0] == 0:
        anchor_vec = None

    user_prompt_template = get_user_prompt_template(context)
    system_prompt = get_system_prompt(context)

    for t in range(max_rounds):
        blocklist = list(sorted(H_set))[:256]  # keep prompt short
        user_prompt = user_prompt_template.format(blocklist=blocklist)

        params = dict(
            model=MODEL_CHAT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": SCHEMA},
            n=round_n,
            temperature=temperature,
            top_p=top_p,
            logprobs=True,
            top_logprobs=5,
        )
        if use_seed:
            # Only some chat models support 'seed'. Safe to include behind a flag.
            params["seed"] = base_seed + t

        resp = client.chat.completions.create(**params)

        # Collect raw candidates across choices with logprob scores
        raw: List[str] = []
        candidate_logprobs: List[float] = []
        for ch in resp.choices:
            candidates = parse_candidates_from_choice(ch)
            choice_logprob = extract_logprobs_from_choice(ch)
            raw.extend(candidates)
            # Assign the same logprob score to all candidates from this choice
            candidate_logprobs.extend([choice_logprob] * len(candidates))

        # Hard de-dup vs H and preserve logprob scores
        fresh = []
        fresh_logprobs = []
        for i, s in enumerate(raw):
            c = canon(s)
            if c and c not in H_set:
                fresh.append(s)
                fresh_logprobs.append(candidate_logprobs[i] if i < len(candidate_logprobs) else 0.0)

        # Rerank for novelty and prompt relevance
        if fresh:
            C_vecs = embed(fresh)
            # Compute rarity scores for this batch
            rarity_scores = compute_rarity_scores(fresh, raw)
            pick = mmr_select(
                candidates=fresh,
                prompt_anchor_vec=anchor_vec[0] if anchor_vec is not None else None,
                cand_vecs=C_vecs,
                hist_vecs=hist_vecs,
                k=min(per_round_pick, len(fresh)),
                lam=lam,
                logprob_scores=fresh_logprobs,
                rarity_scores=rarity_scores,
                alpha=alpha,
                beta=beta,
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
            print(f"Round {t+1}: got {len(raw)} raw, {len(fresh)} fresh, picked {len(pick)}, total {len(H_list)}")


        # Done?
        if len(H_list) >= target_k:
            return H_list[:target_k]

        # Small jitter to decorrelate successive rounds batch inference matters
        #time.sleep(0.1)

    return H_list[:target_k]

# ---------- CLI ----------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        context = sys.argv[1]
    else:
        context = "date ideas in Madrid, Spain"  # default fallback

    ideas = generate_contextual_suggestions(context)

    # Create a clean key for the JSON output
    key = context.lower().replace(" ", "_").replace(",", "").replace("'", "").replace('"', "")
    key = ''.join(c for c in key if c.isalnum() or c == '_')

    print(json.dumps({key: ideas}, ensure_ascii=False, indent=2))
