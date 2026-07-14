"""
routes/chat.py — POST /api/chat and POST /api/chat/stream [SPEC_Phase1 §5.1, §6].

The answer path, shared by both:
    question (+ history + hrm session)
      -> Phase-2 scope guard        [§5.3]
      -> resolve follow-up          (so "and sample_3?" still retrieves the right papers)
      -> retrieve top-k passages    [§5.1 steps 2-3]
      -> build grounded messages    [§5.1 step 4]
      -> llm.chat_llm               [§5.1 step 5]
      -> guardrails (numbers, citations, fabricated references)  [§5.3]
      -> {answer, sources, used_hrm, warnings, followups}

/api/chat        blocks for the whole ~100 s generation and returns one JSON body.
/api/chat/stream emits the same information as Server-Sent Events, token by token.

The guardrails run on the COMPLETE text in both cases. They cannot run on a half-written
answer — a number that looks fabricated mid-sentence may be finished correctly two tokens
later — so in the streaming path they are emitted in a final `done` event, after the text.
"""

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

import llm
from hrm import session
from rag import prompt, retriever

chat_bp = Blueprint("chat", __name__)

MAX_QUESTION_LEN = 2000

# Cap on replayed turns. The frontend sends its whole transcript; a long session must not be
# able to push the evidence out of the model's context window (or blow up the request body).
MAX_HISTORY_MESSAGES = prompt.MAX_HISTORY_TURNS * 2


def _prepare(body: dict):
    """
    Shared front half of both endpoints.

    Returns either ("error", payload, status) or ("ok", context-dict). Splitting it out is
    what keeps the blocking and streaming routes from drifting apart in behaviour — the
    guards, the retrieval and the prompt must be identical, or an answer would depend on
    which endpoint the frontend happened to call.
    """
    question = (body.get("question") or "").strip()

    if not question:
        return "error", {"error": "Missing 'question'."}, 400
    if len(question) > MAX_QUESTION_LEN:
        return "error", {
            "error":   "Question too long.",
            "message": f"Keep the question under {MAX_QUESTION_LEN} characters.",
        }, 400

    history  = _clean_history(body.get("history"))
    hrm_data = session.get(body.get("session_id", ""))
    used_hrm = hrm_data is not None

    # ── Guard 1: Phase-2 scope [§5.3] ────────────────────────────────────────
    # Checked before retrieval and before the LLM: it costs nothing and removes any
    # opportunity for the model to volunteer a primer sequence.
    if prompt.is_design_request(question):
        return "error", {
            "answer":    prompt.PHASE2_REFUSAL,
            "sources":   [],
            "used_hrm":  used_hrm,
            "warnings":  [],
            "blocked":   "phase2_scope",
            "followups": prompt.suggest_followups(hrm_data),
        }, 200

    # ── Retrieve [§5.1 steps 2-3] ────────────────────────────────────────────
    try:
        k = int(body.get("k", retriever.DEFAULT_K))
    except (TypeError, ValueError):
        return "error", {"error": "'k' must be an integer."}, 400

    try:
        # Retrieve on the RESOLVED question: a bare "why?" embeds to nothing useful.
        search_text = prompt.resolve_followup(question, history)
        sources     = retriever.retrieve(search_text, k=max(1, min(10, k)))
    except RuntimeError as exc:
        return "error", {"error": "Retrieval unavailable.", "message": str(exc)}, 503

    # A paper keeps one number for the whole conversation, so the "[1]" in a replayed answer
    # still means the paper it meant when it was written.
    citations = retriever.stabilise_numbers(sources, body.get("citations"))

    # ── Guard 2: grounded or silent [§0] ─────────────────────────────────────
    # No passages AND no HRM table means there is nothing to be grounded in. Calling the LLM
    # here would be asking it to answer from its own weights — precisely what §0 forbids.
    if not sources and not used_hrm:
        return "error", {
            "answer":    prompt.NO_CONTEXT_ANSWER,
            "sources":   [],
            "used_hrm":  False,
            "warnings":  [],
            "blocked":   "no_context",
            "followups": prompt.suggest_followups(None),
        }, 200

    return "ok", {
        "question":  question,
        "history":   history,
        "hrm":       hrm_data,
        "used_hrm":  used_hrm,
        "sources":   sources,
        "citations": citations,
        # Real {role, content} turns, not a transcript pasted into one string — see
        # llm.chat_llm for why that distinction is load-bearing.
        "messages":  prompt.build_messages(question, sources, hrm_data, history),
    }


def _clean_history(raw) -> list[dict]:
    """Keep only well-formed, recent turns. The client is not trusted to send sane data."""
    if not isinstance(raw, list):
        return []

    cleaned = [
        {"role": m["role"], "content": str(m["content"])[:MAX_QUESTION_LEN]}
        for m in raw
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"].strip()
    ]
    return cleaned[-MAX_HISTORY_MESSAGES:]


