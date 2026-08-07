from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("study", "0007_analysis_dashboard_and_llm_runs")]

    operations = [
        migrations.AddConstraint(
            model_name="actionabilityrating",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_llm=False),
                fields=("feedback", "rater", "text_version"),
                name="unique_human_rating_per_response_version",
            ),
        )
    ]
