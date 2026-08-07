"""Balanced random assignment of participants to (condition, newsletter) cells.

The study is between-subjects with three conditions, and newsletter stimulus is
balanced across conditions and treated as a control variable. We assign each new
participant to the least-filled (condition, newsletter) cell, breaking ties at
random. This keeps the design balanced without needing a fixed enrollment cap.
"""

import random

from django.conf import settings
from django.db.models import Count

from .models import Condition, Newsletter, Participant, StudyPhase


def choose_cell(
    forced_condition: int | None = None,
    forced_newsletter_slug: str | None = None,
) -> tuple[int, Newsletter]:
    """Pick a (condition, newsletter) cell for a new participant.

    Normally this is the least-filled cell across all conditions and
    newsletters (balanced assignment). For previews/demos, ``forced_condition``
    and/or ``forced_newsletter_slug`` restrict the choice, e.g. open the study
    with ``?condition=3`` to always land on the Interactive Feedback Assistant.
    """
    newsletters = list(Newsletter.objects.filter(is_active=True))
    if not newsletters:
        raise ValueError("No active newsletter stimuli configured.")

    all_conditions = [c.value for c in Condition]
    if forced_condition in all_conditions:
        # Preview/demo override: honor the requested condition regardless of which
        # conditions are enabled for normal assignment.
        conditions = [forced_condition]
    else:
        enabled = set(
            getattr(settings, "STUDY_ENABLED_CONDITIONS", None) or all_conditions
        )
        conditions = [c for c in all_conditions if c in enabled] or all_conditions
    if forced_newsletter_slug:
        match = [n for n in newsletters if n.slug == forced_newsletter_slug]
        if match:
            newsletters = match

    # Current counts per (condition, newsletter_id).
    forced_preview = forced_condition in all_conditions or bool(forced_newsletter_slug)
    phase = (
        StudyPhase.PREVIEW
        if forced_preview
        else getattr(settings, "STUDY_PHASE", StudyPhase.PILOT)
    )
    if phase not in StudyPhase.values:
        phase = StudyPhase.PILOT
    counts = {
        (row["condition"], row["newsletter_id"]): row["n"]
        for row in Participant.objects.filter(study_phase=phase)
        .values("condition", "newsletter_id")
        .annotate(n=Count("id"))
    }

    cells = [(c, n) for c in conditions for n in newsletters]
    min_count = min(counts.get((c, n.id), 0) for c, n in cells)
    candidates = [(c, n) for c, n in cells if counts.get((c, n.id), 0) == min_count]
    return random.choice(candidates)
