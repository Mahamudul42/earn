"""Focused tests for the EARN study: assignment balance + condition toggle, the
clarify/advise assistant, the participant flow, and researcher permissions/rating."""
import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.study.assistant import (
    ACTION_SUGGESTION,
    RATING_DIMENSIONS,
    _VALID_ACTIONS,
    _parse_rating_json,
    active_provider,
    get_assistant_response,
    llm_rate_feedback,
    provider_status,
    render_newsletter_context,
    run_model,
)
from apps.study.models import (
    ActionabilityRating,
    Condition,
    FeedbackResponse,
    Newsletter,
    Participant,
    SurveyResponse,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def _no_live_llm(settings):
    """Keep ordinary tests offline so they use the deterministic fallback."""
    settings.LOCAL_LLM_BASE_URL = ""
    settings.LOCAL_LLM_API_KEY = ""


@pytest.fixture
def newsletters(db):
    items = []
    for slug in ("a", "b"):
        items.append(
            Newsletter.objects.create(
                slug=slug,
                title=slug.upper(),
                edition_label="Test",
                sections=[{"name": "S", "articles": []}],
            )
        )
    return items


@pytest.fixture
def client():
    return APIClient()


# --- Assistant (concrete suggestions — never rewrites) ---------------------
def test_assistant_suggests_when_vague():
    result = get_assistant_response("make it better")
    assert result.action == ACTION_SUGGESTION
    assert result.used_llm is False


def test_assistant_only_suggests_or_acknowledges():
    """The assistant must only suggest/ask/acknowledge — never 'rewrite'."""
    for text in [
        "make it better",
        "I do not like sports. more science news please",
        "I want fewer long political articles and more short local updates",
        "the newsletter is boring",
    ]:
        result = get_assistant_response(text)
        assert result.action in _VALID_ACTIONS
        assert result.action != "rewrite"
        # No local endpoint configured in tests -> deterministic fallback.
        assert result.used_llm is False


# --- Local-only LLM transport ----------------------------------------------
def test_local_llm_is_the_only_active_provider(settings, monkeypatch):
    """Even legacy external settings cannot redirect the active runtime."""
    settings.LLM_PROVIDER = "external"
    settings.EXTERNAL_API_KEY = "must-not-be-used"
    settings.LOCAL_LLM_BASE_URL = "http://model-host:8123/v1"
    settings.LOCAL_LLM_MODEL = "openai/gpt-oss-120b"
    settings.LOCAL_LLM_API_KEY = ""
    settings.LOCAL_LLM_TIMEOUT_SECONDS = 12
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": "local response"}}
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert active_provider() == "local"
    assert provider_status()["configured"] == {"local": True}
    assert run_model("System", "User", max_tokens=150) == "local response"
    assert captured == {
        "url": "http://model-host:8123/v1/chat/completions",
        "authorization": None,
        "payload": {
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "User"},
            ],
            "temperature": 0.4,
            "max_tokens": 150,
        },
        "timeout": 12,
    }


# --- Newsletter grounding context ------------------------------------------
def test_newsletter_context_is_grounding_only():
    class NL:
        title = "Your POPROX Briefing"
        edition_label = "Saturday Edition"
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
    # The anti-leading guardrail must be present so the model treats the
    # newsletter as reference only, never as suggestion material.
    assert "never suggest" in ctx.lower()
    assert "…" in ctx  # long summaries are truncated

    # Nothing to render -> empty string, so the prompt is unchanged.
    assert render_newsletter_context(None) == ""

    class Empty:
        sections = []

    assert render_newsletter_context(Empty()) == ""


# --- LLM actionability rater -----------------------------------------------
def test_rating_json_parser_clamps_and_validates():
    ok = _parse_rating_json(
        'noise {"target_specificity": 2, "direction_operation": 5, '
        '"collection_allocation": 1, "context_persistence": 0, '
        '"system_feasibility": 1, "target_level": "Section", "notes": "ok"} tail'
    )
    assert ok["direction_operation"] == 2  # out-of-range value clamped to 0..2
    assert ok["target_level"] == "section"  # normalised/lowercased
    assert set(RATING_DIMENSIONS) <= ok.keys()
    # A missing dimension or non-JSON reply is treated as unparseable.
    assert _parse_rating_json('{"target_specificity": 1}') is None
    assert _parse_rating_json("not json at all") is None


