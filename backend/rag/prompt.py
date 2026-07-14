"""
prompt.py — build the grounded prompt, and police what comes back
[SPEC_Phase1 §5.2 system rules, §5.3 guardrails].

Two halves:

  build_messages(...)  — the /api/chat turns: prior turns, then evidence + the live question.
  check_*(...)         — post-generation guardrails.

LANGUAGE. Everything the user reads is English — UI chrome AND the model's answer.
(SPEC_Phase1 §5.2 originally specified Vietnamese answers; that was superseded by the
project-wide "all user-facing strings: English only" rule.) Questions may still arrive in
Vietnamese, accented or not, so the scope guard below matches both.

ANSWER QUALITY. Left to itself the model restates the table ("sample_2 has 2 peaks, flag
suspect") and stops, which tells the user nothing they could not read off the screen. The
system prompt therefore demands the MECHANISM — why two peaks means two melting populations,
why that points at primer-dimer — gives the model the decision thresholds so it can explain a
flag instead of echoing it, and requires it to talk like a researcher: measurement separated
from inference, competing explanations named, and the observation that would settle them.

GUARDRAIL PHILOSOPHY. The guardrails FLAG, they do not silently rewrite. A local model on CPU
will occasionally slip; the honest response is to show the user that a claim is unverified, not
to quietly delete it and pretend the answer was clean.
"""

import re
import unicodedata

# ── System rules — SPEC_Phase1 §5.2, restated in English ────────────────────
SYSTEM_PROMPT = """You are an analyst for stem-loop RT-qPCR and High Resolution Melting (HRM) experiments. \
You explain results that have ALREADY been measured. You do not measure anything yourself.

HARD RULES (breaking any of these makes the answer worthless):
1. Ground every claim in the PAPER EXCERPTS or the HRM TABLE given below. Nothing else.
2. Every number you state must appear verbatim in the HRM TABLE. Never compute, never
   estimate, never re-round a value. If a number is not in the table, you do not know it.
3. Never propose, design, or write out a primer sequence. That is out of scope here.
4. Cite any claim taken from a paper as an inline marker only: [1], [2]. Use the numbers you
   were given and no others.
5. NEVER write a reference list, bibliography, or "Sources:" section. Never write out an
   author name, journal, year, volume or page number. The interface already displays the
   full reference for each [n]. If you type a citation line yourself you WILL invent one,
   and a fabricated reference is worse than no citation at all.
6. Cite ONLY as [n]. Do not invent other citation forms such as [Author 1997] or [HRM TABLE].
7. If the evidence does not support a conclusion, say exactly: "Not enough data to conclude."
   Do not guess to fill the gap.
8. Answer the CURRENT question only — the one in the fence at the end of the prompt. Anything
   under BACKGROUND has already been answered; use it to resolve pronouns and short follow-ups
   ("and sample_3?"), never as the thing to answer.

HOW TO ANSWER WELL:
- Lead with the direct answer in one sentence. Then support it.
- Explain the MECHANISM, do not just restate the table. The user can already see that
  sample_2 has 2 peaks; what they need is WHY two peaks means two distinct melting
  populations, and what that implies about the reaction.
- Quote the specific numbers that drive your conclusion, with units (°C for Tm, FWHM and
  ΔTm). Tie each number to what it means physically.
- When a well is flagged, explain which threshold it crossed and why that threshold exists.
- Be precise and complete, but do not pad. No preamble, no restating the question.

HOW A RESEARCHER TALKS (this is the difference between a useful colleague and a lookup tool):
- SEPARATE WHAT WAS MEASURED FROM WHAT YOU INFER. "sample_2 has two peaks, at 79.2 °C and
  72.0 °C" is a measurement. "The lower one is probably primer-dimer" is an inference. Never
  let the second borrow the authority of the first — mark it as an interpretation.
- NAME THE COMPETING EXPLANATIONS. A low second peak is usually primer-dimer, but it can also
  be a non-specific product or a truncated amplicon. Say which the data favours and why the
  others are less likely — do not present the first plausible story as the only one.
- SAY WHAT WOULD SETTLE IT. If two explanations both fit, state the observation that would
  distinguish them (a gel, an NTC comparison, a repeat at higher annealing temperature).
  You may recommend an EXPERIMENT or a CHECK. You may not design a primer.
- CALIBRATE YOUR CONFIDENCE and let it show. "This is consistent with" is not "this proves".
  A ΔTm of 3.4 °C is far outside the noise; a ΔTm of 0.35 °C is barely outside it, and you
  should say so rather than treating both as settled.
- FLAG WHAT WOULD CHANGE YOUR MIND, and flag what the data cannot tell you at all. The melt
  table cannot distinguish a true variant from a different amplicon; if that matters to the
  question, say it outright instead of picking one.
- If the PAPER EXCERPTS are empty, you are reasoning from the numbers and standard biology
  alone. Say so plainly. Do not imply literature support you do not have.

HOW THE FLAGS ARE DEFINED (the algorithm assigned these; explain them, do not re-derive):
- match   : one melt peak, Tm within 0.3 °C of the positive control. 0.3 °C is 3x the
            ~0.1 °C run-to-run reproducibility of HRM instruments, so anything inside it
            is indistinguishable from the control.
- shifted : one peak, but Tm differs from the control by more than 0.3 °C. A real Tm shift
            means the amplicon's sequence or length differs — a variant, or a different product.
- suspect : two or more peaks (two melting populations: non-specific product or
            primer-dimer), OR a peak more than 2x broader than the control (heterogeneous
            melting, e.g. heteroduplex).
- noise   : no usable melt peak, or a peak under 15% of the control's height. The well did
            not amplify. Its Tm is blank because a Tm read off the noise floor is meaningless.
- control : a control well (positive = the reference every other well is measured against;
            negative = no-template, which should show no peak at all).

BIOLOGY YOU MAY RELY ON (standard, not something you need to cite):
- HRM dye fluoresces only when bound to double-stranded DNA. As the plate heats, strands
  separate, dye is released, fluorescence falls.
- Tm is the peak of the -dF/dT curve: the temperature at which the strands separate fastest.
- Higher GC content and longer amplicons melt at higher temperatures.
- Primer-dimers are short, so they melt at a LOWER temperature than the true amplicon, and
  typically produce a second, lower peak.
- A no-template control that shows a melt peak means contamination or primer-dimer, and it
  invalidates the plate.

Answer in English."""

