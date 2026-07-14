"""
test_rag_guardrails.py — the three guardrails of SPEC_Phase1 §5.3.

These are the checks that make "grounded or silent" (§0) enforceable rather than
aspirational, so they are tested without an LLM in the loop: each one is a pure
function over (answer, context) and must behave identically whatever the model said.

  1. anti-fabricated numbers — a figure not in the HRM table gets flagged
  2. mandatory citations     — an answer using papers without [n] gets flagged
  3. Phase-2 scope block     — "design me a primer" never reaches the model
"""

import pytest

from ingest.indexer import chunk_text
from rag import prompt, retriever

# The worked example from SPEC_Phase1 §4.3.
HRM = {
    "features": {
        "sample_1": {"Tm": 79.4, "num_peaks": 1, "peak_height": 0.42,
                     "fwhm": 1.8, "delta_Tm_vs_pos": -0.2, "flag": "match"},
        "sample_2": {"Tm": 76.1, "num_peaks": 2, "peak_height": 0.18,
                     "fwhm": 3.5, "delta_Tm_vs_pos": -3.5, "flag": "suspect"},
    },
    "positive_control": "positive_ctrl",
    "negative_control": None,
}

SOURCES = [
    {"n": 1, "chunk_text": "Melting curve analysis distinguishes specific product "
                           "from primer-dimer.",
     "pmid": "9056205", "title": "Product differentiation by analysis of DNA melting curves",
     "authors": ["Ririe KM"], "journal": "Anal Biochem", "year": 1997,
     "url": "https://pubmed.ncbi.nlm.nih.gov/9056205/"},
]


# ── Guardrail 1: anti-fabricated numbers ───────────────────────────────────

def test_numbers_from_the_table_pass():
    answer = "sample_2 melts at 76.1 °C, shifted -3.5 °C from the positive control."
    assert prompt.check_numbers(answer, HRM) == []


def test_absolute_value_of_a_signed_delta_passes():
    """"shifted by 3.5 °C" is a faithful reading of delta = -3.5, not a fabrication."""
    assert prompt.check_numbers("Tm is shifted by 3.5 °C from the control.", HRM) == []


def test_a_number_not_in_the_table_is_flagged():
    answer = "sample_2 melts at 81.7 °C."          # 81.7 appears nowhere
    warnings = prompt.check_numbers(answer, HRM)

    assert len(warnings) == 1
    assert "81.7" in warnings[0]


def test_rounding_within_tolerance_is_not_flagged():
    """79.40 is the same number as 79.4 — flagging it would be noise."""
    assert prompt.check_numbers("Tm is 79.40 °C.", HRM) == []


def test_thresholds_quoted_from_the_system_prompt_are_not_flagged():
    """
    The system prompt hands the model the 0.3 °C match window and the 2x width rule so it
    can EXPLAIN a flag. Quoting them back is the intended behaviour, so the anti-fabrication
    check must not fire on them — otherwise every good explanation carries a false warning.
    """
    answer = ("sample_3 is shifted: its Tm differs by more than the 0.3 °C reproducibility "
              "window, which is 3x the 0.1 °C run-to-run SD of HRM instruments.")
    assert prompt.check_numbers(answer, HRM) == []


def test_numbers_are_not_checked_without_an_hrm_table():
    """With no table there is nothing to check against; decimals come from papers."""
    assert prompt.check_numbers("Tm is around 80.5 °C per the paper [1].", None) == []


# ── Guardrail 2: mandatory citations ───────────────────────────────────────

def test_answer_citing_a_provided_source_passes():
    assert prompt.check_citations("Two peaks suggest primer-dimer [1].", SOURCES) == []


def test_answer_using_papers_without_any_citation_is_flagged():
    warnings = prompt.check_citations("Two peaks suggest primer-dimer.", SOURCES)

    assert len(warnings) == 1
    assert "cites none" in warnings[0]


def test_a_citation_pointing_at_a_nonexistent_source_is_flagged():
    """[3] was never supplied — the model invented the reference."""
    warnings = prompt.check_citations("Per [3], Tm falls with lower GC.", SOURCES)

    assert any("[3]" in w and "fabricated" in w for w in warnings)


def test_no_citation_needed_when_no_sources_were_retrieved():
    assert prompt.check_citations("Not enough data to conclude.", []) == []


# ── Guardrail 2b: fabricated reference lists ───────────────────────────────

