from __future__ import annotations

from bias_core.extensions.runtime import create_runtime_timeline_from_builder
from bias_ext_posts.backend.events import PostHiddenEvent


def handle_post_hidden_timeline(event: PostHiddenEvent) -> None:
    create_runtime_timeline_from_builder(
        event,
        "post_hidden",
        extra={"post_type": "postHidden"},
        update_discussion_last_post=False,
    )
