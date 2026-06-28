from __future__ import annotations

from bias_core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    EventListenersExtender,
    ForumCapabilitiesExtender,
    LifecycleExtender,
    ModelExtender,
    ModelVisibilityExtender,
    RealtimeExtender,
    SearchIndexExtender,
    ServiceProviderExtender,
    SettingsExtender,
)

from bias_ext_posts.backend.admin_surface import permission_definitions
from bias_ext_posts.backend.events import PostCreatedEvent, PostHiddenEvent
from bias_ext_posts.backend.forum_contracts import post_type_definitions
from bias_ext_posts.backend.frontend import frontend_extender
from bias_ext_posts.backend.handlers import post_resource_endpoints
from bias_ext_posts.backend.listener_contracts import event_listener_definitions
from bias_ext_posts.backend.model_contracts import owned_models
from bias_ext_posts.backend.models import Post
from bias_ext_posts.backend.resources import (
    admin_stats_resource_field_definitions,
    post_resource_definitions,
    post_resource_field_definitions,
)
from bias_ext_posts.backend.runtime import (
    discussion_posts_service_provider,
    post_service_provider,
    realtime_post_payload_service_provider,
)
from bias_ext_posts.backend.search_contracts import search_index_definitions
from bias_ext_posts.backend.search_targets import post_search_target_provider
from bias_ext_posts.backend.settings import setting_field_definitions
from bias_ext_posts.backend.visibility import scope_post_view


def frontend_extenders():
    return (frontend_extender(),)


def forum_extenders():
    return (
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
        ),
    )


def event_extenders():
    return (
        EventListenersExtender(
            listeners=event_listener_definitions(),
        ),
        RealtimeExtender()
        .broadcast_discussion_event(
            PostCreatedEvent,
            "post.created",
            include_discussion=True,
            include_post=True,
            post_id="post_id",
            condition=lambda event: event.is_approved,
            description="审核通过的回复创建后广播实时讨论和帖子资源。",
        )
        .broadcast_discussion_event(
            PostHiddenEvent,
            "post.hidden",
            description="回复隐藏状态变化后广播实时事件。",
        ),
    )


def admin_extenders():
    return (
        AdminSurfaceExtender(
            permissions=permission_definitions(),
        ),
        SettingsExtender(
            fields=setting_field_definitions(),
            expose_to_forum=("allow_hide_own_posts",),
        ),
    )


def resource_extenders():
    return (
        ApiResourceExtender("post")
        .endpoints_with(*post_resource_endpoints())
        .fields(post_resource_field_definitions),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        *(ApiResourceExtender(definition) for definition in post_resource_definitions()),
    )


def model_extenders():
    extender = ModelExtender()
    for model, description in owned_models():
        extender = extender.owns(model, description=description)
    return (
        extender,
        ModelVisibilityExtender().scope(
            Post,
            scope_post_view,
            description="限制当前用户只能查看有权限访问的讨论帖子。",
        ),
    )


def search_extenders():
    extender = SearchIndexExtender()
    for definition in search_index_definitions():
        extender = extender.postgres_index(
            definition["name"],
            drop=definition["drop"],
            create=definition["create"],
            description=definition["description"],
        )
    return (extender,)


def service_extenders():
    return (
        ServiceProviderExtender(
            key="posts.service",
            provider=post_service_provider,
        ),
        ServiceProviderExtender(
            key="discussion.posts",
            provider=discussion_posts_service_provider,
        ),
        ServiceProviderExtender(
            key="realtime.post_payload",
            provider=realtime_post_payload_service_provider,
        ),
        ServiceProviderExtender(
            key="search.target.post",
            provider=post_search_target_provider,
        ),
        LifecycleExtender(),
    )
