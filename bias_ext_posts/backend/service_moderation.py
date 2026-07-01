from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from bias_core.extensions.platform import dispatch_forum_event_after_commit
from bias_ext_posts.backend.events import (
    PostApprovedEvent,
    PostRejectedEvent,
)
from bias_ext_posts.backend.models import Post


def get_runtime_post_lifecycle_service(*args, **kwargs):
    from bias_core.extensions.runtime import get_runtime_post_lifecycle_service as runtime_get_post_lifecycle_service

    return runtime_get_post_lifecycle_service(*args, **kwargs)


def get_runtime_service(service_key: str, default=None):
    from bias_core.extensions.runtime import get_runtime_service as runtime_get_service

    return runtime_get_service(service_key, default)


def _service_method(service, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"Posts 扩展运行时服务缺少方法: {name}")
    return method


def increment_user_comment_count(*args, **kwargs):
    return _service_method(get_runtime_service("users.service"), "increment_comment_count")(*args, **kwargs)


def mark_discussion_read(*args, **kwargs):
    return _service_method(get_runtime_service("content.discussions"), "mark_read")(*args, **kwargs)


def refresh_runtime_model_private(*args, **kwargs):
    from bias_core.extensions.runtime import refresh_runtime_model_private as runtime_refresh_model_private

    return runtime_refresh_model_private(*args, **kwargs)


def approve_post(
    post: Post,
    admin_user,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        now = timezone.now()
        post.approval_status = Post.APPROVAL_APPROVED
        post.approved_at = now
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = None
        post.hidden_user = None
        refresh_runtime_model_private(post)
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user", "is_private"
        ])

        discussion = post.discussion
        if not was_counted:
            refresh_discussion_approved_stats_cb(discussion)
            discussion.refresh_from_db(fields=[
                "comment_count",
                "participant_count",
                "last_posted_at",
                "last_posted_user",
                "last_post_id",
                "last_post_number",
            ])

            if post.user and post.type in user_counted_post_types:
                increment_user_comment_count(post.user_id, 1)
                mark_discussion_read(
                    discussion_id=discussion.id,
                    user=post.user,
                    last_read_post_number=post.number,
                    require_view=False,
                )

            _apply_post_approved_extensions(
                post,
                context={
                    "content": post.content,
                    "actor": admin_user,
                    "previous_status": previous_status,
                    "was_counted": was_counted,
                    "is_counted": True,
                },
            )

            dispatch_forum_event_after_commit(
                PostApprovedEvent(
                    post_id=post.id,
                    discussion_id=discussion.id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                    post_number=post.number,
                    discussion_title=discussion.title if discussion else "",
                )
            )
    post.refresh_from_db()
    return post


def _apply_post_approved_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_approved(post=post, context=context)


def reject_post(
    post: Post,
    admin_user,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    rejected_at = timezone.now()
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        post.approval_status = Post.APPROVAL_REJECTED
        post.approved_at = rejected_at
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = rejected_at
        post.hidden_user = admin_user
        refresh_runtime_model_private(post)
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user", "is_private"
        ])

        if was_counted:
            refresh_discussion_approved_stats_cb(post.discussion)
            post.discussion.refresh_from_db(fields=[
                "comment_count",
                "participant_count",
                "last_posted_at",
                "last_posted_user",
                "last_post_id",
                "last_post_number",
            ])
            if post.user and post.type in user_counted_post_types:
                increment_user_comment_count(post.user_id, -1)

        _apply_post_rejected_extensions(
            post,
            context={
                "actor": admin_user,
                "previous_status": previous_status,
                "is_hidden": True,
                "was_counted": was_counted,
                "is_counted": False,
            },
        )

        if previous_status != Post.APPROVAL_REJECTED:
            dispatch_forum_event_after_commit(
                PostRejectedEvent(
                    post_id=post.id,
                    discussion_id=post.discussion_id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                    post_number=post.number,
                    discussion_title=post.discussion.title if getattr(post, "discussion", None) else "",
                )
            )
    return post


def _apply_post_rejected_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_hidden(post=post, context=context)

