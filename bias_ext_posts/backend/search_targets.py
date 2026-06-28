from __future__ import annotations


def post_search_target_provider() -> dict:
    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.visibility import apply_post_visibility_scope

    return {
        "model": Post,
        "apply_visibility": apply_post_visibility_scope,
    }
