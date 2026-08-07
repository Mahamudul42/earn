"""Participant-facing copy for the three elicitation conditions.

Kept on the backend so the exact wording is versioned with the study and can be
adjusted after the pilot without changing the frontend.

Design (per advisor guidance):
- The main prompt is neutral and open-ended, not topic-centric. Personalization
  covers more than topics: balance, locality, people and organizations, section
  mix, recency, variety and repetition.
- Condition 1 shows the base prompt only.
- Condition 2 adds examples spanning several dimensions without pushing any
  particular topic.
- Condition 3 adds an assistant that asks clarifying questions or gives short
  advice. It does not rewrite the participant's words.
"""
from django.utils import timezone

from .models import Condition


def current_edition_label() -> str:
    """Masthead date for the newsletter. Uses today so it never looks old."""
    today = timezone.localdate()
    return f"{today:%A} Edition · {today:%B} {today.day}, {today.year}"


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

# Condition 2: base prompt plus examples and extra support. The examples span
# many personalization dimensions and are explicitly framed as optional idea-sparkers
# so they do not push participants toward any particular topic or preference.
CONDITION2_INSTRUCTION = (
    "Your feedback can be about anything in this newsletter — not just the topics. "
    "Here are some aspects other readers sometimes think about. You don't have to use "
    "any of them."
)
# Only lists things the system can act on: which articles are chosen, how much
# of each kind appears, and where they sit. Article length, added background and
# other publishers are left out because POPROX cannot do them, and prompting for
# them would lower the feasibility scores in this condition.
CONDITION2_GUIDANCE = (
    "For example: the topics or stories covered; how local or national it is; "
    "particular people or organizations; the balance between different kinds of "
    "news; the mix of sections; how recent the stories are; which stories appear "
    "near the top; the variety or diversity of what you see; or how often the same "
    "story comes up again. These are only examples to spark ideas — there are no "
    "right answers, and you can mention anything else, or none of these."
)
CONDITION2_EXAMPLE = (
    "For instance, someone might write: “I'd like more local city coverage and "
    "fewer celebrity stories, and when several articles cover the same event I'd "
    "rather just see one of them.”"
)

CONDITION1_GUIDANCE = ""  # Base prompt only, no examples or extra support.

# Condition 3: base prompt plus the interactive assistant. It chats
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
