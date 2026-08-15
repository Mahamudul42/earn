import csv
import json

from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsResearcher, IsStudyManager
from apps.users.roles import is_human_rater

from .assignment import choose_cell
from .assistant import (
    ACTION_NONE,
    AssistantUnavailable,
    compose_final_feedback,
    get_assistant_reply,
)
from .models import (
    ActionabilityRating,
    Condition,
    FeedbackResponse,
    Participant,
    StudyPhase,
    SurveyResponse,
)
from .serializers import (
    AssistantTurnSerializer,
    BlindFeedbackSerializer,
    ChatMessageSerializer,
    FeedbackDetailSerializer,
    FinalFeedbackSerializer,
    InitialFeedbackSerializer,
    RatingSerializer,
    SessionSerializer,
    StartSessionSerializer,
    SurveyResponseSerializer,
)

DIMENSIONS = (
    "target_specificity",
    "direction_operation",
    "collection_allocation",
    "context_persistence",
    "system_feasibility",
)

# Shown when the local model cannot be reached. No canned reply is sent in its
# place.
ASSISTANT_UNAVAILABLE_DETAIL = (
    "The feedback assistant is temporarily unavailable. Please try again, or "
    "submit the feedback you have already written."
)


def _get_participant(public_id) -> Participant:
    return get_object_or_404(
        Participant.objects.select_related("newsletter"), public_id=public_id
    )


def _chat_entry(role: str, content: str, **extra) -> dict:
    return {"role": role, "content": content, "ts": timezone.now().isoformat(), **extra}


