"""The feedback assistant used in Condition 3.

Per advisor guidance, the assistant runs a short multi-turn conversation that
helps the reader make *their own* feedback clearer, more specific, and more
actionable for the POPROX newsletter system. Each round it either asks a
targeted clarifying question, gives a short concrete suggestion, or — when the
feedback is actionable — thanks the reader and paraphrases the request back
(action "ok"), at which point the client offers a confirm-and-submit step.
It still must NOT:
- rewrite, rephrase, or "polish" the reader's words;
- invent or suggest new preferences, topics, entities, people, organizations, or
  sources, or infer hidden preferences;
- lead the reader toward any particular topic, view, or source.

The live system prompt is maintained in ``backend/system_prompt.txt`` (advisor
supplied, POPROX-specific) so it can be edited without touching code; an
embedded prompt below is the fallback if that file is missing.

The live model path is intentionally local-only. It calls the self-hosted
OpenAI-compatible endpoint configured by ``LOCAL_LLM_BASE_URL`` and never
falls back to an external provider. If that endpoint fails, a deterministic
rule-based fallback keeps the participant flow usable without sending their
data elsewhere. No external-provider adapter is imported by this module.

``run_model(system_prompt, user_text)`` exposes a low-level call with an
arbitrary system prompt; it is reused by the researcher prompt playground.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

ACTION_NONE = "none"
ACTION_SUGGESTION = "suggestion"
ACTION_QUESTION = "question"
ACTION_OK = "ok"

_VALID_ACTIONS = {ACTION_SUGGESTION, ACTION_QUESTION, ACTION_OK}

# --- System prompt -----------------------------------------------------------
# The live Condition-3 prompt lives in backend/system_prompt.txt
# This embedded prompt is only a fallback.
_PROMPT_FILE = Path(__file__).resolve().parents[2] / "system_prompt.txt"

_EMBEDDED_SYSTEM_PROMPT = """You are a feedback assistant on a personalized news newsletter. A \
personalized news newsletter is a short, curated set of news articles chosen for one reader. \
The reader has just read their newsletter and written feedback about how they would like it \
improved — for example, what they want more or less of, or anything about the article \
selection they would change. Your job is to help the reader make their own feedback clearer \
and more usable, so that a newsletter system could actually act on it.

STRICT RULES (do not break these):
- Never rewrite, rephrase, or "polish" the reader's feedback. Do not hand back an improved or \
corrected version of their words.
- Never invent, add, or suggest new preferences, topics, entities, people, organizations, or \
sources, and do not guess what they might want. Work only with what they actually wrote.
- Do not infer hidden preferences, and never lead the reader toward any particular topic, \
opinion, political view, source, organization, or type of personalization. Stay neutral.
- Preserve the reader's intent exactly.
- If the feedback contains sensitive, political, or personal information, respond neutrally \
and non-persuasively, and gently remind the reader not to include information that could \
identify them.

WHAT TO DO:
Give one or two short, concrete, operationalizable suggestions that help the reader turn \
their OWN feedback into something specific a system could act on, or ask one short \
clarifying question. If the feedback is already specific and actionable, thank the reader \
and paraphrase back what you understand they are asking for. Keep it short (about one to \
three sentences); the reader always decides the final wording of their feedback.

