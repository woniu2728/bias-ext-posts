from __future__ import annotations

from typing import Any


def _runtime_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"Posts 扩展运行时服务缺少方法: {name}")
    return method


def _content_posts_method(name: str):
    from bias_core.extensions.runtime import get_runtime_content_posts_service

    content_posts = get_runtime_content_posts_service(None)
    if content_posts is None:
        return None
    method = content_posts.get(name) if isinstance(content_posts, dict) else getattr(content_posts, name, None)
    return method if callable(method) else None


def post_service_provider() -> dict:
    from bias_ext_posts.backend import post_query_service
    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.services import PostService

    return {
        "model": Post,
        "approval_approved": Post.APPROVAL_APPROVED,
        "approval_pending": Post.APPROVAL_PENDING,
        "approval_rejected": Post.APPROVAL_REJECTED,
        "can_view": post_query_service.can_view_post,
        "apply_visibility": post_query_service.apply_visibility_filters,
        "build_visible_queryset": post_query_service.build_visible_post_queryset,
        "get_visible_ids": _get_visible_post_ids,
        "get_action_context": _get_post_action_context,
        "get_window": post_query_service.get_post_window,
        "get_page_for_near_post": post_query_service.get_page_for_near_post,
        "get_by_id": PostService.get_post_by_id,
        "create": PostService.create_post,
        "update": PostService.update_post,
        "delete": PostService.delete_post,
        "set_hidden_state": PostService.set_hidden_state,
        "approve": PostService.approve_post,
        "reject": PostService.reject_post,
        "list_approval_queue": _list_approval_queue,
        "count_pending_approvals": _count_pending_approvals,
        "process_approval": _process_approval,
        "event_types": post_event_type_aliases(),
        "can_edit": PostService.can_edit_post,
        "can_delete": PostService.can_delete_post,
        "create_event_post": _create_event_post,
        "resolve_content_html": PostService.resolve_content_html,
        "serialize": _serialize_post,
        "serialize_by_id": _serialize_post_by_id,
        "reply_notification_context": _reply_notification_context,
        "notification_context": _notification_context,
        "get_number": _get_post_number,
    }


def post_event_type_aliases() -> dict[str, type]:
    from bias_ext_posts.backend.events import (
        PostApprovedEvent,
        PostCreatedEvent,
        PostDeletedEvent,
        PostHiddenEvent,
        PostRejectedEvent,
        PostResubmittedEvent,
    )

    return {
        "posts.post.created": PostCreatedEvent,
        "posts.post.approved": PostApprovedEvent,
        "posts.post.rejected": PostRejectedEvent,
        "posts.post.resubmitted": PostResubmittedEvent,
        "posts.post.hidden": PostHiddenEvent,
        "posts.post.deleted": PostDeletedEvent,
    }


post_service_provider.event_types = post_event_type_aliases


def _list_approval_queue() -> list[dict]:
    from bias_core.extensions.runtime import list_runtime_pending_discussion_first_post_ids
    from bias_ext_posts.backend.models import Post

    discussion_first_post_ids = list_runtime_pending_discussion_first_post_ids()
    posts = Post.objects.filter(
        approval_status=Post.APPROVAL_PENDING,
    ).exclude(
        id__in=discussion_first_post_ids,
    ).select_related("user", "discussion").order_by("-created_at")
    return [_serialize_approval_item(post) for post in posts]


def _count_pending_approvals() -> int:
    from bias_core.extensions.runtime import list_runtime_pending_discussion_first_post_ids
    from bias_ext_posts.backend.models import Post

    discussion_first_post_ids = list_runtime_pending_discussion_first_post_ids()
    return Post.objects.filter(approval_status=Post.APPROVAL_PENDING).exclude(
        id__in=discussion_first_post_ids,
    ).count()


def _process_approval(*, content_id: int, action: str, actor, note: str = "") -> dict:
    from django.core.exceptions import ValidationError
    from django.shortcuts import get_object_or_404
    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.services import PostService

    post = get_object_or_404(
        Post.objects.select_related("discussion", "user"),
        id=content_id,
        approval_status=Post.APPROVAL_PENDING,
    )
    if action == "approve":
        processed = PostService.approve_post(post, actor, note=note)
    elif action == "reject":
        processed = PostService.reject_post(post, actor, note=note)
    else:
        raise ValidationError("无效的审核动作")
    return _serialize_approval_item(processed)


