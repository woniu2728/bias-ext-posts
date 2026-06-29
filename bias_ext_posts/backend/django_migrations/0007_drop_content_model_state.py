from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0006_remove_post_posts_discuss_49d427_idx_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Post"),
            ],
        ),
    ]
