import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("study", "0006_feedbackresponse_final_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="analysis_excluded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="participant",
            name="analysis_excluded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="participant",
            name="analysis_exclusion_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="participant",
            name="analysis_excluded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analysis_exclusions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="participant",
            name="study_phase",
            field=models.CharField(
                choices=[
                    ("preview", "Preview / demo"),
                    ("pilot", "Pilot"),
                    ("main", "Main experiment"),
                ],
                default="pilot",
                max_length=12,
            ),
        ),
        migrations.CreateModel(
            name="LLMRatingRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=12,
                    ),
                ),
                ("model", models.CharField(max_length=160)),
                ("prompt_version", models.CharField(max_length=80)),
                ("rubric_version", models.CharField(max_length=40)),
                (
                    "study_phase",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("preview", "Preview / demo"),
                            ("pilot", "Pilot"),
                            ("main", "Main experiment"),
                        ],
                        max_length=12,
                    ),
                ),
                ("condition", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("refresh", models.BooleanField(default=False)),
                ("total", models.PositiveIntegerField(default=0)),
                ("rated", models.PositiveIntegerField(default=0)),
                ("skipped", models.PositiveIntegerField(default=0)),
                ("failed", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="llm_rating_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AnalysisExclusionEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("excluded", models.BooleanField()),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="analysis_exclusion_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analysis_exclusion_events",
                        to="study.participant",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="text_version",
            field=models.CharField(
                choices=[("initial", "Initial feedback"), ("final", "Final feedback")],
                default="final",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="llm_latency_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="llm_model",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="llm_raw_output",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="llm_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ratings",
                to="study.llmratingrun",
            ),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="prompt_version",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="actionabilityrating",
            name="rubric_version",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
