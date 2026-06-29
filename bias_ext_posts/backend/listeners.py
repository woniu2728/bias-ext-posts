from __future__ import annotations

from bias_ext_posts.backend.events import PostHiddenEvent


def create_runtime_timeline_from_builder(*args, **kwargs):
    from bias_core.extensions.runtime import create_runtime_timeline_from_builder as runtime_create_timeline_from_builder

    return runtime_create_timeline_from_builder(*args, **kwargs)


def handle_post_hidden_timeline(event: PostHiddenEvent) -> None:
    create_runtime_timeline_from_builder(
        event,
        "post_hidden",
        extra={"post_type": "postHidden"},
        update_discussion_last_post=False,
    )