def _serialize_approval_item(post) -> dict:
    return {
        "type": "post",
        "id": post.id,
        "title": post.discussion.title if post.discussion else "回复审核",
        "content": post.content,
        "created_at": post.created_at,
        "approval_status": post.approval_status,
        "approval_note": post.approval_note,
        "author": _serialize_user(getattr(post, "user", None)),
        "discussion": {
            "id": post.discussion.id,
            "title": post.discussion.title,
        } if post.discussion else None,
        "post": {
            "id": post.id,
            "number": post.number,
        },
    }


def _serialize_user(user) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
    }


def _get_visible_post_ids(user=None, *, context: dict | None = None):
    content_method = _content_posts_method("get_visible_ids")
    if content_method is not None:
        return content_method(user=user, context=context or {})

    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.post_query_service import apply_visibility_filters

    queryset = Post.objects.all()
    resolved_context = dict(context or {})
    if resolved_context:
        from bias_core.extensions.platform import apply_model_visibility_scope

        return apply_model_visibility_scope(
            Post,
            queryset,
            user=user,
            ability=str(resolved_context.pop("ability", "view") or "view"),
            context=resolved_context,
        ).values("id")
    return apply_visibility_filters(queryset, user).values("id")


def _get_post_action_context(post_id: int, user=None, *, require_visible: bool = True) -> dict | None:
    content_method = _content_posts_method("get_action_context")
    if content_method is not None:
        return content_method(post_id, user=user, require_visible=require_visible)

    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.post_query_service import apply_visibility_filters

    queryset = Post.objects.select_related("discussion").filter(id=post_id)
    if require_visible:
        queryset = apply_visibility_filters(queryset, user)
    row = (
        queryset
        .values(
            "id",
            "discussion_id",
            "user_id",
            "number",
            "hidden_at",
            "discussion__title",
        )
        .first()
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "discussion_id": row["discussion_id"],
        "user_id": row["user_id"],
        "number": row["number"],
        "hidden_at": row["hidden_at"],
        "discussion_title": row["discussion__title"] or "",
    }


def discussion_posts_service_provider() -> dict:
    return {
        "create_first_post": _create_first_post,
        "get_first_post": _get_first_post,
        "update_first_post_content": _update_first_post_content,
        "resubmit_first_post": _resubmit_first_post,
        "approve_first_post": _approve_first_post,
        "reject_first_post": _reject_first_post,
        "approved_reply_counts_by_author": _approved_reply_counts_by_author,
        "approved_discussion_stats": _approved_discussion_stats,
        "delete_discussion_posts": _delete_discussion_posts,
        "get_post_number": _get_post_number,
        "resolve_content_html": _resolve_post_content_html,
    }


def realtime_post_payload_service_provider() -> dict:
    return {
        "serialize_by_id": _serialize_post_by_id,
    }


def _create_event_post(
    *,
    discussion,
    actor,
    post_type: str,
    content: str,
    content_html: str = "",
    approved_at=None,
):
    from django.utils import timezone
    from bias_ext_posts.backend.models import Post
    from bias_ext_posts.backend.services import PostService

    locked_discussion = PostService._lock_discussion_for_post_number(discussion.id)
    return PostService._create_post_with_sequential_number(
        discussion=locked_discussion,
        user=actor,
        type=post_type,
        content=content,
        content_html=content_html,
        approval_status=Post.APPROVAL_APPROVED,
        approved_at=approved_at or timezone.now(),
        approved_by=actor,
    )


def _create_first_post(
    *,
    discussion,
    user,
    content: str,
    content_html: str,
    post_type: str,
    requires_approval: bool,
    approved_at=None,
    approved_by=None,
):
    content_method = _content_posts_method("create_first_post")
    if content_method is not None:
        return content_method(
            discussion=discussion,
            user=user,
            content=content,
            content_html=content_html,
            post_type=post_type,
            requires_approval=requires_approval,
            approved_at=approved_at,
            approved_by=approved_by,
        )

    from bias_ext_posts.backend.models import Post

    return Post.objects.create(
        discussion=discussion,
        number=1,
        user=user,
        content=content,
        content_html=content_html,
        type=post_type,
        approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
        approved_at=None if requires_approval else approved_at,
        approved_by=None if requires_approval else approved_by,
    )


def _get_first_post(discussion):
    content_method = _content_posts_method("get_first_post")
    if content_method is not None:
        return content_method(discussion)

    from bias_ext_posts.backend.models import Post

    first_post_id = getattr(discussion, "first_post_id", None)
    if not first_post_id:
        return None
    return Post.objects.filter(id=first_post_id).first()


