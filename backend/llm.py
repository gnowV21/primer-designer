"""
llm.py — the single abstraction layer for every LLM / embedding call [SPEC_Phase1 §5.4].

Nothing else in the codebase may talk to Ollama or sentence-transformers directly.
Swapping the model, moving to GPU, or switching to a hosted API is a change to THIS
FILE ONLY.

Two public functions:
    chat_llm(messages, system=..., stream=...)          # generation (Ollama /api/chat, local)
    embed(texts, kind='passage'|'query')                # sentence-transformers, local

Plus health probes used by /api/health.

SPEC_Phase1 §5.4 calls the generation entry point `ask_llm(prompt)`. It is `chat_llm(messages)`
here, and the difference is not cosmetic: a conversation cannot be expressed as one flat prompt
string. Passing a pasted transcript to /api/generate made the model re-answer the PREVIOUS
question; only real {role, content} turns through /api/chat fixed it (see chat_llm). The spec's
actual requirement — ONE place in the codebase talks to the LLM — is unchanged.

Design notes
------------
* Both backends are LAZY. Importing this module must stay cheap and must never fail, because
  backend/app.py imports it at startup and the rest of the primer-designer app has to keep
  working even when Ollama is not installed and torch/sentence-transformers are absent. Failures
  surface at CALL time as RuntimeError with an actionable message, not at import time.
* The embedding model is a process-wide singleton — loading it costs several seconds, so it
  happens once, on first use.
"""

import json
import os
import threading

import requests

# ── Ollama configuration ────────────────────────────────────────────────────
# Ollama's default local REST port; overridable for a remote/GPU host later.
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Qwen2.5 7B Instruct (Q4) — ~4.7 GB RAM, comfortable inside 16 GB alongside the embedder.
#
# SPEC_Phase1 §2 chose a 3B model and §9 anticipated "upgrade to 7B through the abstraction".
# That upgrade is now mandatory, not an optimisation: llama3.2:3b CANNOT HOLD A CONVERSATION.
# Measured on the same question, "And is sample_3 a real variant?", asked one turn after a
# sample_2 answer:
#
#     llama3.2:3b   with no history  -> answers about sample_3   (correct)
#     llama3.2:3b   with history      -> re-answers the sample_2 question   (BROKEN)
#     qwen2.5:7b    with history      -> answers about sample_3, and cites  (correct)
#
# Feeding 3B any transcript makes it drift back to the previous question. Prompt fencing,
# labelling the history as background, and moving from /api/generate to /api/chat with real
# message roles were all tried; none fixed it. It is a capability ceiling.
#
# The cost is honest and real: ~170-220 s per answer versus ~80 s for the 3B, on CPU. A
# chatbot whose follow-ups are broken is not a chatbot, so the latency is the better trade.
# Streaming (see chat_llm) is what makes it bearable.
#
# To go back:  OLLAMA_MODEL=llama3.2:3b  (single-turn questions only).
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# CPU inference is slow: a thorough answer runs ~60-100 s on a 3B and several minutes on a
# 7B (16 GB, no GPU). 180 s cut 7B answers off mid-generation, so the ceiling is set for the
# largest model this abstraction is expected to front rather than the default one.
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

# Context window. SPEC_Phase1 §9 lists "limit context length" as the mitigation for slow
# CPU inference, but 4096 was too tight once the system prompt carried the flag definitions
# and the biology the model needs to explain a result: the HRM table plus 6 abstract chunks
# would push the rules out of the window, and a rule the model cannot see is a rule it does
# not follow. 8192 holds all of it with room to answer.
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# Answer budget. Ollama defaults to a short cap, which truncated explanations mid-sentence
# — the model would state the verdict and get cut off before the mechanism, which is the
# part the user actually needs. 800 tokens is a thorough paragraph or two.
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "800"))

# Low temperature: this is a grounded-citation task, not creative writing.
# Determinism matters more than variety [SPEC_Phase1 §0 "Grounded"].
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.1"))