def test_a_self_written_bibliography_is_flagged():
    """
    Verbatim from a real llama3.2:3b answer. Source [1] was actually Kong Y et al. 2022,
    Front Med — the model invented the title, journal, volume and page range wholesale. The
    citation NUMBER is valid, so check_citations() sees nothing wrong; only the text after
    the marker gives it away.
    """
    answer = (
        "Sample_2 has two melt peaks, indicating primer-dimer [1].\n\n"
        "[1] Ririe T et al. (1997). Amplification of single copy mRNA by in vitro "
        "transcription and asymmetric PCR. Nucleic Acids Research, 25(11), 2794-2803."
    )

    assert prompt.check_citations(answer, SOURCES) == []      # number is valid — slips through
    warnings = prompt.check_fabricated_references(answer)     # ...but the entry is invented
    assert any("reference list" in w for w in warnings)


def test_a_references_heading_is_flagged():
    answer = "Two peaks suggest primer-dimer [1].\n\nReferences:\nRirie et al., 1997."
    assert any("reference list" in w for w in prompt.check_fabricated_references(answer))


def test_non_numeric_citation_markers_are_flagged():
    """[Ririe 1997] and [HRM TABLE] look like citations but map to nothing."""
    answer = "Two peaks indicate primer-dimer [Ririe 1997], per the table [HRM TABLE]."
    warnings = prompt.check_fabricated_references(answer)

    assert any("non-standard citation" in w for w in warnings)


def test_grouped_citations_are_accepted():
    """
    Regression: qwen2.5:7b writes "[1, 3]" to cite two sources at once. That is a normal
    citation style, not a malformed marker — flagging it put a false warning on a good answer.
    """
    answer = "Two peaks indicate non-specific product or primer-dimer [1, 3]."

    assert prompt._cited_numbers(answer) == {1, 3}
    assert prompt.check_fabricated_references(answer) == []
    # [3] is genuinely out of range for a one-source list, so THAT is still caught.
    assert any("[3]" in w for w in prompt.check_citations(answer, SOURCES))


def test_a_clean_answer_triggers_no_reference_warning():
    answer = (
        "sample_2 is abnormal: it shows two melt peaks, meaning two distinct melting "
        "populations — the true amplicon plus a shorter product such as primer-dimer [1]."
    )
    assert prompt.check_fabricated_references(answer) == []


def test_system_prompt_forbids_writing_a_bibliography():
    assert "NEVER write a reference list" in prompt.SYSTEM_PROMPT


# ── Guardrail 3: Phase-2 scope block ───────────────────────────────────────

@pytest.mark.parametrize("question", [
    "Thiết kế primer cho hsa-miR-21-5p giúp tôi",
    "Gợi ý primer tốt hơn cho mẫu này",
    "Design a primer for this miRNA",
    "Cho tôi trình tự stem-loop RT",
    "Tối ưu phản ứng này giúp tôi",
    "optimize the reaction conditions",
    "suggest a better primer",
])
def test_design_requests_are_blocked(question):
    assert prompt.is_design_request(question) is True


@pytest.mark.parametrize("question", [
    "Thiet ke primer cho hsa-miR-21-5p giup toi",
    "Goi y primer tot hon cho mau nay",
    "Cho toi trinh tu stem-loop RT",
    "Toi uu phan ung nay giup toi",
    "de xuat moi cho mau nay",
])
def test_design_requests_are_blocked_without_diacritics(question):
    """
    Regression: Vietnamese is habitually typed unaccented. A scope guard that only
    fires on "thiết kế" is bypassed by typing "thiet ke" — which would let the model
    emit a primer sequence, the one thing Phase 1 must never do [§0, §10].
    """
    assert prompt.is_design_request(question) is True


def test_accent_stripping_handles_d_with_stroke():
    """'đ' carries no combining mark, so NFD alone leaves it — it needs its own mapping."""
    assert prompt._strip_accents("đề xuất") == "de xuat"


@pytest.mark.parametrize("question", [
    "Mẫu nào bất thường và vì sao?",
    "Peak thứ hai trong sample_2 nghĩa là gì?",
    "ΔTm bao nhiêu thì coi là khác biệt thật?",
    "Vì sao chứng âm lại có tín hiệu?",
    "Giải thích kết quả HRM này",
])
def test_explanation_questions_are_not_blocked(question):
    assert prompt.is_design_request(question) is False


