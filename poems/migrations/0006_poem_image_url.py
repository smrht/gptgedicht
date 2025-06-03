from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("poems", "0005_poem_user_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="poem",
            name="image_url",
            field=models.URLField(blank=True, help_text="URL van de gegenereerde afbeelding"),
        ),
    ]
