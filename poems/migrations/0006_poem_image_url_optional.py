from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("poems", "0005_poem_user_profile"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="poem",
                    name="image_url",
                    field=models.URLField(
                        default="",
                        blank=True,
                        help_text="Optionele illustratie bij het gedicht",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="poem",
            name="image_url",
            field=models.URLField(
                blank=True,
                null=True,
                help_text="Optionele illustratie bij het gedicht",
            ),
        ),
    ]
