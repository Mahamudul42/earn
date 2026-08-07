import csv
import json
from pathlib import Path

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsResearcher

from . import content
from .assignment import choose_cell
from .assistant import (
    ACTION_NONE,
    SYSTEM_PROMPT,
    active_model,
    active_provider,
    compose_final_feedback,
    get_assistant_reply,
    live_check,
    provider_status,
    run_model,
)
from .models import (
    ActionabilityRating,
    Condition,
    FeedbackResponse,
    Newsletter,
    Participant,
    SurveyResponse,
)
from .serializers import (
    AssistantTurnSerializer,
    ChatMessageSerializer,
    FeedbackDetailSerializer,
    FinalFeedbackSerializer,
    InitialFeedbackSerializer,
    RatingSerializer,
    SessionSerializer,
    StartSessionSerializer,
    SurveyResponseSerializer,
)


def _get_participant(public_id) -> Participant:
    return get_object_or_404(
        Participant.objects.select_related("newsletter"), public_id=public_id
    )


def _chat_entry(role: str, content: str, **extra) -> dict:
    return {"role": role, "content": content, "ts": timezone.now().isoformat(), **extra}


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
        participant = Participant.objects.create(
            condition=condition,
            newsletter=newsletter,
            recruitment_source=serializer.validated_data["recruitment_source"],
            external_ref=serializer.validated_data.get("external_ref", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
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
            result = get_assistant_reply(log, newsletter=participant.newsletter)
            log.append(
                _chat_entry(
                    "assistant",
                    result.message,
                    action=result.action,
                    used_llm=result.used_llm,
                    provider=result.provider,
                )
            )
            feedback.chat_log = log
            feedback.assistant_action = result.action
            feedback.assistant_message = result.message
            feedback.assistant_used_llm = result.used_llm
            feedback.save()
            participant.status = Participant.Status.FEEDBACK
            participant.save(update_fields=["status"])
            return Response(
                AssistantTurnSerializer(
                    {
                        "action": result.action,
                        "message": result.message,
                        "used_llm": result.used_llm,
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
            AssistantTurnSerializer(
                {"action": ACTION_NONE, "message": "", "used_llm": False}
            ).data
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

        result = get_assistant_reply(log, newsletter=participant.newsletter)
        log.append(
            _chat_entry(
                "assistant",
                result.message,
                action=result.action,
                used_llm=result.used_llm,
                provider=result.provider,
            )
        )
        feedback.chat_log = log
        feedback.assistant_action = result.action
        feedback.assistant_message = result.message
        feedback.assistant_used_llm = result.used_llm
        feedback.save(
            update_fields=[
                "chat_log",
                "assistant_action",
                "assistant_message",
                "assistant_used_llm",
                "updated_at",
            ]
        )
        return Response(
            AssistantTurnSerializer(
                {
                    "action": result.action,
                    "message": result.message,
                    "used_llm": result.used_llm,
                    "assistant_turns": sum(
                        1 for m in log if m.get("role") == "assistant"
                    ),
                }
            ).data
        )


class FinalDraftView(APIView):
    """Condition 3: consolidate the whole conversation into ONE submission-ready
    feedback draft in the participant's own voice (first person, only stated
    preferences). Shown prefilled in the confirm-and-submit panel; the
    participant can edit it freely and must explicitly confirm — it is never
    auto-submitted."""

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
        draft, used_llm = compose_final_feedback(log, newsletter=participant.newsletter)
        feedback.final_draft = draft
        feedback.save(update_fields=["final_draft", "updated_at"])
        return Response({"draft": draft, "used_llm": used_llm})


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
    permission_classes = [IsResearcher]

    def get(self, request):
        cells = list(
            Participant.objects.values("condition", "newsletter__slug").annotate(
                n=Count("id"),
                completed=Count("id", filter=Q(status=Participant.Status.COMPLETED)),
            )
        )
        per_condition = {c.value: {"label": c.label, "n": 0, "completed": 0} for c in Condition}
        for row in cells:
            bucket = per_condition[row["condition"]]
            bucket["n"] += row["n"]
            bucket["completed"] += row["completed"]

        total = Participant.objects.count()
        completed = Participant.objects.filter(
            status=Participant.Status.COMPLETED
        ).count()
        with_final = FeedbackResponse.objects.exclude(final_text="").count()
        rated = (
            FeedbackResponse.objects.filter(ratings__is_llm=False)
            .distinct()
            .count()
        )
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
        if request.query_params.get("unrated") == "1":
            qs = qs.exclude(ratings__rater=request.user)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request)
        data = FeedbackDetailSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class ResponseDetailView(APIView):
    permission_classes = [IsResearcher]

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
        serializer = RatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating = ActionabilityRating.objects.create(
            feedback=feedback, rater=request.user, **serializer.validated_data
        )
        return Response(
            RatingSerializer(rating).data, status=status.HTTP_201_CREATED
        )


class ExportView(APIView):
    """Flat CSV of every completed-or-final response for analysis in R/Python."""

    permission_classes = [IsResearcher]

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
                "status",
                "initial_text",
                "final_text",
                # Condition-3 consolidation: the LLM-assembled draft shown in the
                # confirm panel (final_draft) vs what the participant actually
                # submitted (final_text) supports the faithfulness / edit analysis.
                "final_draft",
                "assistant_action",
                "assistant_used_llm",
                "assistant_turns",
                "revision_count",
                "time_on_task_seconds",
                # survey (4 scale-estimation items, 1-5)
                "effort",
                "express",
                "reflect",
                "understand",
                # ratings
                "n_human_ratings",
                "mean_actionability_total",
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
            human = (
                [r.total for r in fb.ratings.all() if not r.is_llm] if fb else []
            )
            mean_total = round(sum(human) / len(human), 3) if human else ""
            writer.writerow(
                [
                    p.public_id,
                    p.condition,
                    Condition(p.condition).label,
                    p.newsletter.slug,
                    p.recruitment_source,
                    p.status,
                    fb.initial_text if fb else "",
                    fb.final_text if fb else "",
                    fb.final_draft if fb else "",
                    fb.assistant_action if fb else "",
                    fb.assistant_used_llm if fb else "",
                    (
                        sum(1 for m in (fb.chat_log or []) if m.get("role") == "assistant")
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
                    len(human),
                    mean_total,
                    (
                        json.dumps(fb.chat_log, ensure_ascii=False)
                        if fb and fb.chat_log
                        else ""
                    ),
                ]
            )
        return response


# --- Prompt playground (researcher tool) ------------------------------------
_SAMPLES_FILE = Path(__file__).resolve().parent / "seed_data" / "collected_samples.csv"
_MAX_SAMPLES_PER_RUN = 25


def _load_collected_samples() -> list[str]:
    """Feedback texts collected via the pilot Google Form (bundled CSV)."""
    if not _SAMPLES_FILE.exists():
        return []
    out = []
    with _SAMPLES_FILE.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    # The feedback text is the last non-timestamp column; use column index 1 when
    # present, else the last column.
    for row in rows[1:]:
        text = (row[1] if len(row) > 1 else (row[-1] if row else "")).strip()
        if text:
            out.append(text)
    return out


class PromptLabDefaultView(APIView):
    """Return the current live Condition-3 system prompt as a starting point."""

    permission_classes = [IsResearcher]

    def get(self, request):
        return Response({"system_prompt": SYSTEM_PROMPT})


class PromptLabSamplesView(APIView):
    """Return feedback samples to try prompts against: the bundled pilot samples
    (?source=collected) or recent responses collected in this study (?source=study)."""

    permission_classes = [IsResearcher]

    def get(self, request):
        source = request.query_params.get("source", "collected")
        try:
            limit = min(int(request.query_params.get("limit", 30)), 100)
        except ValueError:
            limit = 30
        if source == "study":
            samples = list(
                FeedbackResponse.objects.exclude(final_text="")
                .order_by("-created_at")
                .values_list("final_text", flat=True)[:limit]
            )
        else:
            samples = _load_collected_samples()[:limit]
        return Response({"source": source, "samples": samples})


class PromptLabRunView(APIView):
    """Run a system-prompt variant against a set of sample feedback texts and
    return each model response, so the researcher can compare prompts."""

    permission_classes = [IsResearcher]

    def post(self, request):
        system_prompt = (request.data.get("system_prompt") or "").strip()
        samples = request.data.get("samples") or []
        if not system_prompt:
            return Response(
                {"detail": "system_prompt is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(samples, list) or not samples:
            return Response(
                {"detail": "Provide a non-empty list of sample feedback texts."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        samples = [str(s).strip() for s in samples if str(s).strip()][
            :_MAX_SAMPLES_PER_RUN
        ]
        provider = active_provider()
        model = active_model()
        results = []
        for sample in samples:
            try:
                response_text = run_model(system_prompt, sample, max_tokens=1024)
                results.append({"sample": sample, "response": response_text, "ok": True})
            except Exception as exc:  # noqa: BLE001 - surface the error per-row
                results.append(
                    {"sample": sample, "response": "", "ok": False, "error": str(exc)[:200]}
                )
        return Response(
            {
                "count": len(results),
                "provider": provider,
                "model": model,
                "results": results,
            }
        )


class PromptLabStatusView(APIView):
    """Report which LLM provider/model is active and whether a live request
    succeeds — so the researcher can see (and explain) what actually answered."""

    permission_classes = [IsResearcher]

    def get(self, request):
        return Response(live_check())
