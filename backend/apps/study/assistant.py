"""Condition 3 feedback assistant.

Runs a short multi-turn conversation that helps the reader make their own
feedback clearer and more specific. Each round it asks a clarifying question,
gives a short suggestion, or returns action "ok" once the feedback is
actionable, after which the client shows the confirm-and-submit step.

Rules (from the advisor's prompt): it must not rewrite or polish the reader's
words, invent preferences or sources, or lead the reader toward any topic.

The live prompt is in backend/system_prompt.txt so it can be edited without
touching code. The prompt below is used if that file is missing.

Only the self-hosted model at LOCAL_LLM_BASE_URL is called. There is no
external provider and no rule-based substitute: if the call fails,
AssistantUnavailable is raised and the caller reports it.
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
    """The local model could not be reached or returned an unusable reply."""


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
    """Call the local OpenAI-compatible chat endpoint.

    Raises AssistantUnavailable if the base URL is unset, the request fails, or
    the response is malformed or empty.
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
    """Render the newsletter the reader saw, as read-only context.

    Without this the assistant only sees the conversation and cannot tell what
    "the first story" or "the war coverage" refers to. The block is framed as
    context only, so the assistant does not suggest content the reader did not
    raise.

    newsletter can be a Newsletter instance or any object with title and
    sections, where sections is a list of
    {"name", "articles": [{"label", "headline", "summary"}]}.
    Returns "" if there is nothing to render.
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
    """Run one round of the Condition 3 conversation.

    history is the conversation so far, a list of
    {"role": "user"|"assistant", "content": str, "action": str?} ending with the
    reader's newest message. Past assistant turns are replayed in the model's
    own JSON format so the output format stays stable.

    Raises AssistantUnavailable if the model cannot be reached or its reply
    cannot be parsed. newsletter is optional and adds read-only context.
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


# --- Final-feedback consolidation --------------------------------------------
# At the confirm-and-submit step we build one feedback text out of everything
# the reader said. It only combines and orders their own words.
#
# The same SYSTEM_PROMPT is prepended so the summary follows the same rules the
# chat did. FINALIZE_PROMPT only replaces the JSON output format and the
# per-turn task; the rest still applies.
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
    """Turn the conversation into one feedback text in the reader's own voice.

    Raises AssistantUnavailable if the local endpoint cannot be reached.
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
