"""Remove used_llm and provider keys from stored chat logs.

Both keys came from the old fallback path. Every stored turn has used_llm=true,
so nothing is lost. role, content, action and ts are left alone.
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
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("study", "0009_simplify_study_schema"),
    ]

    operations = [
        migrations.RunPython(strip_provenance_keys, noop_reverse),
    ]