def _guardrails(answer: str, ctx: dict) -> list[str]:
    return (
        prompt.check_numbers(answer, ctx["hrm"])
        + prompt.check_citations(answer, ctx["sources"])
        + prompt.check_fabricated_references(answer)
        + prompt.check_coverage(ctx["sources"], ctx["hrm"])
    )


def _asked(ctx: dict) -> set[str]:
    """Questions already put to the assistant — never suggest one of them again."""
    prior = {m["content"] for m in ctx["history"] if m["role"] == "user"}
    return prior | {ctx["question"]}


@chat_bp.route("/chat", methods=["POST"])
def chat():
    status, payload, *rest = _prepare(request.get_json(silent=True) or {})
    if status == "error":
        return jsonify(payload), rest[0]

    ctx = payload

    try:
        answer = llm.chat_llm(ctx["messages"], system=prompt.SYSTEM_PROMPT)
    except RuntimeError as exc:
        # Ollama down or model not pulled — the message is actionable, show it as-is.
        return jsonify({"error": "LLM unavailable.", "message": str(exc)}), 503

    return jsonify({
        "answer":    answer,
        "sources":   retriever.to_citations(ctx["sources"]),
        "citations": ctx["citations"],       # client returns this next turn to keep [n] stable
        "used_hrm":  ctx["used_hrm"],
        "warnings":  _guardrails(answer, ctx),
        "followups": prompt.suggest_followups(ctx["hrm"], _asked(ctx)),
    })


@chat_bp.route("/chat/stream", methods=["POST"])
def chat_stream():
    """
    Server-Sent Events. Event sequence:

        meta   {sources, used_hrm}   — sent immediately, so the sources panel fills in
                                       while the model is still thinking
        token  {text}                — repeated, as the model produces them
        done   {warnings, followups} — guardrails, which need the finished answer
        error  {error, message}      — instead of `done` if generation failed

    Errors are delivered as an SSE `error` event, not an HTTP status: by the time generation
    fails the response has already been committed with 200 and the headers are long gone.
    """
    status, payload, *rest = _prepare(request.get_json(silent=True) or {})

    if status == "error":
        # Blocked or malformed — nothing to stream. Send it as a single-shot SSE so the
        # frontend has exactly one code path for this endpoint.
        code = rest[0]
        if code != 200:
            return jsonify(payload), code

        def blocked():
            yield _sse("meta", {"sources": [], "citations": [],
                                "used_hrm": payload["used_hrm"]})
            yield _sse("token", {"text": payload["answer"]})
            yield _sse("done", {
                "warnings":  payload["warnings"],
                "followups": payload["followups"],
                "blocked":   payload["blocked"],
            })

        return Response(stream_with_context(blocked()), mimetype="text/event-stream",
                        headers=_SSE_HEADERS)

    ctx = payload

    def generate():
        yield _sse("meta", {
            "sources":   retriever.to_citations(ctx["sources"]),
            "citations": ctx["citations"],
            "used_hrm":  ctx["used_hrm"],
        })

        parts = []
        try:
            for piece in llm.chat_llm(ctx["messages"], system=prompt.SYSTEM_PROMPT, stream=True):
                parts.append(piece)
                yield _sse("token", {"text": piece})
        except RuntimeError as exc:
            yield _sse("error", {"error": "LLM unavailable.", "message": str(exc)})
            return
        except GeneratorExit:
            # The client disconnected (pressed Stop, closed the tab). Nothing to clean up,
            # and no guardrails to run on a half-answer the user has already discarded.
            raise

        answer = "".join(parts).strip()
        if not answer:
            yield _sse("error", {
                "error":   "Empty response.",
                "message": "The model returned nothing. Try rephrasing the question.",
            })
            return

        # Guardrails only make sense on the finished text [§5.3].
        yield _sse("done", {
            "warnings":  _guardrails(answer, ctx),
            "followups": prompt.suggest_followups(ctx["hrm"], _asked(ctx)),
        })

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers=_SSE_HEADERS)


# Without these, a reverse proxy will happily buffer the whole stream and hand it over in one
# lump at the end — which is exactly the dead screen streaming exists to remove.
_SSE_HEADERS = {
    "Cache-Control":     "no-cache",
    "X-Accel-Buffering": "no",
    "Connection":        "keep-alive",
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@chat_bp.route("/chat/health", methods=["GET"])
def chat_health():
    """Detailed readiness of the chat stack — surfaced in the UI before the first question."""
    from db import store

    ollama = llm.ollama_health()
    chroma = store.chroma_health()
    sqlite = store.sqlite_health()

    return jsonify({
        "ready":    ollama["alive"] and ollama["model_ready"] and chroma["alive"],
        "ollama":   ollama,
        "embedder": llm.embedder_health(),
        "chroma":   chroma,
        "sqlite":   sqlite,
    })
