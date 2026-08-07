from django.db import migrations, models


class Migration(migrations.Migration):
    """Advisor-meeting update: reduce the survey to four scale-estimation items
    (effort, express, reflect, understand) and broaden the assistant actions to
    include 'suggestion'."""

    dependencies = [
        ("study", "0003_compact_survey"),
    ]

    operations = [
        # --- Survey: 6 items -> 4 scale-estimation items ---
        migrations.RemoveField(model_name="surveyresponse", name="ease_easy"),
        migrations.RemoveField(model_name="surveyresponse", name="ease_low_effort"),
        migrations.RemoveField(model_name="surveyresponse", name="confidence_express"),
        migrations.RemoveField(model_name="surveyresponse", name="confidence_reflects"),
        migrations.RemoveField(model_name="surveyresponse", name="actionability_understand"),
        migrations.RemoveField(model_name="surveyresponse", name="actionability_usable"),
        migrations.AddField(
            model_name="surveyresponse",
            name="effort",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="surveyresponse",
            name="express",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="surveyresponse",
            name="reflect",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="surveyresponse",
            name="understand",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
        # --- Assistant action choices (no DB schema change; keeps state in sync) ---
        migrations.AlterField(
            model_name="feedbackresponse",
            name="assistant_action",
            field=models.CharField(
                choices=[
                    ("none", "No assistant round"),
                    ("suggestion", "Concrete suggestion"),
                    ("question", "Clarifying question"),
                    ("ok", "Already actionable"),
                ],
                default="none",
                max_length=12,
            ),
        ),
    ]