# ── Embedding configuration ─────────────────────────────────────────────────
# BAAI/bge-small-en-v1.5 — 384-dim, ~130 MB, fast on CPU.
#
# SPEC_Phase1 §2 specified pritamdeka/S-PubMedBert-MS-MARCO on the assumption that a
# BIOMEDICAL encoder would retrieve better on PubMed abstracts. Measured, it does the
# opposite: its embedding space is collapsed. Cosine distance from
# "What does a second melt peak in HRM indicate?" to:
#
#     an HRM paper ................ 0.101
#     an unrelated miRNA paper .... 0.154
#     "I'd like to order a pizza" . 0.211   <-- barely further than the HRM paper
#
# Everything lands in a 0.10-0.21 band, so ranking between papers is noise and no distance
# threshold can separate relevant from irrelevant. That breaks the core guarantee of §0
# ("grounded or silent"): the retriever could not tell when it had found nothing, so it
# always returned five confident-looking sources.
#
# bge-small-en-v1.5 on the same probe: relevant 0.303, pizza 0.567 — a real gap that a
# threshold can act on. Domain vocabulary matters less than contrastive retrieval training.
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# BGE models are trained for ASYMMETRIC search: queries carry this instruction prefix and
# passages do not. Skipping it measurably degrades retrieval, and it is the single reason
# embed() has to know whether it is embedding a question or a document.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_embedder      = None
_embedder_lock = threading.Lock()

_INSTALL_HINT = (
    "Install it with:  pip install sentence-transformers"
)
_OLLAMA_HINT = (
    f"Ollama is not reachable at {OLLAMA_URL}. "
    "Install it from https://ollama.com/download, then run:  "
    f"ollama pull {OLLAMA_MODEL}"
)


# ── Text generation ─────────────────────────────────────────────────────────

def chat_llm(messages: list[dict], system: str | None = None,
             stream: bool = False, **opts):
    """
    Multi-turn generation via Ollama's /api/chat — the ONLY correct way to hold a conversation.

    The first implementation replayed the transcript by pasting it into a single /api/generate
    prompt string. A small model cannot reliably tell "text that happens to contain questions"
    from "the question I must answer", and it showed: asked "And is sample_3 a real variant?"
    one turn after a sample_2 answer, it re-answered the sample_2 question verbatim and never
    mentioned sample_3. Fencing the live question and labelling the transcript as BACKGROUND
    did not fix it.

    /api/chat fixes it structurally. Passing real {role, content} turns lets Ollama apply the
    model's own chat template, which marks turn boundaries with the special tokens the model
    was TRAINED on — and instruction-tuned models are trained to answer the final user message.
    The boundary stops being a hint the model may ignore and becomes part of the tokenisation.

    Args:
        messages: [{role: 'user'|'assistant', content: str}, ...], oldest first, ending on the
                  user turn to answer.
        system:   system rules, sent as the system message.
        stream:   True to yield chunks, False to return the whole answer.
    """
    options = {
        "temperature": OLLAMA_TEMPERATURE,
        "num_ctx":     OLLAMA_NUM_CTX,
        "num_predict": OLLAMA_NUM_PREDICT,
    }
    options.update(opts)

    payload = {
        "model":    OLLAMA_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "stream":   stream,
        "options":  options,
    }

    if not stream:
        r = _post("/api/chat", payload, stream=False)
        answer = (r.json().get("message") or {}).get("content", "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty response.")
        return answer

    return _stream_chat(payload)


def _stream_chat(payload: dict):
    r = _post("/api/chat", payload, stream=True)
    for line in r.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (piece := (chunk.get("message") or {}).get("content")):
            yield piece
        if chunk.get("done"):
            break


