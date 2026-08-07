"""Strip dead provenance keys from already-collected Condition-3 transcripts.

Turns recorded before the deterministic fallback was removed carry ``used_llm``
and ``provider`` keys. Only one code path produces a turn now, so these keys are
constant and no longer meaningful — and leaving them in the CSV export invites
questions that no code answers.

This was verified safe before writing: every stored turn had ``used_llm=true``,
i.e. no turn was ever produced by the removed fallback, so no measurement is
lost. Only these two keys are removed; ``role``, ``content``, ``action`` and
``ts`` (the actual transcript) are untouched.
"""

from django.db import migrations

DEAD_KEYS = ("used_llm", "provider")


def strip_provenance_keys(apps, schema_editor):
    FeedbackResponse = apps.get_model("study", "FeedbackResponse")
    for feedback in FeedbackResponse.objects.exclude(chat_log=[]).iterator():
        log = feedback.chat_log or []
        if not isinstance(log, list):
            continue
        cleaned = [
            {k: v for k, v in turn.items() if k not in DEAD_KEYS}
            if isinstance(turn, dict)
            else turn
            for turn in log
        ]
        if cleaned != log:
            feedback.chat_log = cleaned
            feedback.save(update_fields=["chat_log"])


def noop_reverse(apps, schema_editor):
    """The removed keys were constant, so there is nothing to restore."""


class Migration(migrations.Migration):

    dependencies = [
        ("study", "0009_simplify_study_schema"),
    ]

    operations = [
        migrations.RunPython(strip_provenance_keys, noop_reverse),
    ]
