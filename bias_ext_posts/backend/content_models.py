from __future__ import annotations


def get_post_model():
    from bias_core.extensions.runtime import get_runtime_service
    from bias_ext_posts.backend.models import Post

    service = get_runtime_service("content.posts", None)
    if isinstance(service, dict):
        return service.get("model") or Post
    if service is not None:
        return getattr(service, "model", None) or Post
    return Post