def _update_first_post_content(discussion, *, content: str, content_html: str, editor):
    content_method = _content_posts_method("update_first_post_content")
    if content_method is not None:
        return content_method(discussion, content=content, content_html=content_html, editor=editor)

    from django.utils import timezone
    from bias_ext_posts.backend.models import Post

    first_post = Post.objects.get(id=discussion.first_post_id)
    first_post.content = content
    first_post.content_html = content_html
    first_post.edited_at = timezone.now()
    first_post.edited_user = editor
    first_post.save(update_fields=["content", "content_html", "edited_at", "edited_user"])
    return first_post


def _resubmit_first_post(discussion):
    content_method = _content_posts_method("resubmit_first_post")
    if content_method is not None:
        return content_method(discussion)

    from bias_ext_posts.backend.models import Post

    first_post = Post.objects.get(id=discussion.first_post_id)
    first_post.approval_status = Post.APPROVAL_PENDING
    first_post.approved_at = None
    first_post.approved_by = None
    first_post.approval_note = ""
    first_post.hidden_at = None
    first_post.hidden_user = None
    first_post.save(update_fields=[
        "approval_status",
        "approved_at",
        "approved_by",
        "approval_note",
        "hidden_at",
        "hidden_user",
        "is_private",
    ])
    return first_post


def _approve_first_post(discussion, *, approved_at, approved_by, note: str = ""):
    content_method = _content_posts_method("approve_first_post")
    if content_method is not None:
        return content_method(discussion, approved_at=approved_at, approved_by=approved_by, note=note)

    from bias_core.extensions.runtime import refresh_runtime_model_private
    from bias_ext_posts.backend.models import Post

    first_post = Post.objects.filter(id=getattr(discussion, "first_post_id", None)).first()
    if first_post is None:
        return None
    first_post.approval_status = Post.APPROVAL_APPROVED
    first_post.approved_at = approved_at
    first_post.approved_by = approved_by
    first_post.approval_note = note
    first_post.hidden_at = None
    first_post.hidden_user = None
    first_post.is_private = bool(getattr(discussion, "is_private", False)) or refresh_runtime_model_private(first_post)
    first_post.save(update_fields=[
        "approval_status",
        "approved_at",
        "approved_by",
        "approval_note",
        "hidden_at",
        "hidden_user",
        "is_private",
    ])
    return first_post


def _reject_first_post(discussion, *, rejected_at, rejected_by, note: str = ""):
    content_method = _content_posts_method("reject_first_post")
    if content_method is not None:
        return content_method(discussion, rejected_at=rejected_at, rejected_by=rejected_by, note=note)

    from bias_core.extensions.runtime import refresh_runtime_model_private
    from bias_ext_posts.backend.models import Post

    first_post = Post.objects.filter(id=getattr(discussion, "first_post_id", None)).first()
    if first_post is None:
        return None
    first_post.approval_status = Post.APPROVAL_REJECTED
    first_post.approved_at = rejected_at
    first_post.approved_by = rejected_by
    first_post.approval_note = note
    first_post.hidden_at = rejected_at
    first_post.hidden_user = rejected_by
    first_post.is_private = bool(getattr(discussion, "is_private", False)) or refresh_runtime_model_private(first_post)
    first_post.save(update_fields=[
        "approval_status",
        "approved_at",
        "approved_by",
        "approval_note",
        "hidden_at",
        "hidden_user",
        "is_private",
    ])
    return first_post


def _approved_reply_counts_by_author(discussion, *, user_counted_post_types) -> dict:
    content_method = _content_posts_method("approved_reply_counts_by_author")
    if content_method is not None:
        return dict(content_method(discussion, user_counted_post_types=user_counted_post_types) or {})

    from django.db.models import Count
    from bias_ext_posts.backend.models import Post

    approved_replies = (
        Post.objects.filter(
            discussion=discussion,
            type__in=user_counted_post_types,
            approval_status=Post.APPROVAL_APPROVED,
            hidden_at__isnull=True,
            number__gt=1,
        )
        .exclude(user_id__isnull=True)
        .values("user_id")
        .annotate(total=Count("id"))
    )
    return {row["user_id"]: row["total"] for row in approved_replies}