# ── Prompt assembly ────────────────────────────────────────────────────────

def test_prompt_carries_the_hrm_numbers_and_the_citation_labels():
    p = prompt.build_messages("Which wells are abnormal?", SOURCES, HRM)[-1]["content"]

    assert "76.1" in p and "-3.5" in p     # the model can only quote what it is shown
    assert "[1]" in p                       # the citation label it must reuse
    assert "Ririe" in p


def test_prompt_states_plainly_when_a_context_block_is_empty():
    """The model must be told a block is empty, not left to guess from its absence."""
    p = prompt.build_messages("A question", [], None)[-1]["content"]

    assert "Do not cite anything" in p
    assert "Do not state any experimental number" in p


def test_system_prompt_forbids_primer_design_and_invented_numbers():
    sp = prompt.SYSTEM_PROMPT
    assert "Never compute" in sp
    assert "Never propose, design, or write out a primer sequence" in sp
    assert "Not enough data to conclude." in sp


def test_system_prompt_demands_mechanism_not_a_restatement():
    """The quality lever: without this the 3B model just echoes the flag column back."""
    assert "MECHANISM" in prompt.SYSTEM_PROMPT
    assert "do not just restate the table" in prompt.SYSTEM_PROMPT


def test_system_prompt_defines_every_flag_the_algorithm_can_emit():
    """The model can only explain a flag it has been told the meaning of."""
    for flag in ("match", "shifted", "suspect", "noise", "control"):
        assert f"- {flag}" in prompt.SYSTEM_PROMPT


# ── Multi-turn conversation ────────────────────────────────────────────────

HISTORY = [
    {"role": "user",      "content": "Which wells are abnormal?"},
    {"role": "assistant", "content": "sample_2 shows two melt peaks, and sample_3 is shifted."},
]


def test_history_becomes_real_chat_turns_not_pasted_text():
    """
    Regression, and the whole reason /api/chat replaced /api/generate.

    Pasting the transcript into one prompt string made the 3B model re-answer the PREVIOUS
    question: asked "And is sample_3 a real variant?" right after a sample_2 answer, it opened
    with "The second peak in sample_2 is 72.0 °C" and never mentioned sample_3. Fencing the
    live question and labelling the transcript as background did NOT fix it.

    Real {role, content} turns do, because the model's chat template marks the boundary with
    the special tokens it was trained on, and instruction-tuned models answer the LAST user
    message. The boundary stops being a hint and becomes tokenisation.
    """
    msgs = prompt.build_messages("And is sample_3 a real variant?", SOURCES, HRM, HISTORY)

    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "Which wells are abnormal?"
    assert msgs[-1]["role"] == "user", "the live question must be the final user turn"
    assert "sample_3" in msgs[-1]["content"]


def test_the_evidence_rides_in_the_final_user_turn():
    """
    The paper excerpts and the HRM table belong next to the question they must ground — not in
    the system message, which several turns of chatter would push further away than the history.
    """
    msgs = prompt.build_messages("Which wells are abnormal?", SOURCES, HRM, HISTORY)
    last = msgs[-1]["content"]

    assert "HRM TABLE" in last
    assert "PAPER EXCERPTS" in last
    assert "76.1" in last                       # the model may only quote what it is shown
    assert "THE QUESTION TO ANSWER NOW:" in last


def test_messages_work_with_no_history_at_all():
    msgs = prompt.build_messages("Which wells are abnormal?", SOURCES, HRM, None)

    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_prior_answers_are_truncated_in_the_replayed_turns():
    hist = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "x" * 2000}]
    msgs = prompt.build_messages("follow up", SOURCES, HRM, hist)

    assert "[…]" in msgs[1]["content"]


def test_system_prompt_forbids_re_answering_an_earlier_question():
    assert "Answer the CURRENT question only" in prompt.SYSTEM_PROMPT


def test_history_is_capped_to_the_recent_turns():
    """A long session must not push the evidence out of the model's context window."""
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
        for i in range(40)
    ]
    msgs = prompt.build_messages("now", SOURCES, HRM, long_history)

    replayed = msgs[:-1]                                   # everything but the live question
    assert len(replayed) <= prompt.MAX_HISTORY_TURNS * 2
    assert any("msg39" in m["content"] for m in replayed)  # the most recent survives
    assert not any("msg0" == m["content"] for m in replayed)  # the oldest is dropped


