from __future__ import annotations

from bias_core.extensions import ExtensionEventListenerDefinition

from bias_ext_posts.backend.events import PostHiddenEvent
from bias_ext_posts.backend.listeners import handle_post_hidden_timeline


def event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=PostHiddenEvent,
            handler=handle_post_hidden_timeline,
            description="回复隐藏状态变化后写入讨论时间线事件帖。",
        ),
    )