def _post(path: str, payload: dict, stream: bool):
    """Shared POST + error translation for both Ollama endpoints."""
    try:
        r = requests.post(
            f"{OLLAMA_URL}{path}", json=payload, timeout=OLLAMA_TIMEOUT, stream=stream
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        raise RuntimeError(_OLLAMA_HINT) from exc

    if r.status_code == 404:
        raise RuntimeError(
            f"Model '{OLLAMA_MODEL}' is not available in Ollama. "
            f"Run:  ollama pull {OLLAMA_MODEL}"
        )
    if r.status_code != 200:
        raise RuntimeError(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")
    return r


# ── Embeddings ──────────────────────────────────────────────────────────────

def _get_embedder():
    """Load the sentence-transformers model once per process (thread-safe)."""
    global _embedder
    if _embedder is not None:
        return _embedder

    with _embedder_lock:
        if _embedder is not None:          # another thread won the race
            return _embedder
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                f"sentence-transformers is not installed. {_INSTALL_HINT}"
            ) from exc

        # First call downloads the model from HuggingFace (~440 MB) and caches it
        # under ~/.cache/huggingface. Subsequent starts are offline.
        _embedder = SentenceTransformer(EMBED_MODEL)
        return _embedder


def embed(texts: list[str], kind: str = "passage") -> list[list[float]]:
    """
    Embed a list of texts into vectors [SPEC_Phase1 §5.4].

    The ONLY place embeddings are produced. Both ingest (indexer.py) and query
    (retriever.py) go through here, which is what guarantees the query vector and the stored
    chunk vectors share one embedding space.

    Args:
        texts: the strings to embed.
        kind:  "passage" (a document chunk being indexed) or "query" (a user question).
               BGE is an asymmetric retriever — the query side takes an instruction prefix
               and the passage side does not. Getting this backwards silently costs accuracy
               without raising anything, which is why it is an explicit argument rather than
               something the caller is trusted to remember.

    Vectors are L2-normalised, so cosine distance is 1 - dot product. The Chroma collection
    is created with hnsw:space=cosine to match.
    """
    if not texts:
        return []
    if kind not in ("passage", "query"):
        raise ValueError(f"kind must be 'passage' or 'query', got {kind!r}")

    if kind == "query" and EMBED_MODEL.lower().startswith("baai/bge"):
        texts = [_BGE_QUERY_PREFIX + t for t in texts]

    model   = _get_embedder()
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vectors]


def embedding_dim() -> int:
    """Vector width of the active embedding model (768 for S-PubMedBert)."""
    return int(_get_embedder().get_sentence_embedding_dimension())


# ── Health probes (used by /api/health) ─────────────────────────────────────

def ollama_health() -> dict:
    """
    Report whether Ollama is running and whether the configured model is pulled.
    Never raises — /api/health must answer even when everything is down.
    """
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code != 200:
            return {"alive": False, "model_ready": False,
                    "error": f"Ollama returned HTTP {r.status_code}"}

        # Ollama reports "llama3.2:3b"; accept a bare "llama3.2" config too.
        names       = [m.get("name", "") for m in r.json().get("models", [])]
        model_ready = any(
            n == OLLAMA_MODEL or n.split(":")[0] == OLLAMA_MODEL.split(":")[0]
            for n in names
        )
        return {
            "alive":       True,
            "model_ready": model_ready,
            "model":       OLLAMA_MODEL,
            "available":   names,
            "error":       None if model_ready else f"Run: ollama pull {OLLAMA_MODEL}",
        }
    except Exception as exc:
        return {"alive": False, "model_ready": False, "model": OLLAMA_MODEL,
                "error": f"{_OLLAMA_HINT} ({type(exc).__name__})"}


def embedder_health() -> dict:
    """
    Report whether the embedding model is importable and loaded.
    Does NOT force a load — that would cost several seconds on every /api/health.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return {"installed": False, "loaded": False, "model": EMBED_MODEL,
                "error": f"sentence-transformers is not installed. {_INSTALL_HINT}"}
    return {"installed": True, "loaded": _embedder is not None,
            "model": EMBED_MODEL, "error": None}