def test_llm_rater_offline_returns_none():
    # The autouse fixture disables the local endpoint -> no rating is produced.
    assert llm_rate_feedback("more local science, fewer sports") is None


def test_rate_with_llm_command_skips_gracefully_offline(newsletters):
    from django.core.management import call_command

    p = Participant.objects.create(
        condition=Condition.JUST_ASK, newsletter=newsletters[0]
    )
    FeedbackResponse.objects.create(participant=p, final_text="more science")
    call_command("rate_with_llm")  # offline: no provider -> creates nothing
    assert ActionabilityRating.objects.filter(is_llm=True).count() == 0


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
    User.objects.create_user("rx", password="x", is_staff=True)
    token = client.post(
        "/api/auth/token/", {"username": "rx", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.get("/api/research/export.csv")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "final_draft" in body and "chat_log_json" in body
    assert "I want more local science." in body


# --- Assignment + condition toggle -----------------------------------------
def test_assignment_is_balanced_across_cells(newsletters):
    from apps.study.assignment import choose_cell

    counts = {}
    for _ in range(24):  # 2 newsletters x 3 conditions = 6 cells -> 4 each
        condition, newsletter = choose_cell()
        Participant.objects.create(condition=condition, newsletter=newsletter)
        counts[(condition, newsletter.id)] = counts.get((condition, newsletter.id), 0) + 1
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
def test_full_participant_flow(client, newsletters):
    start = client.post("/api/session/start/", {"recruitment_source": "direct"}, format="json")
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
        {"final_text": "more local education news, less celebrity coverage", "time_on_task_seconds": 60},
        format="json",
    )

    survey = {f: 4 for f in ["effort", "express", "reflect", "understand"]}
    done = client.post(f"/api/session/{pid}/survey/", survey, format="json")
    assert done.status_code == 200
    p = Participant.objects.get(public_id=pid)
    assert p.status == Participant.Status.COMPLETED
    assert FeedbackResponse.objects.filter(participant=p).exists()
    assert SurveyResponse.objects.filter(participant=p).exists()


def test_condition3_chat_flow(client, newsletters):
    """Condition 3 runs a multi-turn conversation: initial feedback -> assistant
    round(s) -> confirm-and-submit. The full conversation is stored in chat_log."""
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
    fb = FeedbackResponse.objects.get(participant=p)
    assert len(fb.chat_log) == 4  # user, assistant, user, assistant
    assert [m["role"] for m in fb.chat_log] == ["user", "assistant", "user", "assistant"]

    # Consolidated draft for the confirm panel (offline -> joins the reader's
    # own messages verbatim) and is stored for the faithfulness analysis.
    draft = client.post(f"/api/session/{pid}/feedback/final-draft/")
    assert draft.status_code == 200
    assert "make it better" in draft.data["draft"]
    assert "fewer sports stories" in draft.data["draft"]
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
    # Create a completed feedback.
    nl = newsletters[0]
    p = Participant.objects.create(condition=Condition.JUST_ASK, newsletter=nl)
    fb = FeedbackResponse.objects.create(participant=p, final_text="more science")

    User.objects.create_user("r", password="x", is_staff=True)
    token = client.post(
        "/api/auth/token/", {"username": "r", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.post(
        f"/api/research/responses/{fb.id}/ratings/",
        {
            "target_specificity": 1, "direction_operation": 2,
            "collection_allocation": 0, "context_persistence": 0,
            "system_feasibility": 2, "target_level": "collection",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["total"] == 5


def test_prompt_lab_default_and_samples(client, newsletters):
    User.objects.create_user("r2", password="x", is_staff=True)
    token = client.post(
        "/api/auth/token/", {"username": "r2", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    default = client.get("/api/research/prompt-lab/default/")
    assert default.status_code == 200
    assert len(default.data["system_prompt"]) > 50

    samples = client.get("/api/research/prompt-lab/samples/?source=collected&limit=5")
    assert samples.status_code == 200
    assert isinstance(samples.data["samples"], list)


def test_prompt_lab_requires_staff(client, newsletters):
    User.objects.create_user("plain2", password="x")
    token = client.post(
        "/api/auth/token/", {"username": "plain2", "password": "x"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/research/prompt-lab/default/").status_code == 403
