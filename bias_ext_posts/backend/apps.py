from django.apps import AppConfig


class PostsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bias_ext_posts.backend"
    label = "posts"
    verbose_name = "Bias Posts"

