"""Tests for assignment, the Condition 3 assistant, the participant flow and
researcher permissions.

Tests that need a conversation stub the model call. Tests for the outage path
leave it unstubbed.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.study import assistant as assistant_module
from apps.study.assistant import (
    ACTION_OK,
    ACTION_QUESTION,
    AssistantUnavailable,
    _VALID_ACTIONS,
    _parse_assistant_json,
    compose_final_feedback,
    get_assistant_reply,
    render_newsletter_context,
)
from apps.study.models import (
    ActionabilityRating,
    Condition,
    FeedbackResponse,
    Newsletter,
    Participant,
    SurveyResponse,
    StudyPhase,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def _no_live_llm(settings):
    """Keep tests off the network."""
    settings.LOCAL_LLM_BASE_URL = ""
    settings.LOCAL_LLM_API_KEY = ""


@pytest.fixture
def fake_llm(monkeypatch):
    """Stub the local model. Returns the list of messages sent on each call."""
    calls = []

    def _fake_chat(messages, temperature, max_tokens):
        calls.append(messages)
        system = messages[0]["content"]
        # The consolidation step overrides the JSON output format.
        if "CONSOLIDATION STEP" in system:
            return "I want fewer sports stories and more local science coverage."
        turns = sum(1 for m in messages if m["role"] == "assistant")
        if turns == 0:
            return json.dumps(
                {"action": "question", "message": "Which topics would you change?"}
            )
        return json.dumps({"action": "ok", "message": "Thanks, that is clear."})

    monkeypatch.setattr(assistant_module, "_chat_local", _fake_chat)
    return calls


@pytest.fixture
def newsletters(db):
    items = []
    for slug in ("a", "b"):
        items.append(
            Newsletter.objects.create(
                slug=slug,
                title=slug.upper(),
                sections=[{"name": "S", "articles": []}],
            )
        )
    return items


@pytest.fixture
def client():
    return APIClient()


def _staff_token(client, username="r", password="x"):
    User.objects.create_user(username, password=password, is_staff=True)
    return client.post(
        "/api/auth/token/",
        {"username": username, "password": password},
        format="json",
    ).data["access"]


# --- Assistant --------------------------------------------------------------
def test_assistant_reply_parses_model_json(fake_llm):
    result = get_assistant_reply([{"role": "user", "content": "make it better"}])
    assert result.action == ACTION_QUESTION
    assert result.message == "Which topics would you change?"


def test_assistant_json_parser_rejects_malformed_replies():
    assert _parse_assistant_json('{"action": "question", "message": "ok?"}') is not None
    # Unknown action, empty message and non-JSON should all be rejected.
    assert _parse_assistant_json('{"action": "rewrite", "message": "hi"}') is None
    assert _parse_assistant_json('{"action": "question", "message": ""}') is None
    assert _parse_assistant_json("not json at all") is None


def test_assistant_raises_when_model_unreachable():
    """There is no fallback, so a failed call has to raise."""
    with pytest.raises(AssistantUnavailable):
        get_assistant_reply([{"role": "user", "content": "make it better"}])
    with pytest.raises(AssistantUnavailable):
        compose_final_feedback([{"role": "user", "content": "make it better"}])


def test_assistant_rejects_non_http_model_url(settings):
    settings.LOCAL_LLM_BASE_URL = "file:///tmp/model"
    with pytest.raises(AssistantUnavailable, match=r"must be an HTTP\(S\) URL"):
        assistant_module._chat_local([], temperature=0, max_tokens=1)


def test_assistant_replays_prior_turns_in_json_format(fake_llm):
    history = [
        {"role": "user", "content": "make it better"},
        {"role": "assistant", "content": "Which topics?", "action": "question"},
        {"role": "user", "content": "less sports"},
    ]
    result = get_assistant_reply(history)
    assert result.action == ACTION_OK
    sent = fake_llm[-1]
    assistant_turn = next(m for m in sent if m["role"] == "assistant")
    # Past turns go back in as JSON so the format stays stable.
    assert json.loads(assistant_turn["content"])["action"] == "question"


def test_newsletter_context_is_grounding_only():
    class NL:
        title = "Your POPROX Briefing"
        sections = [
            {
                "name": "Your Top Stories",
                "articles": [
                    {
                        "label": "Iran war",
                        "headline": "Deal to end the war",
                        "summary": "x " * 200,
                    }
                ],
            }
        ]

    ctx = render_newsletter_context(NL())
    assert "Your Top Stories" in ctx
    assert "Deal to end the war" in ctx
    # The guardrail keeps the model from suggesting from the newsletter.
    assert "never suggest" in ctx.lower()
    assert "…" in ctx  # long summaries are truncated

    # Nothing to render -> empty string, so the prompt is unchanged.
    assert render_newsletter_context(None) == ""

    class Empty:
        sections = []

    assert render_newsletter_context(Empty()) == ""


# --- Participant-facing copy ------------------------------------------------
def test_edition_label_is_always_today(client, newsletters):
    """The masthead date should follow the current date."""
    from django.utils import timezone

    from apps.study.content import current_edition_label

    today = timezone.localdate()
    label = current_edition_label()
    assert f"{today.year}" in label and f"{today:%B}" in label
    assert str(today.day) in label

    start = client.post(
        "/api/session/start/", {"recruitment_source": "direct"}, format="json"
    )
    assert start.data["newsletter"]["edition_label"] == label


def test_condition2_example_only_asks_for_feasible_operations():
    """The Condition 2 copy should not ask for things POPROX cannot do.

    It can select, filter, balance and reorder articles, but not rewrite text,
    change preview length or use another publisher.
    """
    from apps.study.content import CONDITION2_EXAMPLE, CONDITION2_GUIDANCE

    infeasible = [
        "shorter article",
        "longer article",
        "length of the article",
        "background on why",
        "more background",
        "kinds of sources",
        "rewrite",
        "summarize",
    ]
    for phrase in infeasible:
        assert phrase not in CONDITION2_EXAMPLE.lower(), phrase
        assert phrase not in CONDITION2_GUIDANCE.lower(), phrase


# --- Assignment + condition toggle -----------------------------------------
def test_assignment_is_balanced_across_cells(newsletters):
    from apps.study.assignment import choose_cell

    counts = {}
    for _ in range(24):  # 2 newsletters x 3 conditions = 6 cells -> 4 each
        condition, newsletter = choose_cell()
        Participant.objects.create(condition=condition, newsletter=newsletter)
        counts[(condition, newsletter.id)] = (
            counts.get((condition, newsletter.id), 0) + 1
        )
    assert set(counts.values()) == {4}, counts


def test_assignment_respects_enabled_conditions(newsletters, settings):
    """Disabling Condition 3 keeps normal assignment within {1, 2}."""
    settings.STUDY_ENABLED_CONDITIONS = [1, 2]
    from apps.study.assignment import choose_cell

    seen = set()
    for _ in range(30):
        condition, newsletter = choose_cell()
        seen.add(condition)
        Participant.objects.create(condition=condition, newsletter=newsletter)
    assert seen == {1, 2}
    assert Condition.ASSISTANT.value not in seen


def test_forced_condition_overrides_toggle(newsletters, settings):
    """The preview override can still reach a disabled condition (for demos)."""
    settings.STUDY_ENABLED_CONDITIONS = [1, 2]
    from apps.study.assignment import choose_cell

    condition, _ = choose_cell(forced_condition=3)
    assert condition == Condition.ASSISTANT.value


# --- Participant flow -------------------------------------------------------
def test_full_participant_flow(client, newsletters, fake_llm):
    # Assignment is random here so the phase stays pilot. The model is stubbed
    # because the draw can land on Condition 3.
    start = client.post(
        "/api/session/start/", {"recruitment_source": "direct"}, format="json"
    )
    assert start.status_code == 201
    pid = start.data["public_id"]

    assert client.post(f"/api/session/{pid}/consent/").status_code == 200

    initial = client.post(
        f"/api/session/{pid}/feedback/initial/",
        {"initial_text": "more local education news, less celebrity coverage"},
        format="json",
    )
    assert initial.status_code == 200

    client.post(
        f"/api/session/{pid}/feedback/final/",
        {
            "final_text": "more local education news, less celebrity coverage",
            "time_on_task_seconds": 60,
        },
        format="json",
    )

    survey = {f: 4 for f in ["effort", "express", "reflect", "understand"]}
    done = client.post(f"/api/session/{pid}/survey/", survey, format="json")
    assert done.status_code == 200
    p = Participant.objects.get(public_id=pid)
    assert p.status == Participant.Status.COMPLETED
    assert FeedbackResponse.objects.filter(participant=p).exists()
    assert SurveyResponse.objects.filter(participant=p).exists()
    assert p.study_phase == StudyPhase.PILOT


def test_condition3_chat_flow(client, newsletters, fake_llm):
    """Initial feedback, then assistant rounds, then confirm and submit."""
    start = client.post(
        "/api/session/start/",
        {"recruitment_source": "direct", "condition": 3},
        format="json",
    )
    pid = start.data["public_id"]
    client.post(f"/api/session/{pid}/consent/")

    initial = client.post(
        f"/api/session/{pid}/feedback/initial/",
        {"initial_text": "make it better"},
        format="json",
    )
    assert initial.status_code == 200
    assert initial.data["action"] in _VALID_ACTIONS
    assert initial.data["assistant_turns"] == 1

    turn = client.post(
        f"/api/session/{pid}/feedback/chat/",
        {"message": "I want fewer sports stories and more local science coverage"},
        format="json",
    )
    assert turn.status_code == 200
    assert turn.data["action"] in _VALID_ACTIONS
    assert turn.data["assistant_turns"] == 2

    p = Participant.objects.get(public_id=pid)
    assert p.study_phase == StudyPhase.PREVIEW
    fb = FeedbackResponse.objects.get(participant=p)
    assert [m["role"] for m in fb.chat_log] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    # Draft for the confirm panel, stored next to what they submit.
    draft = client.post(f"/api/session/{pid}/feedback/final-draft/")
    assert draft.status_code == 200
    assert "local science" in draft.data["draft"]
    fb.refresh_from_db()
    assert fb.final_draft == draft.data["draft"]

    final = client.post(
        f"/api/session/{pid}/feedback/final/",
        {
            "final_text": "fewer sports stories, more local science coverage",
            "time_on_task_seconds": 90,
            "revision_count": 1,
        },
        format="json",
    )
    assert final.status_code == 200
    fb.refresh_from_db()
    assert fb.final_text == "fewer sports stories, more local science coverage"


def test_condition3_reports_503_when_assistant_unavailable(client, newsletters):
    """An outage should not block the participant."""
    start = client.post(
        "/api/session/start/",
        {"recruitment_source": "direct", "condition": 3},
        format="json",
    )
    pid = start.data["public_id"]

    initial = client.post(
        f"/api/session/{pid}/feedback/initial/",
        {"initial_text": "make it better"},
        format="json",
    )
    assert initial.status_code == 503
    assert "unavailable" in initial.data["detail"].lower()

    # Their text is kept and no assistant turn is stored.
    fb = FeedbackResponse.objects.get(participant__public_id=pid)
    assert fb.initial_text == "make it better"
    assert fb.chat_log == []
    assert fb.assistant_message == ""

    # They can still submit what they wrote.
    final = client.post(
        f"/api/session/{pid}/feedback/final/",
        {"final_text": "make it better", "time_on_task_seconds": 30},
        format="json",
    )
    assert final.status_code == 200


def test_chat_endpoint_rejected_for_other_conditions(client, newsletters):
    start = client.post(
        "/api/session/start/",
        {"recruitment_source": "direct", "condition": 1},
        format="json",
    )
    pid = start.data["public_id"]
    client.post(
        f"/api/session/{pid}/feedback/initial/",
        {"initial_text": "more science"},
        format="json",
    )
    turn = client.post(
        f"/api/session/{pid}/feedback/chat/", {"message": "hello"}, format="json"
    )
    assert turn.status_code == 400


# --- Researcher permissions & rating ---------------------------------------
def test_research_endpoints_require_staff(client, newsletters):
    User.objects.create_user("plain", password="x")
    token = client.post(
        "/api/auth/token/", {"username": "plain", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/research/overview/").status_code == 403


def test_researcher_can_rate(client, newsletters):
    p = Participant.objects.create(
        condition=Condition.JUST_ASK, newsletter=newsletters[0]
    )
    fb = FeedbackResponse.objects.create(participant=p, final_text="more science")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_staff_token(client)}")
    resp = client.post(
        f"/api/research/responses/{fb.id}/ratings/",
        {
            "target_specificity": 1,
            "direction_operation": 2,
            "collection_allocation": 0,
            "context_persistence": 0,
            "system_feasibility": 2,
            "target_level": "collection",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["total"] == 5
    assert ActionabilityRating.objects.count() == 1


def test_manager_creates_distinct_blinded_human_raters(client, newsletters):
    manager = User.objects.create_user("manager", password="x", is_staff=True)
    assert manager.is_staff
    manager_token = client.post(
        "/api/auth/token/", {"username": "manager", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token}")

    created = client.post(
        "/api/auth/raters/",
        {
            "username": "rater_a",
            "email": "rater-a@example.com",
            "password": "Secure-Rater-8472!",
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.data["role"] == "rater"
    assert created.data["rating_count"] == 0

    participant = Participant.objects.create(
        condition=Condition.ASSISTANT,
        newsletter=newsletters[0],
        status=Participant.Status.COMPLETED,
        study_phase=StudyPhase.MAIN,
    )
    feedback = FeedbackResponse.objects.create(
        participant=participant,
        initial_text="make it better",
        final_text="show fewer sports stories and more local science",
        chat_log=[{"role": "assistant", "content": "Which topics?"}],
    )

    client.credentials()
    rater_token = client.post(
        "/api/auth/token/",
        {"username": "rater_a", "password": "Secure-Rater-8472!"},
        format="json",
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {rater_token}")
    me = client.get("/api/auth/me/")
    assert me.status_code == 200 and me.data["role"] == "rater"
    # Raters are confined to the blind queue.
    assert client.get("/api/research/overview/").status_code == 403
    assert client.get(f"/api/research/responses/{feedback.id}/").status_code == 403
    assert client.get("/api/research/export.csv").status_code == 403

    queue = client.get("/api/research/responses/?unrated=1")
    assert queue.status_code == 200
    row = queue.data["results"][0]
    # The queue only exposes the id and the final text.
    assert set(row) == {"id", "final_text"}
    assert row["id"] == feedback.id

    payload = {
        "target_specificity": 2,
        "direction_operation": 2,
        "collection_allocation": 1,
        "context_persistence": 0,
        "system_feasibility": 2,
        "target_level": "collection",
    }
    first = client.post(
        f"/api/research/responses/{feedback.id}/ratings/", payload, format="json"
    )
    assert first.status_code == 201
    duplicate = client.post(
        f"/api/research/responses/{feedback.id}/ratings/", payload, format="json"
    )
    assert duplicate.status_code == 409

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token}")
    raters = client.get("/api/auth/raters/")
    assert raters.status_code == 200
    assert raters.data[0]["username"] == "rater_a"
    assert raters.data[0]["rating_count"] == 1


# --- Export -----------------------------------------------------------------
def test_export_includes_final_draft_and_chat_log(client, newsletters):
    p = Participant.objects.create(
        condition=Condition.ASSISTANT, newsletter=newsletters[0]
    )
    FeedbackResponse.objects.create(
        participant=p,
        final_text="more local science",
        final_draft="I want more local science.",
        chat_log=[{"role": "user", "content": "science please"}],
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_staff_token(client, 'rx')}")
    resp = client.get("/api/research/export.csv")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "final_draft" in body and "chat_log_json" in body
    assert "I want more local science." in body
    # LLM ratings are gone, so none should show up as human ratings.
    assert "llm" not in body.lower()
