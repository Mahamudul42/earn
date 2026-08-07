from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("study", "0004_survey_4item_and_actions"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackresponse",
            name="chat_log",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
