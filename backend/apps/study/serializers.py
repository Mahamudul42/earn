from rest_framework import serializers

from . import content
from .models import (
    ActionabilityRating,
    FeedbackResponse,
    Newsletter,
    Participant,
    SurveyResponse,
)


class NewsletterSerializer(serializers.ModelSerializer):
    # Rendered from today's date rather than stored, so the stimulus never
    # reads as stale. See content.current_edition_label().
    edition_label = serializers.SerializerMethodField()

    class Meta:
        model = Newsletter
        fields = ["slug", "title", "edition_label", "sections"]

    def get_edition_label(self, obj):
        return content.current_edition_label()


class SessionSerializer(serializers.ModelSerializer):
    """What the participant client receives about its own session."""

    newsletter = NewsletterSerializer(read_only=True)
    condition_config = serializers.SerializerMethodField()
    consent_text = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = [
            "public_id",
            "condition",
            "status",
            "newsletter",
            "condition_config",
            "consent_text",
        ]

    def get_condition_config(self, obj):
        return content.condition_config(obj.condition)

    def get_consent_text(self, obj):
        return content.CONSENT_TEXT


class StartSessionSerializer(serializers.Serializer):
    recruitment_source = serializers.ChoiceField(
        choices=[
            c[0] for c in Participant._meta.get_field("recruitment_source").choices
        ],
        required=False,
        default="direct",
    )
    external_ref = serializers.CharField(required=False, allow_blank=True, default="")
    # Optional preview controls (for demos): force a specific condition (1-3)
    # and/or a specific newsletter slug. Omitted for real participants, who get
    # balanced random assignment.
    condition = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=3
    )
    newsletter = serializers.CharField(required=False, allow_blank=True, default="")


class InitialFeedbackSerializer(serializers.Serializer):
    initial_text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class AssistantTurnSerializer(serializers.Serializer):
    """One assistant round. For conditions 1 & 2 ``action`` is 'none'. For
    condition 3 it carries the question/suggestion/ok message plus how many
    assistant rounds have run so far in this conversation."""

    action = serializers.CharField()
    message = serializers.CharField(allow_blank=True)
    assistant_turns = serializers.IntegerField(required=False, default=0)


class ChatMessageSerializer(serializers.Serializer):
    """A follow-up message from the participant in the Condition-3 chat."""

    message = serializers.CharField(allow_blank=False, trim_whitespace=True)


class FinalFeedbackSerializer(serializers.Serializer):
    final_text = serializers.CharField(allow_blank=False, trim_whitespace=True)
    time_on_task_seconds = serializers.IntegerField(required=False, min_value=0)
    revision_count = serializers.IntegerField(required=False, min_value=0, default=0)


class SurveyResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyResponse
        exclude = ["id", "participant", "created_at"]

    def validate(self, attrs):
        for field, value in attrs.items():
            if not (1 <= value <= 5):
                raise serializers.ValidationError(
                    {field: "Each survey item must be a 1–5 Likert response."}
                )
        return attrs


# --- Researcher-facing serializers -----------------------------------------
class RatingSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(read_only=True)
    rater_username = serializers.CharField(source="rater.username", read_only=True)

    class Meta:
        model = ActionabilityRating
        fields = [
            "id",
            "rater_username",
            "target_specificity",
            "direction_operation",
            "collection_allocation",
            "context_persistence",
            "system_feasibility",
            "target_level",
            "notes",
            "total",
            "created_at",
        ]
        read_only_fields = ["id", "rater_username", "total", "created_at"]

    def validate(self, attrs):
        for dim in (
            "target_specificity",
            "direction_operation",
            "collection_allocation",
            "context_persistence",
            "system_feasibility",
        ):
            if dim in attrs and not (0 <= attrs[dim] <= 2):
                raise serializers.ValidationError(
                    {dim: "Each rubric dimension is scored 0, 1, or 2."}
                )
        return attrs


class FeedbackDetailSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(source="participant.public_id", read_only=True)
    condition = serializers.IntegerField(source="participant.condition", read_only=True)
    newsletter = serializers.CharField(
        source="participant.newsletter.slug", read_only=True
    )
    recruitment_source = serializers.CharField(
        source="participant.recruitment_source", read_only=True
    )
    study_phase = serializers.CharField(source="participant.study_phase", read_only=True)
    ratings = RatingSerializer(many=True, read_only=True)
    mean_total = serializers.SerializerMethodField()

    class Meta:
        model = FeedbackResponse
        fields = [
            "id",
            "public_id",
            "condition",
            "newsletter",
            "recruitment_source",
            "study_phase",
            "initial_text",
            "final_text",
            "assistant_action",
            "assistant_message",
            "chat_log",
            "final_draft",
            "revision_count",
            "time_on_task_seconds",
            "ratings",
            "mean_total",
            "created_at",
        ]

    def get_mean_total(self, obj):
        totals = [r.total for r in obj.ratings.all()]
        return round(sum(totals) / len(totals), 2) if totals else None


class BlindFeedbackSerializer(serializers.ModelSerializer):
    """Only the final response needed for condition-blind human scoring."""

    class Meta:
        model = FeedbackResponse
        fields = ["id", "final_text"]
