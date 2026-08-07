"""Simplify the schema down to what the study actually uses.

Drops the LLM auto-rating subsystem, the statistical-analysis exclusion audit,
and several fields that were written but never read.

IMPORTANT: machine-generated ratings are deleted *before* the ``is_llm`` column
is dropped. Without this, every ``is_llm=True`` row would silently become
indistinguishable from a human rating and would be counted as one in the CSV
export and the researcher dashboard.
"""

from django.conf import settings
from django.db import migrations, models


def delete_llm_ratings(apps, schema_editor):
    """Remove machine-generated ratings while ``is_llm`` still distinguishes them."""
    ActionabilityRating = apps.get_model('study', 'ActionabilityRating')
    ActionabilityRating.objects.filter(is_llm=True).delete()


def noop_reverse(apps, schema_editor):
    """Deleted measurements cannot be reconstructed; reversing is a no-op."""


class Migration(migrations.Migration):

    dependencies = [
        ('study', '0008_unique_human_rating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(delete_llm_ratings, noop_reverse),
        migrations.RemoveField(
            model_name='analysisexclusionevent',
            name='decided_by',
        ),
        migrations.RemoveField(
            model_name='analysisexclusionevent',
            name='participant',
        ),
        migrations.RemoveField(
            model_name='llmratingrun',
            name='requested_by',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='llm_run',
        ),
        migrations.RemoveConstraint(
            model_name='actionabilityrating',
            name='unique_human_rating_per_response_version',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='is_llm',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='llm_latency_ms',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='llm_model',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='llm_raw_output',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='prompt_version',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='rubric_version',
        ),
        migrations.RemoveField(
            model_name='actionabilityrating',
            name='text_version',
        ),
        migrations.RemoveField(
            model_name='feedbackresponse',
            name='assistant_used_llm',
        ),
        migrations.RemoveField(
            model_name='newsletter',
            name='intro',
        ),
        migrations.RemoveField(
            model_name='newsletter',
            name='theme',
        ),
        migrations.RemoveField(
            model_name='participant',
            name='analysis_excluded',
        ),
        migrations.RemoveField(
            model_name='participant',
            name='analysis_excluded_at',
        ),
        migrations.RemoveField(
            model_name='participant',
            name='analysis_excluded_by',
        ),
        migrations.RemoveField(
            model_name='participant',
            name='analysis_exclusion_reason',
        ),
        migrations.RemoveField(
            model_name='participant',
            name='user_agent',
        ),
        migrations.AlterField(
            model_name='participant',
            name='status',
            field=models.CharField(choices=[('created', 'Created'), ('consented', 'Consented'), ('feedback', 'Submitted feedback'), ('completed', 'Completed')], default='created', max_length=20),
        ),
        migrations.AddConstraint(
            model_name='actionabilityrating',
            constraint=models.UniqueConstraint(fields=('feedback', 'rater'), name='unique_rating_per_rater_per_response'),
        ),
        migrations.DeleteModel(
            name='AnalysisExclusionEvent',
        ),
        migrations.DeleteModel(
            name='LLMRatingRun',
        ),
    ]
