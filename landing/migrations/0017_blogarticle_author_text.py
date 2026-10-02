from django.conf import settings
from django.db import migrations, models


def preserve_author_names(apps, schema_editor):
    Article = apps.get_model("landing", "BlogArticle")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    username_field = getattr(User, "USERNAME_FIELD", "username")
    database = schema_editor.connection.alias
    for article in Article.objects.using(database).select_related("author").iterator():
        if article.author is None:
            continue
        author = article.author
        full_name = " ".join(
            name.strip()
            for name in (
                getattr(author, "first_name", "") or "",
                getattr(author, "last_name", "") or "",
            )
            if name.strip()
        )
        name = full_name or getattr(author, username_field, "") or "Contributor"
        Article.objects.using(database).filter(pk=article.pk).update(author_text=name)


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0016_blogarticle_author"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogarticle",
            name="author_text",
            field=models.CharField(max_length=320, blank=True, default=""),
        ),
        migrations.RunPython(preserve_author_names),
        migrations.RemoveField(model_name="blogarticle", name="author"),
        migrations.RenameField(
            model_name="blogarticle", old_name="author_text", new_name="author"
        ),
    ]