def _approved_discussion_stats(discussion, *, discussion_counted_post_types) -> dict:
    content_method = _content_posts_method("approved_discussion_stats")
    if content_method is not None:
        return dict(content_method(discussion, discussion_counted_post_types=discussion_counted_post_types) or {})

    from django.db.models import Count
    from bias_ext_posts.backend.models import Post

    approved_posts = Post.objects.filter(
        discussion=discussion,
        type__in=discussion_counted_post_types,
        approval_status=Post.APPROVAL_APPROVED,
        hidden_at__isnull=True,
    ).order_by("number")

    approved_count = approved_posts.count()
    participant_count = (
        approved_posts.exclude(user_id__isnull=True)
        .values("user_id")
        .distinct()
        .aggregate(total=Count("user_id"))["total"]
        or 0
    )
    last_post = approved_posts.order_by("-number").select_related("user").first()
    if last_post is None:
        return {
            "comment_count": approved_count,
            "participant_count": participant_count,
            "last_post_id": None,
            "last_post_number": None,
            "last_posted_at": None,
            "last_posted_user": None,
        }
    return {
        "comment_count": approved_count,
        "participant_count": participant_count,
        "last_post_id": last_post.id,
        "last_post_number": last_post.number,
        "last_posted_at": last_post.created_at,
        "last_posted_user": last_post.user,
    }


def _delete_discussion_posts(discussion) -> tuple[dict, ...]:
    content_method = _content_posts_method("delete_discussion_posts")
    if content_method is not None:
        return tuple(content_method(discussion) or ())

    from bias_ext_posts.backend.models import Post

    deleted_posts = tuple(
        Post.objects.filter(discussion=discussion)
        .order_by("number")
        .values("id", "number", "approval_status", "hidden_at")
    )
    Post.objects.filter(discussion=discussion).delete()
    return deleted_posts


def _serialize_post(post, user=None, **kwargs):
    from bias_core.extensions.runtime import get_runtime_content_posts_service

    content_posts = get_runtime_content_posts_service(None)
    if content_posts is not None:
        method = content_posts.get("serialize") if isinstance(content_posts, dict) else getattr(content_posts, "serialize", None)
        if callable(method):
            return method(post, user=user, **kwargs)
    from bias_ext_posts.backend.handlers import serialize_post

    return serialize_post(post, user, **kwargs)


def _serialize_post_by_id(post_id: int, user=None, **kwargs):
    from bias_core.extensions.runtime import get_runtime_content_posts_service

    content_posts = get_runtime_content_posts_service(None)
    if content_posts is not None:
        method = content_posts.get("serialize_by_id") if isinstance(content_posts, dict) else getattr(
            content_posts,
            "serialize_by_id",
            None,
        )
        if callable(method):
            return method(post_id, user=user, **kwargs)
    from bias_ext_posts.backend.handlers import apply_post_resource_preloads, serialize_post
    from bias_ext_posts.backend.models import Post

    post = (
        apply_post_resource_preloads(
            Post.objects.select_related("discussion"),
            user=user,
        )
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return None
    return serialize_post(post, user=user, **kwargs)


def _resolve_post_content_html(post) -> str:
    content_method = _content_posts_method("resolve_content_html")
    if content_method is not None:
        return str(content_method(post) or "")

    from bias_ext_posts.backend.services import PostService

    return PostService.resolve_content_html(post)


def _reply_notification_context(reply_to_post_id: int, post_id: int, from_user):
    content_method = _content_posts_method("reply_notification_context")
    if content_method is not None:
        return content_method(reply_to_post_id, post_id, from_user)

    from bias_ext_posts.backend.models import Post

    try:
        reply_to_post = Post.objects.select_related("user", "discussion__user").get(id=reply_to_post_id)
        post = Post.objects.only("id", "number").get(id=post_id)
    except Post.DoesNotExist:
        return None

    recipient = reply_to_post.user
    if (
        recipient is None
        or recipient.id == getattr(from_user, "id", None)
        or recipient.id == getattr(reply_to_post.discussion.user, "id", None)
    ):
        return None

    return {
        "recipient": recipient,
        "payload": {
            "post_id": post_id,
            "post_number": post.number,
            "discussion_id": reply_to_post.discussion_id,
            "discussion_title": reply_to_post.discussion.title,
            "reply_to_post_id": reply_to_post_id,
            "reply_to_post_number": reply_to_post.number,
        },
    }


def _notification_context(post_id: int):
    content_method = _content_posts_method("notification_context")
    if content_method is not None:
        return content_method(post_id)

    from bias_ext_posts.backend.models import Post

    try:
        post = Post.objects.select_related("user", "discussion").get(id=post_id)
    except Post.DoesNotExist:
        return None

    return {
        "post": post,
        "author": post.user,
        "payload": {
            "post_id": post_id,
            "post_number": post.number,
            "discussion_id": post.discussion_id,
            "discussion_title": post.discussion.title if post.discussion else "",
        },
    }


def _get_post_number(post_id: int):
    content_method = _content_posts_method("get_post_number")
    if content_method is not None:
        return content_method(post_id)

    from bias_ext_posts.backend.models import Post

    return Post.objects.filter(id=post_id).values_list("number", flat=True).first()