Respond with ONLY a JSON object:
{"action": "suggestion" | "question" | "ok", "message": "<your short response>"}"""


def _load_system_prompt() -> str:
    try:
        text = _PROMPT_FILE.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    return _EMBEDDED_SYSTEM_PROMPT


SYSTEM_PROMPT = _load_system_prompt()

# Appended to the system prompt when the assistant runs as a conversation. The
# base prompt is written for a single round; this adapts it to multiple rounds
# without changing any of its rules.
CONVERSATION_ADDENDUM = """
CONVERSATION MODE
You are in an ongoing conversation with the reader. The conversation begins with the \
reader's initial feedback; you may already have asked questions or given suggestions, and \
the reader may have replied. Treat ALL of the reader's messages together as their feedback \
so far.
- Respond to the reader's newest message in the context of the whole conversation.
- Never re-ask something the reader has already answered, and do not repeat an earlier \
suggestion. At most one question per response.
- As soon as the combined feedback is clear enough for POPROX to act on, use action "ok" \
and paraphrase back the COMPLETE request across the whole conversation in one or two \
sentences (for example, "Thanks — it sounds like you want ..."). Do not keep asking for \
more detail once the feedback is actionable.
- If the reader declines to add detail or says they are done, accept that: use action "ok" \
and paraphrase what they have given so far.
- Continue to respond with ONLY the required JSON object."""


@dataclass
class AssistantResult:
    action: str
    message: str
    used_llm: bool
    provider: str = ""
    model: str = ""


# --- Lightweight signal detection (used only by the deterministic fallback) ----
_DIRECTION_WORDS = re.compile(
    r"\b(more|less|fewer|avoid|exclude|include|prioriti[sz]e|reduce|cut|drop|"
    r"diversify|wider|variety|repeat|repetiti|reorder|focus|skip|shorter|longer)\b",
    re.IGNORECASE,
)
_TOPIC_LEXICON = re.compile(
    r"\b(politic|election|sport|tennis|football|science|technolog|tech|health|"
    r"business|finance|econom|world|local|weather|climate|education|entertainment|"
    r"celebrit|crime|opinion|culture|art|music|travel|food|tone|balance|length|"
    r"source|recent|depth|background|context|diversity|variety)\w*",
    re.IGNORECASE,
)


def _has_target(text: str) -> bool:
    if _TOPIC_LEXICON.search(text):
        return True
    return bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text))


def _fallback(combined_text: str, rounds: int = 0) -> AssistantResult:
    """Deterministic suggestion assistant — never rewrites the reader's text.

    ``combined_text`` is everything the reader has written so far; ``rounds`` is
    how many assistant replies they have already received, so the fallback stops
    asking after a couple of rounds instead of looping forever.
    """
    text = (combined_text or "").strip()
    words = text.split()
    has_dir = bool(_DIRECTION_WORDS.search(text))
    has_tgt = _has_target(text)

    if (has_dir and has_tgt) or rounds >= 2:
        return AssistantResult(
            ACTION_OK,
            "Thanks — that gives the newsletter something concrete to work with. "
            "Review your feedback below and submit it when you are happy with it.",
            used_llm=False,
        )
    if len(words) < 5 or not (has_dir or has_tgt):
        return AssistantResult(
            ACTION_SUGGESTION,
            "It would help to name one concrete thing you'd change — for example, "
            "whether you want more or less of a particular kind of story, or a part of "
            "the newsletter that didn't work for you. What is one change that would make "
            "it better for you?",
            used_llm=False,
        )
    return AssistantResult(
        ACTION_SUGGESTION,
        "You could make this easier to act on by giving a concrete example and saying how "
        "much more or less of it you'd want.",
        used_llm=False,
    )


def _parse_assistant_json(raw: str) -> AssistantResult | None:
    """Pull the {action, message} object out of a model's text reply."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    data = json.loads(match.group(0) if match else raw)
    action = data.get("action")
    message = (data.get("message") or "").strip()
    if action in _VALID_ACTIONS and message:
        return AssistantResult(action, message, used_llm=True)
    return None


# --- Local-only model client -----------------------------------------------
def _local_conf() -> dict:
    """Resolve only the self-hosted OpenAI-compatible model configuration."""
    return {
        "provider": "local",
        "model": getattr(settings, "LOCAL_LLM_MODEL", "openai/gpt-oss-120b"),
        "base": (getattr(settings, "LOCAL_LLM_BASE_URL", "") or "").strip(),
        "key": (getattr(settings, "LOCAL_LLM_API_KEY", "") or "").strip(),
        "timeout": getattr(settings, "LOCAL_LLM_TIMEOUT_SECONDS", 45),
    }


def active_provider() -> str:
    """The active runtime is deliberately fixed to the self-hosted model."""
    return "local"


def active_model() -> str:
    return _local_conf()["model"]


def provider_status() -> dict:
    """Static local endpoint description; this does not make a network call."""
    conf = _local_conf()
    configured = bool(conf["base"])
    return {
        "provider": "local",
        "model": conf["model"],
        # Kept for compatibility with the researcher UI. A local no-auth
        # endpoint is considered ready when its base URL is configured.
        "has_key": configured,
        "configured": {"local": configured},
    }


def _chat_local(conf: dict, messages, temperature, max_tokens) -> str:
    """Call only the configured local OpenAI-compatible chat endpoint."""
    if not conf["base"]:
        raise RuntimeError("LOCAL_LLM_BASE_URL is not configured.")
    import urllib.request

    base = conf["base"].rstrip("/")
    body = json.dumps(
        {
            "model": conf["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EARN-study/1.0",
    }
    # The current local endpoint does not require authentication. This remains
    # optional in case authentication is enabled on that server later.
    if conf["key"]:
        headers["Authorization"] = f"Bearer {conf['key']}"
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body, headers=headers
    )
    with urllib.request.urlopen(req, timeout=conf["timeout"]) as resp:
        data = json.loads(resp.read())
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "Local LLM returned an invalid chat-completion response."
        ) from exc
    text = content.strip() if isinstance(content, str) else ""
    if not text:
        raise RuntimeError("Local LLM returned an empty response.")
    return text