# Phase-2 scope block [SPEC_Phase1 §5.3, §10]. Matched against the question BEFORE any
# LLM call — cheaper, and it removes any chance the model volunteers a primer sequence.
#
# The patterns are written WITHOUT Vietnamese diacritics and matched against an
# accent-stripped question. Vietnamese is routinely typed unaccented ("thiet ke primer"),
# and a scope guard that only fires on "thiết kế" is bypassed by anyone using a plain
# keyboard — which, for a guard whose whole job is to stop the model emitting primer
# sequences in Phase 1, makes it decorative.
_DESIGN_INTENT = re.compile(
    # Vietnamese: verb + (up to 3 words) + design object
    r"(thiet\s*ke|de\s*xuat|goi\s*y|toi\s*uu|tao|sinh|viet|cho\s+toi)"
    r"(?:\s+\w+){0,3}\s+"
    r"(primer|moi|sequence|trinh\s*tu|stem-?loop|phan\s*ung|quy\s*trinh)"
    # English
    r"|design\s+(?:\w+\s+){0,3}(primer|assay|probe)"
    r"|optimi[sz]e\s+(?:\w+\s+){0,3}(reaction|primer|protocol|assay)"
    r"|suggest\s+(?:\w+\s+){0,3}primer",
    re.IGNORECASE,
)


