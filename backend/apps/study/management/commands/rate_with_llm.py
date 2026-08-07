"""Score final feedback responses with an LLM actionability rater.

Runs the same five-dimension actionability rubric the human raters use over each
final feedback text, using only the configured local LLM,
and stores the result as an ``ActionabilityRating`` with ``is_llm=True`` and no
human rater. This lets scoring scale and be validated against the human ratings
(the researcher dashboard and CSV export already separate human vs LLM ratings).

Idempotent: responses that already have an LLM rating are skipped unless
``--refresh`` is passed. Transient provider failures (e.g. a free-tier
rate-limit spike) leave that response unrated, so simply re-running the command
picks up whatever was missed. Use ``--sleep`` to throttle large batches under a
provider's per-minute token limit.

    python manage.py rate_with_llm                 # rate every unrated response
    python manage.py rate_with_llm --condition 3   # only Condition 3
    python manage.py rate_with_llm --limit 50      # cap this run
    python manage.py rate_with_llm --sleep 2       # pause 2s between calls
    python manage.py rate_with_llm --refresh       # re-rate, replacing old LLM ratings
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from apps.study.assistant import (
    RATING_DIMENSIONS,
    active_model,
    active_provider,
    llm_rate_feedback,
)
from apps.study.models import ActionabilityRating, FeedbackResponse


class Command(BaseCommand):
    help = "Score final feedback with the LLM actionability rater (is_llm=True)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--condition", type=int, choices=[1, 2, 3], default=None,
            help="Only rate responses from this condition.",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Max responses to rate this run."
        )
        parser.add_argument(
            "--refresh", action="store_true",
            help="Re-rate responses that already have an LLM rating (replaces it).",
        )
        parser.add_argument(
            "--sleep", type=float, default=0.0,
            help="Seconds to pause between responses (throttle for rate limits).",
        )

    def handle(self, *args, **opts):
        qs = (
            FeedbackResponse.objects.exclude(final_text="")
            .select_related("participant", "participant__newsletter")
            .order_by("created_at")
        )
        if opts["condition"]:
            qs = qs.filter(participant__condition=opts["condition"])
        if not opts["refresh"]:
            existing_llm = ActionabilityRating.objects.filter(
                feedback=OuterRef("pk"), is_llm=True
            )
            qs = qs.exclude(Exists(existing_llm))
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        self.stdout.write(
            f"LLM rater: provider={active_provider()} model={active_model()}"
        )
        rated = failed = 0
        for i, fb in enumerate(qs):
            if i and opts["sleep"]:
                time.sleep(opts["sleep"])
            newsletter = getattr(fb.participant, "newsletter", None)
            scores = llm_rate_feedback(fb.final_text, newsletter=newsletter)
            if scores is None:
                failed += 1
                self.stderr.write(
                    self.style.WARNING(f"  ! no rating for {fb.participant.public_id}")
                )
                continue
            if opts["refresh"]:
                ActionabilityRating.objects.filter(feedback=fb, is_llm=True).delete()
            ActionabilityRating.objects.create(
                feedback=fb, rater=None, is_llm=True, **scores
            )
            rated += 1
            total = sum(scores[d] for d in RATING_DIMENSIONS)
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ {fb.participant.public_id} total={total}/10")
            )
        style = self.style.SUCCESS if failed == 0 else self.style.WARNING
        self.stdout.write(style(f"Done. rated={rated} failed={failed}"))
