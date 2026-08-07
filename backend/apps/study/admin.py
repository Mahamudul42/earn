from django.contrib import admin

from .models import (
    ActionabilityRating,
    FeedbackResponse,
    Newsletter,
    Participant,
    SurveyResponse,
)


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "is_active")
    list_filter = ("is_active",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "condition",
        "newsletter",
        "status",
        "recruitment_source",
        "study_phase",
        "created_at",
    )
    list_filter = (
        "condition",
        "status",
        "study_phase",
        "recruitment_source",
        "newsletter",
    )
    search_fields = ("public_id", "external_ref")


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(admin.ModelAdmin):
    list_display = ("participant", "assistant_action", "revision_count", "created_at")
    list_filter = ("assistant_action",)


@admin.register(ActionabilityRating)
class ActionabilityRatingAdmin(admin.ModelAdmin):
    list_display = ("feedback", "rater", "total", "created_at")


admin.site.register(SurveyResponse)