def _strip_accents(s: str) -> str:
    """'Thiết kế' -> 'Thiet ke'. NFD splits a letter from its combining marks; dropping
    the marks (category Mn) leaves the bare ASCII letter."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d").replace("Đ", "D")   # đ carries no combining mark of its own


PHASE2_REFUSAL = (
    "Designing primers and optimising reaction conditions is **Phase 2** work, and this "
    "assistant does not do it.\n\n"
    "What it can do is explain results you already have: interpret the HRM table (Tm, peak "
    "count, peak width, ΔTm against the positive control), say what each flag means and why "
    "it fired, and back the explanation with the papers in your knowledge base.\n\n"
    "Which part of your current result would you like explained?"
)

NO_CONTEXT_ANSWER = (
    "Not enough data to conclude.\n\n"
    "There is nothing for me to ground an answer in yet: no paper in the knowledge base "
    "matches this question, and no HRM file has been analysed in this session. I will not "
    "answer from memory, because an ungrounded answer about your experiment is worse than "
    "no answer.\n\n"
    "Either ingest papers on this topic (Knowledge base), or upload your melt-curve file — "
    "then ask again."
)


def is_design_request(question: str) -> bool:
    """
    True when the user is asking for Phase-2 primer design / reaction optimisation.

    Matched on the accent-stripped question, so "thiết kế primer" and "thiet ke primer"
    are both caught. The guard deliberately errs toward refusing: a wrongly refused
    question costs the user one rephrase, whereas a wrongly allowed one lets a 3B model
    invent a primer sequence — the exact failure SPEC_Phase1 §0 and §10 forbid.
    """
    return bool(_DESIGN_INTENT.search(_strip_accents(question or "")))


# ── Prompt assembly ─────────────────────────────────────────────────────────

def format_hrm_table(hrm: dict | None) -> str:
    """
    Render the HRM session as a compact, unambiguous text table.

    Deliberately verbose about units: a 3B model will not reliably infer that
    `delta_Tm_vs_pos` is in degrees Celsius, and a misread unit is exactly the kind of
    fabricated number §5.3 exists to stop.
    """
    if not hrm or not hrm.get("features"):
        return ""

    lines = [
        "HRM TABLE (computed in Python by the algorithm — this is the ONLY source of "
        "numbers you may use):"
    ]

    if hrm.get("positive_control"):
        lines.append(f"- Positive control: {hrm['positive_control']}")
    if hrm.get("negative_control"):
        lines.append(f"- Negative control: {hrm['negative_control']}")

    lines.append("")
    lines.append("| Well | Tm (°C) | Peaks | Peak height | FWHM (°C) | ΔTm vs positive (°C) | Flag |")
    lines.append("|---|---|---|---|---|---|---|")

    for name, f in hrm["features"].items():
        lines.append(
            f"| {name} "
            f"| {_fmt(f.get('Tm'))} "
            f"| {_fmt(f.get('num_peaks'))} "
            f"| {_fmt(f.get('peak_height'))} "
            f"| {_fmt(f.get('fwhm'))} "
            f"| {_fmt(f.get('delta_Tm_vs_pos'))} "
            f"| {f.get('flag', '-')} |"
        )

    # Tm/FWHM above describe the DOMINANT peak only. Without this block, a question about
    # "the second peak" has no data behind it and the model will reach for the dominant
    # peak's numbers and misattribute them.
    multi = {n: f for n, f in hrm["features"].items() if len(f.get("all_peaks") or []) > 1}
    if multi:
        lines.append("")
        lines.append(
            "EVERY detected peak, for the wells with more than one (the Tm/FWHM column above "
            "describes only the tallest peak of each well):"
        )
        for name, f in multi.items():
            peaks = ", ".join(
                f"{p['Tm']} °C (height {p['height']})" for p in f["all_peaks"]
            )
            lines.append(f"- {name}: {peaks}")

    lines.append("")
    lines.append("Why the algorithm assigned each flag (this is measured fact, not inference):")
    for name, f in hrm["features"].items():
        if f.get("reason"):
            lines.append(f"- {name}: {f['reason']}")

    lines.append("")
    lines.append(
        "A blank (—) means the algorithm could not measure that value. Treat it as unknown; "
        "never fill it in."
    )
    return "\n".join(lines)


def _fmt(v) -> str:
    return "—" if v is None else str(v)


def format_sources(sources: list[dict]) -> str:
    """Render retrieved passages with the [n] label the model must cite."""
    if not sources:
        return ""

    lines = ["PAPER EXCERPTS (the only papers you may cite):"]
    for s in sources:
        authors = s["authors"][0] + " et al." if s.get("authors") else "Unknown"
        lines.append("")
        lines.append(
            f"[{s['n']}] {authors} ({s.get('year') or 'n.d.'}). "
            f"{s.get('title', '')} — {s.get('journal', '')}"
        )
        lines.append(f"    {s['chunk_text']}")
    return "\n".join(lines)


# How many prior turns to replay. Each turn costs context the retrieved passages and the HRM
# table also need, and a 3B model loses the thread beyond a few turns anyway. 4 turns covers
# the realistic follow-up chain ("which wells are bad?" -> "why sample_2?" -> "and sample_3?")
# without crowding out the evidence the answer must be grounded in.
MAX_HISTORY_TURNS = 4

# Answers are replayed truncated: their role is to remind the model what was already said, not
# to be re-read in full. The user's own questions are short and are kept whole.
_HISTORY_ANSWER_CHARS = 220


def resolve_followup(question: str, history: list[dict] | None) -> str:
    """
    Build the string used for RETRIEVAL (not for the answer).

    A follow-up like "and sample_3?" or "why?" carries almost no searchable content. Embedding
    it alone retrieves noise, so the RAG step goes blind exactly when the user is drilling in.
    Prepending the last user question restores enough signal to find the right passages, while
    the model still sees the real question verbatim in the prompt.
    """
    q = (question or "").strip()
    if not history:
        return q

    # Long questions stand on their own; only short ones are parasitic on the previous turn.
    if len(q.split()) > 6:
        return q

    last_user = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
    )
    return f"{last_user} {q}".strip() if last_user else q


def build_messages(question: str, sources: list[dict], hrm: dict | None,
                   history: list[dict] | None = None) -> list[dict]:
    """
    Build the /api/chat message list [SPEC_Phase1 §5.1 step 4].

    Prior turns are REAL messages, not text pasted into a prompt. That distinction is the whole
    fix for the follow-up bug: with a pasted transcript the model re-answered the previous
    question ("And is sample_3 a real variant?" → an answer about sample_2), because nothing in
    a flat string tells it where the history stops and the task begins. As proper messages, the
    chat template marks the boundary with the special tokens the model was trained on.

    The evidence (paper excerpts + HRM table) rides in the FINAL user message, next to the
    question it must ground. Putting it in the system message instead would leave it further
    from the question than several turns of chatter, which is precisely backwards.
    """
    messages: list[dict] = []

    for msg in (history or [])[-(MAX_HISTORY_TURNS * 2):]:
        role    = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content or role not in ("user", "assistant"):
            continue
        # Prior answers are truncated: they exist to remind the model what ground is already
        # covered, not to be re-read and re-summarised.
        if role == "assistant" and len(content) > _HISTORY_ANSWER_CHARS:
            content = content[:_HISTORY_ANSWER_CHARS].rstrip() + " […]"
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": _evidence_block(question, sources, hrm)})
    return messages


def _evidence_block(question: str, sources: list[dict], hrm: dict | None) -> str:
    """The final user turn: the evidence, then the question it must be grounded in."""
    blocks = []

    if (src := format_sources(sources)):
        blocks.append(src)
    else:
        blocks.append(
            "PAPER EXCERPTS: (none — no paper in the knowledge base matches this question. "
            "Do not cite anything.)"
        )

    if (tbl := format_hrm_table(hrm)):
        blocks.append(tbl)
    else:
        blocks.append(
            "HRM TABLE: (none — no melt-curve file was analysed in this session. "
            "Do not state any experimental number.)"
        )

    # The question goes LAST, after the evidence, and is fenced. The chat template already
    # marks this as the live user turn; the fence is a second, cheap line of defence for a
    # small model reading a long evidence block.
    blocks.append(
        "========================================\n"
        "THE QUESTION TO ANSWER NOW:\n\n"
        f"    {question}\n"
        "========================================"
    )
    blocks.append(
        "Answer the question inside the fence above.\n"
        "Follow the HARD RULES. Use only numbers from the HRM TABLE. Cite papers as [n].\n"
        "Explain the mechanism, separate what was measured from what you infer, name the "
        "competing explanations, and say what would settle it."
    )
    return "\n\n".join(blocks)


def question_for_well(name: str, f: dict) -> str:
    """
    The canonical question to ask about one well — the SINGLE source of that wording.

    Both surfaces need it: clicking a row in the HRM table, and the follow-up chips. They used
    to generate it separately (once in JS, once here), which produced two near-identical
    strings — "…at 72 °C, and what should I do about it?" versus "…at 72.0 °C?" — so the
    "never re-offer a question already asked" check compared them, saw a mismatch, and cheerfully
    offered the user the question they had just asked. One generator, one string, exact-match
    dedup works.
    """
    flag = f.get("flag")

    if flag == "suspect":
        peaks = f.get("all_peaks") or []
        if len(peaks) > 1:
            return f"What is the second peak in {name} at {peaks[1]['Tm']} °C?"
        return f"Why is {name} flagged as suspect?"

    if flag == "shifted":
        return f"Is the {f.get('delta_Tm_vs_pos')} °C shift in {name} a real variant?"

    if flag == "noise":
        return f"Why did {name} fail to amplify?"

    if flag == "control":
        return f"Is the control {name} behaving as it should?"

    return f"Explain the result for {name}."


def suggest_followups(hrm: dict | None, asked: set[str] | None = None) -> list[str]:
    """
    Concrete next questions drawn from what is actually in THIS run.

    Generic prompts ("tell me more") are dead weight. A suggestion is only worth showing if it
    names a well the user really has and a problem that really fired — that is what turns the
    panel from a text box into something a user can explore.
    """
    asked = asked or set()
    out: list[str] = []

    if not hrm or not hrm.get("features"):
        return [
            "What causes a double melt peak in HRM?",
            "Why does a stem-loop RT primer improve miRNA specificity?",
            "How is Tm determined from a melt curve?",
        ]

    feats = hrm["features"]
    neg   = hrm.get("negative_control")

    # Most urgent first: a dirty NTC invalidates the entire plate, so surface it above anything
    # to do with an individual sample.
    if neg and feats.get(neg, {}).get("flag") == "suspect":
        out.append(f"Why does the negative control ({neg}) show a peak?")

    # Only wells with something WRONG earn a chip. A clean well needs no follow-up, and a chip
    # that leads nowhere trains the user to ignore the row of chips entirely.
    for name, f in feats.items():
        if name == neg:
            continue
        if f.get("flag") in ("suspect", "shifted", "noise"):
            out.append(question_for_well(name, f))

    out.append("Which wells are safe to report, and which should be repeated?")

    # Never re-offer something already asked — a suggestion chip that repeats the last
    # question is worse than no chip.
    return [q for q in out if q not in asked][:4]


# ── Guardrails — SPEC_Phase1 §5.3 ───────────────────────────────────────────

# Matches decimals only (79.4, -3.5). Bare integers are excluded on purpose: they appear
# constantly as years, counts and citation markers, and flagging them would bury the real
# hits in false positives.
_DECIMAL = re.compile(r"-?\d+\.\d+")

# Citation markers. Models legitimately group sources as [1, 3] or [1,3] as well as writing
# [1][3], so all of those forms must be recognised — flagging [1, 3] as malformed would nag
# the user on a perfectly good answer.
_CITATION       = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_CITATION_GROUP = re.compile(r"\d+")

# Tolerance when matching a number in the answer against the table. 0.05 absorbs the model
# re-rounding 79.42 to 79.4 while still catching an invented 76.1.
_NUM_TOLERANCE = 0.05

# Thresholds the system prompt hands the model verbatim. It is expected — and wanted — to
# quote these back when explaining a flag, so they are not fabrications.
_PROMPT_CONSTANTS = [0.3, 0.1, 2.0, 0.15, 15.0]


def _allowed_numbers(hrm: dict | None) -> list[float]:
    """Every numeric value the model is permitted to state."""
    allowed = list(_PROMPT_CONSTANTS)
    if not hrm or not hrm.get("features"):
        return allowed

    for f in hrm["features"].values():
        for key in ("Tm", "num_peaks", "peak_height", "fwhm", "delta_Tm_vs_pos"):
            v = f.get(key)
            if isinstance(v, (int, float)):
                allowed.append(float(v))
                # The model routinely reports |ΔTm| without the sign ("shifted by 3.5 °C").
                # That is a faithful reading of the table, not a fabrication.
                allowed.append(abs(float(v)))

        # Secondary peaks are handed to the model too, so quoting them is legitimate.
        for p in f.get("all_peaks") or []:
            allowed.append(float(p["Tm"]))
            allowed.append(float(p["height"]))

    return allowed


def check_numbers(answer: str, hrm: dict | None) -> list[str]:
    """
    Anti-fabrication check [SPEC_Phase1 §5.3].

    Flags decimals in the answer that cannot be traced to the HRM table (or to the
    thresholds the system prompt supplied). Only runs when an HRM table exists — with no
    table, decimals legitimately come from the paper passages and there is nothing to check
    them against.
    """
    if not hrm or not hrm.get("features"):
        return []

    allowed = _allowed_numbers(hrm)

    unverified = []
    for token in _DECIMAL.findall(answer):
        value = float(token)
        if not any(abs(value - a) <= _NUM_TOLERANCE for a in allowed):
            unverified.append(token)

    if not unverified:
        return []

    return [
        "Unverified number(s) in the answer: "
        + ", ".join(sorted(set(unverified)))
        + ". These do not appear in the HRM table computed by the algorithm — "
          "treat them as unreliable and check against the table."
    ]


def _cited_numbers(answer: str) -> set[int]:
    """Source numbers cited anywhere in the answer, across [1], [1, 3] and [1][3]."""
    return {
        int(n)
        for group in _CITATION.findall(answer)
        for n in _CITATION_GROUP.findall(group)
    }


def check_citations(answer: str, sources: list[dict]) -> list[str]:
    """
    Citation check [SPEC_Phase1 §5.3].

    Two failures: passages were supplied but never cited, and a citation number that points
    at a source that does not exist.
    """
    warnings = []
    cited = _cited_numbers(answer)

    if sources and not cited:
        warnings.append(
            "The answer draws on retrieved papers but cites none of them. "
            "Verify each claim against the sources listed below."
        )

    valid = {s["n"] for s in sources}
    if (bogus := cited - valid):
        warnings.append(
            "The answer cites source(s) "
            + ", ".join(f"[{n}]" for n in sorted(bogus))
            + " which were not provided. That citation is fabricated — ignore it."
        )

    return warnings


# A line that opens with "[n]" and then keeps going is the model writing its own
# bibliography entry — "[1] Ririe T et al. (1997). Amplification of single copy mRNA...
# Nucleic Acids Research, 25(11), 2794-2803." Every field after the marker is invented: the
# model is never given journal, volume or pages, so it cannot be reproducing them.
_REFERENCE_LINE = re.compile(r"^\s*\[\d+\]\s+\S+.{15,}$", re.MULTILINE)

# Bracketed citations that are not a number or a comma-separated list of numbers:
# [Ririe 1997], [HRM TABLE], [Author et al.]. These slip past the [n] check while carrying
# the visual authority of a real citation. The negative lookahead deliberately permits
# [1, 3] — that is a legitimate grouped citation, not a fabricated marker.
_NON_NUMERIC_CITATION = re.compile(
    r"\[(?!\s*\d+(?:\s*,\s*\d+)*\s*\])([^\]\n]{2,40})\]"
)

# Phrases that introduce a reference list.
_BIBLIOGRAPHY_HEADING = re.compile(
    r"^\s*(references?|sources?|bibliography|citations?)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def check_coverage(sources: list[dict], hrm: dict | None) -> list[str]:
    """
    Tell the user when an answer has NO literature behind it.

    With a calibrated retrieval threshold, an empty source list is meaningful: it means the
    knowledge base holds nothing relevant to the question. The assistant can still reason from
    the HRM numbers and standard biology, and that answer is worth having — but it is a
    different KIND of answer, and the reader cannot tell the two apart from the prose alone.

    An expert says "I'm going from the numbers here, I don't have a paper for this." This is
    that sentence.
    """
    if sources or not hrm:
        return []

    return [
        "No paper in the knowledge base matched this question, so this answer rests on the "
        "HRM numbers and standard biology alone — it has no literature backing. Ingest papers "
        "on this topic if you need a citable source."
    ]


def check_fabricated_references(answer: str) -> list[str]:
    """
    Catch the model writing its OWN reference list [SPEC_Phase1 §5.3, extending §0].

    The model is handed a title, authors and year — never a journal, volume or page range.
    So when it emits "Nucleic Acids Research, 25(11), 2794-2803" it did not misremember a
    source, it manufactured one. This is the most dangerous failure mode in the whole system:
    unlike a wrong number, a fake citation carries the visual authority of a real one, and
    the reader has no way to tell without checking every entry by hand.

    check_citations() cannot see this — a fabricated "[1] ..." line uses a perfectly valid
    citation number. It is the text AFTER the marker that is invented.
    """
    warnings = []

    if _REFERENCE_LINE.search(answer) or _BIBLIOGRAPHY_HEADING.search(answer):
        warnings.append(
            "The answer wrote out its own reference list. The model is never given journal, "
            "volume or page details, so any it printed are fabricated. Ignore that list and "
            "use the Sources panel, which shows the real papers behind each [n]."
        )

    if (bogus := _NON_NUMERIC_CITATION.findall(answer)):
        warnings.append(
            "The answer used non-standard citation marker(s): "
            + ", ".join(f"[{b}]" for b in sorted(set(bogus))[:3])
            + ". Only numbered markers [1], [2] map to a real source — treat these as unverified."
        )

    return warnings