def test_a_bare_followup_is_resolved_for_retrieval():
    """
    "And sample_3?" embeds to almost nothing. Retrieving on it alone returns noise, so the
    RAG step would go blind exactly when the user drills in. The previous question is
    prepended to restore the search signal.
    """
    resolved = prompt.resolve_followup("And sample_3?", HISTORY)

    assert "Which wells are abnormal?" in resolved
    assert "And sample_3?" in resolved


def test_a_self_contained_question_is_not_rewritten():
    q = "What does a second melt peak at a lower temperature usually indicate in HRM assays?"
    assert prompt.resolve_followup(q, HISTORY) == q


def test_resolve_followup_survives_an_empty_history():
    assert prompt.resolve_followup("Why?", []) == "Why?"


# ── Follow-up suggestions ──────────────────────────────────────────────────

def test_followups_name_the_users_own_wells():
    """A generic "tell me more" chip is dead weight; a chip must point at a real problem."""
    hrm = {
        "features": {
            "sample_2": {"flag": "suspect", "all_peaks": [{"Tm": 79.2, "height": 0.25},
                                                          {"Tm": 72.0, "height": 0.17}]},
            "sample_3": {"flag": "shifted", "delta_Tm_vs_pos": -3.4},
        },
        "positive_control": "positive_ctrl", "negative_control": None,
    }
    chips = prompt.suggest_followups(hrm)

    assert any("72.0" in c and "sample_2" in c for c in chips)
    assert any("sample_3" in c and "-3.4" in c for c in chips)


def test_a_contaminated_ntc_is_the_first_followup_offered():
    """A dirty no-template control invalidates the plate — it outranks any single sample."""
    hrm = {
        "features": {
            "negative_ctrl": {"flag": "suspect", "all_peaks": [{"Tm": 79.4, "height": 0.4}]},
            "sample_3":      {"flag": "shifted", "delta_Tm_vs_pos": -3.4},
        },
        "positive_control": "positive_ctrl", "negative_control": "negative_ctrl",
    }
    assert "negative control" in prompt.suggest_followups(hrm)[0]


def test_followups_never_repeat_a_question_already_asked():
    hrm = {
        "features": {"sample_3": {"flag": "shifted", "delta_Tm_vs_pos": -3.4}},
        "positive_control": "positive_ctrl", "negative_control": None,
    }
    first = prompt.suggest_followups(hrm)[0]

    assert first not in prompt.suggest_followups(hrm, asked={first})


def test_clicking_a_well_asks_exactly_the_question_the_chip_offers():
    """
    Regression. The row-click question was generated in JS and the chip in Python, producing
    two near-identical strings ("…at 72 °C, and what should I do about it?" vs "…at 72.0 °C?").
    Exact-match dedup then failed, and after clicking sample_2 the chip row cheerfully offered
    the user the very question they had just asked. One generator, one string.
    """
    f = {"flag": "suspect",
         "all_peaks": [{"Tm": 79.2, "height": 0.25}, {"Tm": 72.0, "height": 0.17}]}
    hrm = {"features": {"sample_2": f},
           "positive_control": "positive_ctrl", "negative_control": None}

    clicked = prompt.question_for_well("sample_2", f)     # what HRMUpload sends on a row click
    assert clicked in prompt.suggest_followups(hrm)       # ...is offered as a chip
    assert clicked not in prompt.suggest_followups(hrm, asked={clicked})   # ...and then is not


def test_a_clean_well_gets_no_followup_chip():
    """A chip that leads nowhere trains the user to ignore the whole row of chips."""
    hrm = {
        "features": {
            "sample_1": {"flag": "match", "delta_Tm_vs_pos": 0.1},
            "sample_3": {"flag": "shifted", "delta_Tm_vs_pos": -3.4},
        },
        "positive_control": "positive_ctrl", "negative_control": None,
    }
    chips = prompt.suggest_followups(hrm)

    assert not any("sample_1" in c for c in chips)
    assert any("sample_3" in c for c in chips)


def test_followups_fall_back_to_general_questions_without_hrm():
    chips = prompt.suggest_followups(None)

    assert len(chips) > 0
    assert all("sample" not in c for c in chips)


# ── Stable citation numbers across turns ───────────────────────────────────

