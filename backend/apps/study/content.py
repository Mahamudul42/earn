"""Participant-facing copy for the three elicitation conditions.

Kept on the backend so the exact wording is versioned with the study and can be
adjusted after the pilot without changing the frontend.

Design (per advisor guidance):
- The main feedback prompt is neutral, open-ended, inclusive, and NOT topic-centric.
  Personalization is more than topics — it can be about tone, balance, locality,
  people/organizations, story depth, source style, section mix, recency, article
  length, diversity, the amount of background/context, or broader/narrower coverage.
- Condition 1 shows the base explanatory prompt only.
- Condition 2 adds concise, inclusive examples that span many dimensions without
  pushing any particular topic or preference.
- Condition 3 adds an LLM assistant that only asks clarifying questions or gives
  short advice — it never rewrites the participant's words or invents preferences.
"""
from .models import Condition

# Neutral, open-ended base prompt used in ALL conditions.
PROMPT = "How would you like this newsletter to work better for you?"

# Short explanation shown beneath the prompt in every condition. It signals that
# feedback can be about many aspects, not only topics.
BASE_EXPLANATION = (
    "In your own words, describe anything about this newsletter you would change or "
    "improve. It does not have to be about topics — write whatever matters to you."
)

CONSENT_TEXT = (
    "You are invited to take part in a research study on how people give feedback "
    "about personalized news newsletters.\n\n"
    "What you will do: read one news newsletter, write a short comment describing "
    "how you would like it improved, and answer a brief survey. This takes about 5 "
    "to 8 minutes.\n\n"
    "Use of your responses: your responses are collected for research purposes only "
    "and will not change any newsletter you receive now or in the future. Please do "
    "not include information that could identify you, such as your name, address, "
    "email, or phone number.\n\n"
    "Voluntary participation: taking part is completely voluntary. You may stop at "
    "any time, for any reason, by closing this window.\n\n"
    "By selecting “I agree” below, you confirm that you are 18 years of age "
    "or older and that you agree to take part in this study."
)

# Condition 2 — base prompt + inclusive examples/extra support. The examples span
# many personalization dimensions and are explicitly framed as optional idea-sparkers
# so they do not push participants toward any particular topic or preference.
CONDITION2_INSTRUCTION = (
    "Your feedback can be about anything in this newsletter — not just the topics. "
    "Here are some aspects other readers sometimes think about. You don't have to use "
    "any of them."
)
CONDITION2_GUIDANCE = (
    "For example: the topics or stories covered; the tone or balance; how local or "
    "national it is; particular people or organizations; how detailed or in-depth the "
    "stories are; the kinds of sources; the mix of sections; how recent the news is; "
    "the length of the articles; the variety or diversity; or how much background and "
    "context is included. These are only examples to spark ideas — there are no right "
    "answers, and you can mention anything else, or none of these."
)
CONDITION2_EXAMPLE = (
    "For instance, someone might write: “I'd like a little more local coverage and "
    "somewhat shorter articles, with less repetition of the same story, and a bit more "
    "background on why each story matters.”"
)

CONDITION1_GUIDANCE = ""  # Base prompt only — no examples or extra support.

# Condition 3 — base prompt + interactive LLM guidance. The assistant chats
# briefly with the participant (clarifying questions / short tips) until the
# feedback is actionable; it never rewrites the participant's words, and the
# participant confirms and submits the final version themselves.
CONDITION3_INTRO = (
    "After you write your feedback, a feedback assistant will read it and may ask you "
    "short clarifying questions or give brief tips in a quick back-and-forth to help "
    "you make your own feedback clearer. It will not rewrite your words — when your "
    "feedback is ready, you review it and submit the final version yourself."
)


def condition_config(condition: int) -> dict:
    """Return the copy the frontend needs to render a given condition."""
    cfg = {
        "condition": condition,
        "condition_label": Condition(condition).label,
        "prompt": PROMPT,
        "base_explanation": BASE_EXPLANATION,
        "instruction": "",
        "guidance": "",
        "example": "",
        "intro": "",
        "interactive": condition == Condition.ASSISTANT,
    }
    if condition == Condition.EXAMPLES:
        cfg["instruction"] = CONDITION2_INSTRUCTION
        cfg["guidance"] = CONDITION2_GUIDANCE
        cfg["example"] = CONDITION2_EXAMPLE
    elif condition == Condition.ASSISTANT:
        cfg["intro"] = CONDITION3_INTRO
    return cfg
