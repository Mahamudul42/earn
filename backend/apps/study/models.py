"""Data model for the EARN feedback-elicitation experiment.

The experiment is between-subjects with three feedback-elicitation conditions
(Just Ask / Examples + Instructions / Interactive Feedback Assistant) and a
small fixed set of realistic newsletter stimuli. Each participant is randomly
assigned one newsletter and one condition, reads the newsletter, writes
feedback, and completes a post-task survey. Researchers later score each final
feedback response with the five-dimension actionability rubric.
"""

import uuid

from django.conf import settings
from django.db import models


class Condition(models.IntegerChoices):
    JUST_ASK = 1, "Base prompt"
    EXAMPLES = 2, "Base prompt + examples"
    ASSISTANT = 3, "Base prompt + assistant guidance"


class RecruitmentSource(models.TextChoices):
    DIRECT = "direct", "Direct link"
    MOVIELENS = "movielens", "MovieLens"
    PROLIFIC = "prolific", "Prolific"
    OTHER = "other", "Other"


class StudyPhase(models.TextChoices):
    PREVIEW = "preview", "Preview / demo"
    PILOT = "pilot", "Pilot"
    MAIN = "main", "Main experiment"


class TargetLevel(models.TextChoices):
    ARTICLE = "article", "Individual article"
    SECTION = "section", "Newsletter section"
    COLLECTION = "collection", "Whole newsletter collection"
    UNCLEAR = "unclear", "Unclear / mixed"


class Newsletter(models.Model):
    """A fixed-format newsletter stimulus.

    Format is intentionally fixed (five sections, three articles each). Only the
    content can be commented on — this mirrors the participant-facing framing in
    the study design.
    """

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    # The masthead date is not stored: it is rendered from today's date by
    # content.current_edition_label() so the stimulus never reads as stale.
    # sections: list of {"name": str, "articles": [{"label","headline","summary","image","url"}]}
    sections = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return f"{self.title} ({self.slug})"


class Participant(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CONSENTED = "consented", "Consented"
        FEEDBACK = "feedback", "Submitted feedback"
        COMPLETED = "completed", "Completed"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    condition = models.IntegerField(choices=Condition.choices)
    newsletter = models.ForeignKey(
        Newsletter, on_delete=models.PROTECT, related_name="participants"
    )
    recruitment_source = models.CharField(
        max_length=20,
        choices=RecruitmentSource.choices,
        default=RecruitmentSource.DIRECT,
    )
    external_ref = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional recruitment id, e.g. a Prolific PID passed as a query param.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED
    )
    consented_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    study_phase = models.CharField(
        max_length=12, choices=StudyPhase.choices, default=StudyPhase.PILOT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"P:{self.public_id} C{self.condition} {self.newsletter.slug}"


class FeedbackResponse(models.Model):
    """The participant's open-ended newsletter feedback.

    For Conditions 1 and 2 ``initial_text`` and ``final_text`` are the same. For
    Condition 3 we retain the initial response, the full assistant conversation
    (``chat_log``), and the final confirmed response, to support the
    assistant-faithfulness analysis.
    """

    class AssistantAction(models.TextChoices):
        NONE = "none", "No assistant round"
        SUGGESTION = "suggestion", "Concrete suggestion"
        QUESTION = "question", "Clarifying question"
        OK = "ok", "Already actionable"

    participant = models.OneToOneField(
        Participant, on_delete=models.CASCADE, related_name="feedback"
    )
    initial_text = models.TextField(blank=True)
    final_text = models.TextField(blank=True)
    assistant_action = models.CharField(
        max_length=12, choices=AssistantAction.choices, default=AssistantAction.NONE
    )
    assistant_message = models.TextField(
        blank=True, help_text="The latest assistant response shown in Condition 3."
    )
    # Full Condition-3 conversation, oldest first. Each entry:
    # {"role": "user"|"assistant", "content": str, "action": str?, "ts": iso-datetime}
    chat_log = models.JSONField(default=list, blank=True)
    # The consolidated draft shown in the confirm-and-submit panel (Condition 3),
    # assembled from everything the participant said. Comparing it with
    # final_text shows how much the participant edited before submitting.
    final_draft = models.TextField(blank=True)
    revision_count = models.PositiveIntegerField(default=0)
    time_on_task_seconds = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback<{self.participant.public_id}>"


class SurveyResponse(models.Model):
    """Compact post-task survey: four items, each stored as a 1–5 magnitude
    ("scale-estimation") response. Each item measures a distinct construct:
    effort (cost), self-efficacy, a seriousness check, and perceived
    actionability."""

    participant = models.OneToOneField(
        Participant, on_delete=models.CASCADE, related_name="survey"
    )
    # Effort (cost): "How much effort did it take to write your feedback?"
    # 1 = Very little … 5 = A lot (higher = more effort).
    effort = models.PositiveSmallIntegerField()
    # Self-efficacy: "How much were you able to express what you wanted?"
    express = models.PositiveSmallIntegerField()
    # Seriousness check: "How much does your feedback reflect what you actually
    # want in your newsletter?"
    reflect = models.PositiveSmallIntegerField()
    # Perceived actionability: "How much would someone reading your feedback
    # understand what you want changed?"
    understand = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Survey<{self.participant.public_id}>"


class ActionabilityRating(models.Model):
    """A single human score of a final feedback response against the
    five-dimension rubric. Each dimension is 0/1/2; total is 0–10.

    Each rater may score a given response only once. Ratings are entered blind:
    the rater never sees the condition or any other rater's score.
    """

    feedback = models.ForeignKey(
        FeedbackResponse, on_delete=models.CASCADE, related_name="ratings"
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ratings",
    )

    target_specificity = models.PositiveSmallIntegerField()
    direction_operation = models.PositiveSmallIntegerField()
    collection_allocation = models.PositiveSmallIntegerField()
    context_persistence = models.PositiveSmallIntegerField()
    system_feasibility = models.PositiveSmallIntegerField()

    target_level = models.CharField(
        max_length=12, choices=TargetLevel.choices, blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["feedback", "rater"],
                name="unique_rating_per_rater_per_response",
            )
        ]

    @property
    def total(self) -> int:
        return (
            self.target_specificity
            + self.direction_operation
            + self.collection_allocation
            + self.context_persistence
            + self.system_feasibility
        )

    def __str__(self):
        return f"Rating<{self.feedback_id}> total={self.total}"
