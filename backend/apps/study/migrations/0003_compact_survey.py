from django.db import migrations, models


class Migration(migrations.Migration):
    """Replace the 12-item survey with the compact 6-item survey (three
    constructs: Perceived Feedback Ease, Expressive Confidence, Perceived
    Feedback Actionability)."""

    dependencies = [
        ("study", "0002_alter_feedbackresponse_assistant_action_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="surveyresponse", name="news_reading_frequency"),
        migrations.RemoveField(model_name="surveyresponse", name="personalized_news_exposure"),
        migrations.RemoveField(model_name="surveyresponse", name="baseline_clarity_topics"),
        migrations.RemoveField(model_name="surveyresponse", name="baseline_clarity_describe"),
        migrations.RemoveField(model_name="surveyresponse", name="communicability_knows"),
        migrations.RemoveField(model_name="surveyresponse", name="communicability_better"),
        migrations.RemoveField(model_name="surveyresponse", name="persistence_general"),
        migrations.RemoveField(model_name="surveyresponse", name="persistence_beyond"),
        migrations.AddField(
            model_name="surveyresponse",
            name="actionability_understand",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="surveyresponse",
            name="actionability_usable",
            field=models.PositiveSmallIntegerField(default=3),
            preserve_default=False,
        ),
    ]