def run_model(
    system_prompt: str,
    user_text: str,
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> str:
    """Low-level single-turn call to the local model only."""
    conf = _local_conf()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text.strip()},
    ]
    return _chat_local(conf, messages, temperature, max_tokens)


def run_local_chat(
    messages,
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> tuple[str, dict]:
    """Dispatch a conversation exclusively to the local LLM."""
    conf = _local_conf()
    return _chat_local(conf, messages, temperature, max_tokens), conf


def live_check(max_tokens: int = 64) -> dict:
    """Send a tiny real request to the active provider and report the outcome.

    Returns ``{provider, model, ok, error, configured}`` so the researcher UI can
    show exactly which provider/model answered (and, if not, why).
    """
    info = provider_status()
    if not info["has_key"]:
        return {
            **info,
            "ok": False,
            "error": "LOCAL_LLM_BASE_URL is not configured.",
        }
    try:
        run_model("Reply with the single word OK.", "ping", max_tokens=max_tokens)
        return {**info, "ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001 - report the reason to the researcher
        return {**info, "ok": False, "error": str(exc)[:200]}


# --- Condition-3 conversation ------------------------------------------------
def _combined_user_text(history) -> str:
    return "\n".join(m["content"] for m in history if m.get("role") == "user")


def _assistant_rounds(history) -> int:
    return sum(1 for m in history if m.get("role") == "assistant")


def _truncate(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_newsletter_context(newsletter) -> str:
    """Render the specific newsletter the reader read as READ-ONLY grounding.

    The assistant otherwise only sees the conversation, so it has to guess what
    "the first story" or "the war coverage" refers to. Showing it the exact
    newsletter lets it resolve those references and judge what is actually
    present — but the block is framed strictly as context, never as material to
    suggest from, so the assistant does not lead the reader toward content they
    did not raise (which would violate the STRICT RULES and bias the study).

    ``newsletter`` may be a ``Newsletter`` model instance or any object exposing
    ``title``/``edition_label``/``sections`` (``sections`` = a list of
    ``{"name", "articles": [{"label","headline","summary"}]}``). Returns "" when
    there is nothing to show.
    """
    if newsletter is None:
        return ""
    sections = getattr(newsletter, "sections", None) or []
    if not sections:
        return ""
    title = (getattr(newsletter, "title", "") or "").strip()
    edition = (getattr(newsletter, "edition_label", "") or "").strip()
    lines = [
        "THE NEWSLETTER THE READER JUST READ (read-only context)",
        "The reader wrote their feedback right after reading the specific newsletter "
        "below. Use it ONLY to understand which section or article the reader is "
        'referring to (for example "the first story", "the war coverage", "the top '
        'section") and to judge what is actually present. This is strict context, NOT '
        "material to draw from: never suggest, add, mention, or steer the reader toward "
        "any topic, article, section, entity, or preference from this newsletter that "
        "the reader did not themselves bring up. All the STRICT RULES above still apply.",
        "",
    ]
    masthead = " · ".join(p for p in (title, edition) if p)
    if masthead:
        lines.append(masthead)
    for si, sec in enumerate(sections, 1):
        if not isinstance(sec, dict):
            continue
        lines.append(f"Section {si}: {(sec.get('name') or '').strip()}")
        for ai, art in enumerate(sec.get("articles") or [], 1):
            if not isinstance(art, dict):
                continue
            label = (art.get("label") or "").strip()
            headline = (art.get("headline") or "").strip()
            summary = (art.get("summary") or "").strip()
            head = f"[{label}] {headline}" if label else headline
            line = f"  {si}.{ai} {head}".rstrip()
            if summary:
                line += f" — {_truncate(summary)}"
            lines.append(line)
    return "\n".join(lines)


def get_assistant_reply(history, newsletter=None) -> AssistantResult:
    """Run one round of the Condition-3 conversation.

    ``history`` is the conversation so far as a list of
    ``{"role": "user"|"assistant", "content": str, "action": str?}`` dicts,
    ending with the reader's newest message. Assistant turns are replayed to the
    model in its own JSON output format so the format stays stable across turns.

    The local LLM is the only network destination. On failure, the deterministic
    rule-based fallback runs without contacting an external provider. The
    assistant clarifies and suggests; it never rewrites the reader's text.
    ``newsletter`` (optional) is the exact stimulus the reader read; when given,
    it is added as read-only grounding so the assistant can resolve references.
    """
    system = SYSTEM_PROMPT + "\n" + CONVERSATION_ADDENDUM
    context = render_newsletter_context(newsletter)
    if context:
        system += "\n\n" + context
    messages = [{"role": "system", "content": system}]
    for m in history:
        if m.get("role") == "assistant":
            content = json.dumps(
                {"action": m.get("action") or ACTION_SUGGESTION, "message": m["content"]}
            )
            messages.append({"role": "assistant", "content": content})
        elif m.get("role") == "user":
            messages.append({"role": "user", "content": (m["content"] or "").strip()})

    try:
        text, conf = run_local_chat(messages, max_tokens=1024)
        parsed = _parse_assistant_json(text)
        if parsed:
            parsed.provider = conf["provider"]
            parsed.model = conf["model"]
            return parsed
    except Exception:
        # Local endpoint failed -> deterministic fallback; never call externally.
        pass
    return _fallback(_combined_user_text(history), rounds=_assistant_rounds(history))


def get_assistant_response(initial_text: str, newsletter=None) -> AssistantResult:
    """First assistant round on the participant's initial feedback."""
    return get_assistant_reply(
        [{"role": "user", "content": initial_text}], newsletter=newsletter
    )


# --- Final-feedback consolidation ---------------------------------------------
# When the participant reaches the confirm-and-submit step, we assemble ONE
# submission-ready feedback text out of everything they said across the
# conversation. This is faithful consolidation, not authoring: it may only
# combine and order the reader's own stated preferences.
#
# The consolidation is prefixed with the same POPROX ``SYSTEM_PROMPT`` the chat
# assistant uses, so the final summary honours the same system constraints
# (capabilities/limits, neutrality, no-invention, sensitive-info handling) that
# the reader saw enforced during the conversation. ``FINALIZE_PROMPT`` below
# only *overrides* that prompt's JSON output format and swaps the per-turn task
# (ask/suggest/ok) for a one-shot consolidation task; every other rule carries
# over unchanged.
FINALIZE_PROMPT = """CONSOLIDATION STEP — this is a different task from the round-by-round \
conversation described above.

The conversation with the reader is now finished. For THIS step you are NOT asking a \
question, giving a suggestion, or returning the {"action", "message"} JSON object — ignore \
the OUTPUT FORMAT section above. Everything else above still fully applies: the POPROX \
system context, what the newsletter system can and cannot act on, and especially the \
STRICT RULES (do not invent or infer preferences, stay neutral, preserve the reader's \
intent, and handle any sensitive or identifying information carefully).

You will receive the conversation between a newsletter READER and the feedback ASSISTANT. \
Write the reader's complete final feedback as the reader would submit it themselves: a \
single short statement (one to four sentences) in the reader's own first-person voice.

Rules for the consolidated feedback:
- Include EVERY preference the reader expressed across ALL of their messages, with the \
details they gave (which topic or section, more or less, where it should appear, how \
strongly they feel).
- Use ONLY what the reader actually said. Do not add new topics, preferences, examples, \
reasons, or details the reader did not state. Reuse the reader's own words and phrasing \
wherever possible.
- Use the POPROX context above only to phrase the reader's preferences accurately in the \
system's own terms (its sections, topics, and the kinds of changes it can make). Do NOT \
drop, soften, or "fix" a preference just because the system might not be able to satisfy \
it — if the reader asked for it, keep it, in their words. Faithfulness to what the reader \
actually said always comes first.
- Use the assistant's messages only to understand what the reader's short answers refer \
to; never copy the assistant's questions or suggestions into the feedback.
- Do not mention the assistant, the conversation, or the newsletter system.
- Drop greetings and filler; keep the reader's meaning and tone.
- Output ONLY the feedback text — no preamble, quotes, labels, or JSON."""


def compose_final_feedback(history, newsletter=None) -> tuple[str, bool]:
    """Consolidate the whole conversation into one submission-ready feedback
    text in the reader's own voice. Returns ``(text, used_llm)``. Falls back to
    the reader's messages joined verbatim if the local endpoint fails.

    The consolidation is grounded in the same POPROX ``SYSTEM_PROMPT`` the chat
    assistant used, so the final summary respects the identical system
    constraints (capabilities/limits and strict rules); ``FINALIZE_PROMPT``
    overrides only that prompt's output format and per-turn task. ``newsletter``
    (optional) is added as the same read-only grounding used during the chat.
    """
    transcript = []
    for m in history:
        if m.get("role") == "user":
            transcript.append(f"READER: {m['content']}")
        elif m.get("role") == "assistant":
            transcript.append(f"ASSISTANT: {m['content']}")
    system = SYSTEM_PROMPT + "\n\n\n" + FINALIZE_PROMPT
    context = render_newsletter_context(newsletter)
    if context:
        system += "\n\n" + context
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(transcript)},
    ]
    try:
        text, _conf = run_local_chat(messages, max_tokens=1024)
        text = text.strip().strip('"').strip()
        if text:
            return text, True
    except Exception:
        pass
    return _combined_user_text(history), False


# --- Actionability auto-rating ------------------------------------------------
# An LLM "judge" that scores a final feedback text against the same
# five-dimension actionability rubric the human raters use, so scoring can scale
# and be validated against the humans. It is grounded in the POPROX
# ``SYSTEM_PROMPT`` so the feasibility dimension is judged against real system
# capabilities. Results are stored as ActionabilityRating(is_llm=True) by the
# ``rate_with_llm`` management command.
RATING_DIMENSIONS = (
    "target_specificity",
    "direction_operation",
    "collection_allocation",
    "context_persistence",
    "system_feasibility",
)
_TARGET_LEVELS = {"article", "section", "collection", "unclear"}

RATER_PROMPT = """SCORING TASK — this is different from the conversation task described above.

You are now an expert annotator scoring a reader's FINAL newsletter feedback for how \
ACTIONABLE it is for the POPROX system described above. You are not chatting, asking a \
question, or returning the {"action", "message"} object — ignore the OUTPUT FORMAT section \
above. Use the POPROX capabilities and limits above to judge feasibility.

Score the feedback on five dimensions. Each dimension is 0, 1, or 2 \
(0 = absent or unusable, 1 = partial or only implied, 2 = clear and directly usable):
- target_specificity: names a concrete target to act on — a topic, entity, event, \
geography, source type, or section.
- direction_operation: states a clear operation — include, exclude, prioritize, \
de-prioritize, diversify, reduce repetition, or reorder.
- collection_allocation: speaks to the overall mix, variety, repetition, or the use of the \
newsletter's limited slots across the whole collection.
- context_persistence: says when the preference applies, how long it lasts, or what \
exceptions matter.
- system_feasibility: can POPROX actually satisfy it with the available AP article pool and \
its supported operations, as described above.

Also classify target_level as exactly one of: "article", "section", "collection", or \
"unclear".

Respond with ONLY a JSON object, no other text:
{"target_specificity": 0, "direction_operation": 0, "collection_allocation": 0, \
"context_persistence": 0, "system_feasibility": 0, \
"target_level": "article|section|collection|unclear", \
"notes": "<one short sentence justifying the scores>"}"""


def _parse_rating_json(raw: str) -> dict | None:
    """Pull the rubric scores out of a model's reply. Returns a dict with the
    five 0-2 scores, ``target_level``, and ``notes``, or ``None`` if the reply
    is unparseable or missing a dimension."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else raw)
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict = {}
    for dim in RATING_DIMENSIONS:
        try:
            out[dim] = max(0, min(2, int(data[dim])))
        except (KeyError, TypeError, ValueError):
            return None
    level = str(data.get("target_level") or "").strip().lower()
    out["target_level"] = level if level in _TARGET_LEVELS else "unclear"
    out["notes"] = str(data.get("notes") or "").strip()[:500]
    return out


def llm_rate_feedback(final_text: str, newsletter=None) -> dict | None:
    """Score one final feedback text against the five-dimension actionability
    rubric using only the local LLM. Returns the parsed scores dict (see
    ``_parse_rating_json``) or ``None`` if the local endpoint did not answer or
    the reply could not be parsed. Grounded in the POPROX ``SYSTEM_PROMPT``
    (and the newsletter, when given) so feasibility is judged in context."""
    text = (final_text or "").strip()
    if not text:
        return None
    system = SYSTEM_PROMPT + "\n\n\n" + RATER_PROMPT
    context = render_newsletter_context(newsletter)
    if context:
        system += "\n\n" + context
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"READER'S FINAL FEEDBACK:\n{text}"},
    ]
    try:
        raw, _conf = run_local_chat(messages, max_tokens=1024)
    except Exception:
        return None
    return _parse_rating_json(raw)
