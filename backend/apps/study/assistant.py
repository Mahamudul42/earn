"""The feedback assistant used in Condition 3.

Per advisor guidance, the assistant runs a short multi-turn conversation that
helps the reader make *their own* feedback clearer, more specific, and more
actionable for the POPROX newsletter system. Each round it either asks a
targeted clarifying question, gives a short concrete suggestion, or — when the
feedback is actionable — thanks the reader and paraphrases the request back
(action "ok"), at which point the client offers a confirm-and-submit step.
It must NOT:
- rewrite, rephrase, or "polish" the reader's words;
- invent or suggest new preferences, topics, entities, people, organizations, or
  sources, or infer hidden preferences;
- lead the reader toward any particular topic, view, or source.

The live system prompt is maintained in ``backend/system_prompt.txt`` (advisor
supplied, POPROX-specific) so it can be edited without touching code; an
embedded prompt below is the fallback if that file is missing.

The model path is intentionally local-only. It calls the self-hosted
OpenAI-compatible endpoint configured by ``LOCAL_LLM_BASE_URL`` and never falls
back to an external provider. There is deliberately no rule-based stand-in
either: if the endpoint fails, ``AssistantUnavailable`` is raised so the caller
can surface a clear error. The assistant never fabricates a turn, so every
stored conversation turn is genuine model output.
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


class AssistantUnavailable(RuntimeError):
    """The local model could not produce a usable reply.

    Raised instead of silently substituting canned text, so the participant is
    told the assistant is unavailable rather than shown a fake turn.
    """


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
    model: str = ""


def _parse_assistant_json(raw: str) -> AssistantResult | None:
    """Pull the {action, message} object out of a model's text reply."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else raw)
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None
    action = data.get("action")
    message = (data.get("message") or "").strip()
    if action in _VALID_ACTIONS and message:
        return AssistantResult(action, message)
    return None


# --- Local-only model client -----------------------------------------------
def _local_conf() -> dict:
    """Resolve the self-hosted OpenAI-compatible model configuration."""
    return {
        "model": getattr(settings, "LOCAL_LLM_MODEL", "openai/gpt-oss-120b"),
        "base": (getattr(settings, "LOCAL_LLM_BASE_URL", "") or "").strip(),
        "key": (getattr(settings, "LOCAL_LLM_API_KEY", "") or "").strip(),
        "timeout": getattr(settings, "LOCAL_LLM_TIMEOUT_SECONDS", 45),
    }


def active_model() -> str:
    return _local_conf()["model"]


def _chat_local(messages, temperature: float, max_tokens: int) -> str:
    """Call the configured local OpenAI-compatible chat endpoint.

    Raises ``AssistantUnavailable`` for any failure — unset base URL, network
    error, malformed response, or empty content.
    """
    conf = _local_conf()
    if not conf["base"]:
        raise AssistantUnavailable("LOCAL_LLM_BASE_URL is not configured.")
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
    req = urllib.request.Request(f"{base}/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=conf["timeout"]) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
    except AssistantUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - any transport/parse failure is the same to callers
        raise AssistantUnavailable(f"Local LLM request failed: {exc}") from exc
    text = content.strip() if isinstance(content, str) else ""
    if not text:
        raise AssistantUnavailable("Local LLM returned an empty response.")
    return text


# --- Condition-3 conversation ------------------------------------------------
def _combined_user_text(history) -> str:
    return "\n".join(m["content"] for m in history if m.get("role") == "user")


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
    ``title``/``sections`` (``sections`` = a list of
    ``{"name", "articles": [{"label","headline","summary"}]}``). Returns "" when
    there is nothing to show.
    """
    if newsletter is None:
        return ""
    sections = getattr(newsletter, "sections", None) or []
    if not sections:
        return ""
    from .content import current_edition_label

    title = (getattr(newsletter, "title", "") or "").strip()
    # Same masthead date the reader sees, so references like "today's edition"
    # line up between the participant's screen and the assistant's context.
    edition = current_edition_label()
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

    The local LLM is the only network destination. Raises
    ``AssistantUnavailable`` if it cannot be reached or its reply cannot be
    parsed — no canned reply is ever substituted. The assistant clarifies and
    suggests; it never rewrites the reader's text. ``newsletter`` (optional) is
    the exact stimulus the reader read; when given, it is added as read-only
    grounding so the assistant can resolve references.
    """
    system = SYSTEM_PROMPT + "\n" + CONVERSATION_ADDENDUM
    context = render_newsletter_context(newsletter)
    if context:
        system += "\n\n" + context
    messages = [{"role": "system", "content": system}]
    for m in history:
        if m.get("role") == "assistant":
            content = json.dumps(
                {
                    "action": m.get("action") or ACTION_SUGGESTION,
                    "message": m["content"],
                }
            )
            messages.append({"role": "assistant", "content": content})
        elif m.get("role") == "user":
            messages.append({"role": "user", "content": (m["content"] or "").strip()})

    text = _chat_local(messages, temperature=0.4, max_tokens=1024)
    parsed = _parse_assistant_json(text)
    if parsed is None:
        raise AssistantUnavailable("Local LLM reply was not in the required format.")
    parsed.model = active_model()
    return parsed


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


def compose_final_feedback(history, newsletter=None) -> str:
    """Consolidate the whole conversation into one submission-ready feedback
    text in the reader's own voice.

    The consolidation is grounded in the same POPROX ``SYSTEM_PROMPT`` the chat
    assistant used, so the final summary respects the identical system
    constraints (capabilities/limits and strict rules); ``FINALIZE_PROMPT``
    overrides only that prompt's output format and per-turn task. ``newsletter``
    (optional) is added as the same read-only grounding used during the chat.

    Raises ``AssistantUnavailable`` if the local endpoint cannot be reached; the
    caller decides what to show the participant.
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
    text = _chat_local(messages, temperature=0.4, max_tokens=1024)
    return text.strip().strip('"').strip()