def _assistant_unavailable() -> Response:
    return Response(
        {"detail": ASSISTANT_UNAVAILABLE_DETAIL},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


# --- Participant flow (public) ---------------------------------------------
class StartSessionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        condition, newsletter = choose_cell(
            forced_condition=serializer.validated_data.get("condition"),
            forced_newsletter_slug=serializer.validated_data.get("newsletter") or None,
        )
        forced_preview = bool(
            serializer.validated_data.get("condition")
            or serializer.validated_data.get("newsletter")
        )
        from django.conf import settings

        configured_phase = getattr(settings, "STUDY_PHASE", StudyPhase.PILOT)
        if configured_phase not in StudyPhase.values:
            configured_phase = StudyPhase.PILOT
        participant = Participant.objects.create(
            condition=condition,
            newsletter=newsletter,
            recruitment_source=serializer.validated_data["recruitment_source"],
            external_ref=serializer.validated_data.get("external_ref", ""),
            study_phase=(StudyPhase.PREVIEW if forced_preview else configured_phase),
        )
        return Response(
            SessionSerializer(participant).data, status=status.HTTP_201_CREATED
        )


class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        participant = _get_participant(public_id)
        return Response(SessionSerializer(participant).data)


class ConsentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        if participant.consented_at is None:
            participant.consented_at = timezone.now()
            participant.status = Participant.Status.CONSENTED
            participant.save(update_fields=["consented_at", "status"])
        return Response(SessionSerializer(participant).data)


class InitialFeedbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        serializer = InitialFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        initial = serializer.validated_data["initial_text"]

        feedback, _ = FeedbackResponse.objects.get_or_create(participant=participant)
        feedback.initial_text = initial

        if participant.condition == Condition.ASSISTANT:
            # (Re)start the conversation from this initial feedback.
            log = [_chat_entry("user", initial)]
            try:
                result = get_assistant_reply(log, newsletter=participant.newsletter)
            except AssistantUnavailable:
                # Keep the participant's words; they can retry or submit as-is.
                feedback.save()
                return _assistant_unavailable()
            log.append(
                _chat_entry("assistant", result.message, action=result.action)
            )
            feedback.chat_log = log
            feedback.assistant_action = result.action
            feedback.assistant_message = result.message
            feedback.save()
            participant.status = Participant.Status.FEEDBACK
            participant.save(update_fields=["status"])
            return Response(
                AssistantTurnSerializer(
                    {
                        "action": result.action,
                        "message": result.message,
                        "assistant_turns": 1,
                    }
                ).data
            )

        # Conditions 1 and 2: the initial response is also the final response.
        feedback.final_text = initial
        feedback.assistant_action = ACTION_NONE
        feedback.save()
        participant.status = Participant.Status.FEEDBACK
        participant.save(update_fields=["status"])
        return Response(
            AssistantTurnSerializer({"action": ACTION_NONE, "message": ""}).data
        )


class AssistantChatView(APIView):
    """Condition 3 only: one more round of the feedback-assistant conversation.

    Appends the participant's follow-up message to the stored chat log, asks the
    assistant for its next reply (question/suggestion, or "ok" once the combined
    feedback is actionable), stores it, and returns it. The participant always
    stays in control: submitting the final feedback is a separate, explicit step
    (``FinalFeedbackView``)."""

    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        if participant.condition != Condition.ASSISTANT:
            return Response(
                {"detail": "This session does not include the feedback assistant."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = get_object_or_404(FeedbackResponse, participant=participant)

        log = list(feedback.chat_log or [])
        if not log and feedback.initial_text:
            # Safety: sessions created before the chat log existed.
            log = [_chat_entry("user", feedback.initial_text)]
        log.append(_chat_entry("user", serializer.validated_data["message"]))

        try:
            result = get_assistant_reply(log, newsletter=participant.newsletter)
        except AssistantUnavailable:
            # Persist what the participant said so their message is not lost,
            # then report the outage.
            feedback.chat_log = log
            feedback.save(update_fields=["chat_log", "updated_at"])
            return _assistant_unavailable()

        log.append(_chat_entry("assistant", result.message, action=result.action))
        feedback.chat_log = log
        feedback.assistant_action = result.action
        feedback.assistant_message = result.message
        feedback.save(
            update_fields=[
                "chat_log",
                "assistant_action",
                "assistant_message",
                "updated_at",
            ]
        )
        return Response(
            AssistantTurnSerializer(
                {
                    "action": result.action,
                    "message": result.message,
                    "assistant_turns": sum(
                        1 for m in log if m.get("role") == "assistant"
                    ),
                }
            ).data
        )


class FinalDraftView(APIView):
    """Condition 3: consolidate the whole conversation into ONE submission-ready
    feedback draft in the participant's own voice, using only what they said.
    It is prefilled in the confirm-and-submit panel. The participant can edit it
    and has to confirm before it is submitted."""

    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        if participant.condition != Condition.ASSISTANT:
            return Response(
                {"detail": "This session does not include the feedback assistant."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        feedback = get_object_or_404(FeedbackResponse, participant=participant)
        log = list(feedback.chat_log or [])
        if not log and feedback.initial_text:
            log = [_chat_entry("user", feedback.initial_text)]
        try:
            draft = compose_final_feedback(log, newsletter=participant.newsletter)
        except AssistantUnavailable:
            return _assistant_unavailable()
        feedback.final_draft = draft
        feedback.save(update_fields=["final_draft", "updated_at"])
        return Response({"draft": draft})


class FinalFeedbackView(APIView):
    """Used by Condition 3 to submit the final response after the assistant round.
    Also accepted for Conditions 1 & 2 if the client lets participants edit."""

    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        serializer = FinalFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = get_object_or_404(FeedbackResponse, participant=participant)
        feedback.final_text = serializer.validated_data["final_text"]
        feedback.time_on_task_seconds = serializer.validated_data.get(
            "time_on_task_seconds"
        )
        feedback.revision_count = serializer.validated_data.get("revision_count", 0)
        feedback.save(
            update_fields=["final_text", "time_on_task_seconds", "revision_count"]
        )
        return Response({"status": "ok"})


class SurveyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_id):
        participant = _get_participant(public_id)
        serializer = SurveyResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SurveyResponse.objects.update_or_create(
            participant=participant, defaults=serializer.validated_data
        )
        participant.status = Participant.Status.COMPLETED
        participant.completed_at = timezone.now()
        participant.save(update_fields=["status", "completed_at"])
        return Response({"status": "completed"})


# --- Researcher dashboard ---------------------------------------------------
class OverviewView(APIView):
    permission_classes = [IsStudyManager]

    def get(self, request):
        cells = list(
            Participant.objects.values("condition", "newsletter__slug").annotate(
                n=Count("id"),
                completed=Count("id", filter=Q(status=Participant.Status.COMPLETED)),
            )
        )
        per_condition = {
            c.value: {"label": c.label, "n": 0, "completed": 0} for c in Condition
        }
        for row in cells:
            bucket = per_condition[row["condition"]]
            bucket["n"] += row["n"]
            bucket["completed"] += row["completed"]

        total = Participant.objects.count()
        completed = Participant.objects.filter(
            status=Participant.Status.COMPLETED
        ).count()
        with_final = FeedbackResponse.objects.exclude(final_text="").count()
        rated = FeedbackResponse.objects.filter(ratings__isnull=False).distinct().count()
        return Response(
            {
                "total_participants": total,
                "completed": completed,
                "responses_with_final_text": with_final,
                "responses_rated": rated,
                "per_condition": per_condition,
                "cells": cells,
            }
        )


class ResponseListView(APIView):
    permission_classes = [IsResearcher]

    def get(self, request):
        qs = (
            FeedbackResponse.objects.exclude(final_text="")
            .select_related("participant", "participant__newsletter")
            .prefetch_related("ratings", "ratings__rater")
            .order_by("-created_at")
        )
        condition = request.query_params.get("condition")
        if condition:
            qs = qs.filter(participant__condition=condition)
        newsletter = request.query_params.get("newsletter")
        if newsletter:
            qs = qs.filter(participant__newsletter__slug=newsletter)
        phase = request.query_params.get("phase")
        if phase in StudyPhase.values:
            qs = qs.filter(participant__study_phase=phase)
        blind_queue = (
            request.query_params.get("unrated") == "1" or is_human_rater(request.user)
        )
        if blind_queue:
            qs = qs.exclude(ratings__rater=request.user)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer_class = (
            BlindFeedbackSerializer if blind_queue else FeedbackDetailSerializer
        )
        data = serializer_class(page, many=True).data
        return paginator.get_paginated_response(data)


class ResponseDetailView(APIView):
    permission_classes = [IsStudyManager]

    def get(self, request, pk):
        feedback = get_object_or_404(
            FeedbackResponse.objects.select_related(
                "participant", "participant__newsletter"
            ).prefetch_related("ratings"),
            pk=pk,
        )
        return Response(FeedbackDetailSerializer(feedback).data)


class RatingCreateView(APIView):
    permission_classes = [IsResearcher]

    def post(self, request, pk):
        feedback = get_object_or_404(FeedbackResponse, pk=pk)
        if ActionabilityRating.objects.filter(
            feedback=feedback, rater=request.user
        ).exists():
            return Response(
                {"detail": "You have already rated this response."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = RatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rating = ActionabilityRating.objects.create(
                feedback=feedback, rater=request.user, **serializer.validated_data
            )
        except IntegrityError:
            return Response(
                {"detail": "You have already rated this response."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)


class ExportView(APIView):
    """Flat CSV of every response for analysis in R/Python."""

    permission_classes = [IsStudyManager]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=earn_export.csv"
        writer = csv.writer(response)
        writer.writerow(
            [
                "public_id",
                "condition",
                "condition_label",
                "newsletter",
                "recruitment_source",
                "study_phase",
                "status",
                "initial_text",
                "final_text",
                # Condition-3 consolidation: the LLM-assembled draft shown in the
                # confirm panel (final_draft) vs what the participant actually
                # submitted (final_text) supports the faithfulness / edit analysis.
                "final_draft",
                "assistant_action",
                "assistant_turns",
                "revision_count",
                "time_on_task_seconds",
                # survey (4 scale-estimation items, 1-5)
                "effort",
                "express",
                "reflect",
                "understand",
                # ratings (human)
                "n_ratings",
                "mean_actionability_total",
                *[f"mean_{dimension}" for dimension in DIMENSIONS],
                "target_levels_json",
                # Full Condition-3 conversation as JSON (empty for conditions 1 & 2).
                "chat_log_json",
            ]
        )
        participants = (
            Participant.objects.select_related("newsletter", "feedback", "survey")
            .prefetch_related("feedback__ratings")
            .order_by("created_at")
        )
        for p in participants:
            fb = getattr(p, "feedback", None)
            sv = getattr(p, "survey", None)
            ratings = list(fb.ratings.all()) if fb else []
            mean_total = (
                round(sum(r.total for r in ratings) / len(ratings), 3) if ratings else ""
            )
            writer.writerow(
                [
                    p.public_id,
                    p.condition,
                    Condition(p.condition).label,
                    p.newsletter.slug,
                    p.recruitment_source,
                    p.study_phase,
                    p.status,
                    fb.initial_text if fb else "",
                    fb.final_text if fb else "",
                    fb.final_draft if fb else "",
                    fb.assistant_action if fb else "",
                    (
                        sum(
                            1
                            for m in (fb.chat_log or [])
                            if m.get("role") == "assistant"
                        )
                        if fb
                        else ""
                    ),
                    fb.revision_count if fb else "",
                    fb.time_on_task_seconds if fb else "",
                    *(
                        [sv.effort, sv.express, sv.reflect, sv.understand]
                        if sv
                        else [""] * 4
                    ),
                    len(ratings),
                    mean_total,
                    *(
                        [
                            round(
                                sum(getattr(r, dimension) for r in ratings)
                                / len(ratings),
                                3,
                            )
                            for dimension in DIMENSIONS
                        ]
                        if ratings
                        else [""] * len(DIMENSIONS)
                    ),
                    json.dumps([r.target_level for r in ratings]),
                    (
                        json.dumps(fb.chat_log, ensure_ascii=False)
                        if fb and fb.chat_log
                        else ""
                    ),
                ]
            )
        return response
