from __future__ import annotations

from bias_ext_posts.backend.models import Post


def owned_models():
    return (
        (
            Post,
            "帖子流与回复记录由 posts 扩展拥有。",
        ),
    )
