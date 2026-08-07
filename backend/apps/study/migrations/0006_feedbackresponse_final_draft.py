from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("study", "0005_feedbackresponse_chat_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackresponse",
            name="final_draft",
            field=models.TextField(blank=True),
        ),
    ]