def test_a_paper_keeps_its_number_across_turns():
    """
    Numbers are assigned per query, so without a registry turn 1 could cite paper A as [1] and
    turn 2 could call a different paper [1] — while the transcript still carries turn 1's
    "[1]". One number, two papers, and nothing on screen reveals it.
    """
    turn1 = [{"pmid": "111", "n": 0}, {"pmid": "222", "n": 0}]
    registry = retriever.stabilise_numbers(turn1, None)

    assert [s["n"] for s in turn1] == [1, 2]

    # Turn 2 retrieves paper 222 again plus a new paper 333.
    turn2 = [{"pmid": "333", "n": 0}, {"pmid": "222", "n": 0}]
    registry = retriever.stabilise_numbers(turn2, registry)

    by_pmid = {s["pmid"]: s["n"] for s in turn2}
    assert by_pmid["222"] == 2, "a paper cited earlier must keep its number"
    assert by_pmid["333"] == 3, "a new paper takes the next free number"
    assert {e["pmid"] for e in registry} == {"111", "222", "333"}


def test_a_fresh_conversation_numbers_from_one():
    sources = [{"pmid": "999", "n": 0}]
    retriever.stabilise_numbers(sources, [])
    assert sources[0]["n"] == 1


def test_stabilise_ignores_malformed_registry_entries():
    """The client is not trusted to send well-formed data."""
    sources = [{"pmid": "111", "n": 0}]
    retriever.stabilise_numbers(sources, [{"pmid": None}, {"n": "x"}, {}])
    assert sources[0]["n"] == 1


# ── Retrieval quality guards ───────────────────────────────────────────────

def test_the_distance_threshold_can_actually_reject():
    """
    The previous embedding model put every distance in a 0.10-0.21 band, so no threshold could
    separate relevant from irrelevant and the "grounded or silent" guard never fired. The
    threshold is only meaningful if it sits between measured relevant and irrelevant scores.
    """
    assert 0.30 < retriever.MAX_DISTANCE < 0.55, (
        "MAX_DISTANCE must sit in the measured gap: relevant ~0.30-0.40, off-topic ~0.57+"
    )


def test_no_single_paper_can_dominate_the_sources():
    assert retriever.MAX_CHUNKS_PER_PAPER < retriever.DEFAULT_K, (
        "one paper must not be able to fill every citation slot — five chunks from one "
        "abstract look like five independent sources and are not"
    )


# ── Expert conduct ─────────────────────────────────────────────────────────

def test_an_answer_with_no_literature_is_flagged_as_such():
    """An answer from the numbers alone is worth having, but the reader must know that is what it is."""
    warnings = prompt.check_coverage([], HRM)

    assert len(warnings) == 1
    assert "no literature backing" in warnings[0]


def test_no_coverage_warning_when_sources_were_found():
    assert prompt.check_coverage(SOURCES, HRM) == []


def test_no_coverage_warning_without_hrm_either():
    """With neither sources nor HRM the request is refused upstream — nothing to warn about."""
    assert prompt.check_coverage([], None) == []


def test_system_prompt_demands_researcher_conduct():
    sp = prompt.SYSTEM_PROMPT
    assert "SEPARATE WHAT WAS MEASURED FROM WHAT YOU INFER" in sp
    assert "NAME THE COMPETING EXPLANATIONS" in sp
    assert "SAY WHAT WOULD SETTLE IT" in sp
    assert "CALIBRATE YOUR CONFIDENCE" in sp


def test_recommending_an_experiment_is_allowed_but_designing_a_primer_is_not():
    """The expert may say "run a gel"; it may never say "use this primer"."""
    assert "You may recommend an EXPERIMENT or a CHECK. You may not design a primer." \
        in prompt.SYSTEM_PROMPT
    assert prompt.is_design_request("Should I run a gel to check for primer-dimer?") is False
    assert prompt.is_design_request("Design a better primer for me") is True


# ── Chunking [§3.2] ────────────────────────────────────────────────────────

def test_short_abstract_stays_a_single_chunk():
    assert len(chunk_text("word " * 100)) == 1


def test_long_abstract_splits_with_overlap():
    chunks = chunk_text(" ".join(f"w{i}" for i in range(900)), size=350, overlap=50)

    assert len(chunks) > 1
    # The tail of chunk 0 must reappear at the head of chunk 1, or a sentence
    # straddling the boundary would be unretrievable.
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]


def test_overlap_must_be_smaller_than_the_window():
    with pytest.raises(ValueError, match="must be smaller"):
        chunk_text("a b c", size=50, overlap=50)
