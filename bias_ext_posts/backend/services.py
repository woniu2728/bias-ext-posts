"""帖子系统业务逻辑层。"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from django.db import IntegrityError

from django.utils import timezone

from bias_core.extensions.platform import get_extension_settings, sqlite_write_retry
from bias_core.extensions.platform import get_forum_event_bus
from bias_core.extensions.platform import evaluate_extension_policy
from bias_core.extensions.runtime import (
    get_runtime_content_posts_service,
    lock_runtime_discussion_for_post_number,
    refresh_runtime_discussion_approved_stats,
    validate_runtime_replyable_discussion,
)
from bias_core.extensions.platform import get_forum_registry
from bias_ext_posts.backend import post_query_service, service_lifecycle, service_moderation
from bias_ext_posts.backend.models import Post
from bias_core.extensions.runtime import (
    has_runtime_forum_permission,
)


def _get_forum_registry():
    return get_forum_registry()


def _get_default_post_type() -> str:
    return _get_forum_registry().get_default_post_type_code()


def _get_stream_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_stream_post_type_codes()


def _get_discussion_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_discussion_counted_post_type_codes()


def _get_user_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_user_counted_post_type_codes()


PostStreamWindow = post_query_service.PostStreamWindow


class PostService:
    """帖子服务"""

    POST_NUMBER_CONFLICT_RETRY_ATTEMPTS = 3

    @staticmethod
    def _can_view_post(post: Post, user: Optional[Any]) -> bool:
        return post_query_service.can_view_post(post, user)

    @staticmethod
    def apply_visibility_filters(queryset, user: Optional[Any] = None):
        return post_query_service.apply_visibility_filters(queryset, user)

    @staticmethod
    @sqlite_write_retry()
    def create_post(
        discussion_id: int,
        content: str,
        user: Any,
        reply_to_post_id: Optional[int] = None,
    ) -> Post:
        """
        创建帖子（回复讨论）

        Args:
            discussion_id: 讨论ID
            content: 帖子内容
            user: 创建者

        Returns:
            Post: 创建的帖子对象

        Raises:
            ValueError: 讨论不存在或已锁定
        """
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            create = content_posts.get("create") if isinstance(content_posts, dict) else getattr(content_posts, "create", None)
            if callable(create):
                return create(
                    discussion_id=discussion_id,
                    content=content,
                    user=user,
                    reply_to_post_id=reply_to_post_id,
                    default_post_type=_get_default_post_type(),
                    discussion_counted_post_types=_get_discussion_counted_post_types(),
                    user_counted_post_types=_get_user_counted_post_types(),
                    can_reply_in_discussion_cb=PostService._validate_replyable_discussion,
                    runtime_model=Post,
                )
        return service_lifecycle.create_post(
            discussion_id,
            content,
            user,
            reply_to_post_id=reply_to_post_id,
            default_post_type=_get_default_post_type(),
            can_reply_in_discussion=PostService._validate_replyable_discussion,
            render_markdown_cb=PostService._render_markdown,
            lock_discussion_for_post_number_cb=PostService._lock_discussion_for_post_number,
            create_post_with_sequential_number_cb=PostService._create_post_with_sequential_number,
        )

    @staticmethod
    def get_post_list(
        discussion_id: int,
        page: int = 1,
        limit: int = 20,
        user: Optional[Any] = None,
        preload=None,
    ) -> Tuple[List[Post], int]:
        """
        获取帖子列表

        Args:
            discussion_id: 讨论ID
            page: 页码
            limit: 每页数量
            user: 当前用户（用于判断点赞状态）

        Returns:
            Tuple[List[Post], int]: (帖子列表, 总数)
        """
        return service_lifecycle.get_post_list(
            discussion_id,
            page=page,
            limit=limit,
            user=user,
            preload=preload,
            stream_post_types=_get_stream_post_types(),
            apply_visibility_filters_cb=PostService.apply_visibility_filters,
        )

    @staticmethod
    def _build_visible_post_queryset(
        discussion_id: int,
        user: Optional[Any] = None,
        preload=None,
    ):
        return post_query_service.build_visible_post_queryset(
            discussion_id,
            stream_post_types=_get_stream_post_types(),
            user=user,
            preload=preload,
        )

    @staticmethod
    def get_post_window(
        discussion_id: int,
        *,
        limit: int = 20,
        page: int = 1,
        near: Optional[int] = None,
        before: Optional[int] = None,
        after: Optional[int] = None,
        user: Optional[Any] = None,
        preload=None,
    ) -> PostStreamWindow:
        return post_query_service.get_post_window(
            discussion_id,
            stream_post_types=_get_stream_post_types(),
            limit=limit,
            page=page,
            near=near,
            before=before,
            after=after,
            user=user,
            preload=preload,
        )

    @staticmethod
    def get_page_for_near_post(
        discussion_id: int,
        near: int,
        limit: int = 20,
        user: Optional[Any] = None,
    ) -> int:
        return post_query_service.get_page_for_near_post(
            discussion_id,
            near,
            stream_post_types=_get_stream_post_types(),
            limit=limit,
            user=user,
        )

    @staticmethod
    def get_post_by_id(
        post_id: int,
        user: Optional[Any] = None,
        preload=None,
    ) -> Optional[Post]:
        """
        获取帖子详情

        Args:
            post_id: 帖子ID
            user: 当前用户

        Returns:
            Optional[Post]: 帖子对象
        """
        return service_lifecycle.get_post_by_id(
            post_id,
            user=user,
            preload=preload,
            can_view_post_cb=PostService._can_view_post,
        )

    @staticmethod
    def update_post(
        post_id: int,
        user: Any,
        content: str,
    ) -> Post:
        """
        更新帖子

        Args:
            post_id: 帖子ID
            user: 操作用户
            content: 新内容

        Returns:
            Post: 更新后的帖子对象

        Raises:
            PermissionDenied: 权限不足
        """
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            update = content_posts.get("update") if isinstance(content_posts, dict) else getattr(content_posts, "update", None)
            if callable(update):
                return update(
                    post_id,
                    user,
                    content,
                    can_edit_post_cb=PostService.can_edit_post,
                    runtime_model=Post,
                )
        return service_lifecycle.update_post(
            post_id,
            user,
            content,
            can_edit_post_cb=PostService.can_edit_post,
            render_markdown_cb=PostService._render_markdown,
        )

    @staticmethod
    def delete_post(post_id: int, user: Any) -> bool:
        """
        删除帖子

        Args:
            post_id: 帖子ID
            user: 操作用户

        Returns:
            bool: 是否删除成功

        Raises:
            PermissionDenied: 权限不足
        """
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            delete = content_posts.get("delete") if isinstance(content_posts, dict) else getattr(content_posts, "delete", None)
            if callable(delete):
                return bool(delete(
                    post_id,
                    user,
                    can_delete_post_cb=PostService.can_delete_post,
                    discussion_counted_post_types=_get_discussion_counted_post_types(),
                    user_counted_post_types=_get_user_counted_post_types(),
                ))
        return service_lifecycle.delete_post(
            post_id,
            user,
            can_delete_post_cb=PostService.can_delete_post,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def set_hidden_state(post: Post, admin_user: Any, is_hidden: bool) -> Post:
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            set_hidden = content_posts.get("set_hidden_state") if isinstance(content_posts, dict) else getattr(content_posts, "set_hidden_state", None)
            if callable(set_hidden):
                return set_hidden(
                    post,
                    admin_user,
                    is_hidden,
                    can_hide_post_cb=PostService.can_hide_post,
                    discussion_counted_post_types=_get_discussion_counted_post_types(),
                    user_counted_post_types=_get_user_counted_post_types(),
                    runtime_model=Post,
                )
        return service_lifecycle.set_hidden_state(
            post,
            admin_user,
            is_hidden,
            can_hide_post_cb=PostService.can_hide_post,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def _validate_replyable_discussion(
        discussion_id: int,
        user: Any,
        *,
        discussion=None,
    ):
        return validate_runtime_replyable_discussion(
            discussion_id,
            user,
            discussion=discussion,
        )

    @staticmethod
    def _lock_discussion_for_post_number(discussion_id: int):
        return lock_runtime_discussion_for_post_number(discussion_id)

    @staticmethod
    def _allocate_next_post_number(discussion) -> int:
        last_post = (
            Post.objects.filter(discussion=discussion)
            .order_by("-number")
            .only("number")
            .first()
        )
        return (last_post.number + 1) if last_post else 1

    @staticmethod
    def _is_post_number_conflict(exc: IntegrityError) -> bool:
        return service_lifecycle.is_post_number_conflict(exc)

    @staticmethod
    def _create_post_with_sequential_number(**post_kwargs) -> Post:
        return service_lifecycle.create_post_with_sequential_number(
            attempts=PostService.POST_NUMBER_CONFLICT_RETRY_ATTEMPTS,
            allocate_next_post_number_cb=PostService._allocate_next_post_number,
            **post_kwargs,
        )

    @staticmethod
    def _refresh_discussion_approved_stats(discussion):
        return refresh_runtime_discussion_approved_stats(
            discussion,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
        )

    @staticmethod
    def approve_post(post: Post, admin_user: Any, note: str = "") -> Post:
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            approve = content_posts.get("approve") if isinstance(content_posts, dict) else getattr(content_posts, "approve", None)
            if callable(approve):
                return approve(
                    post.id,
                    admin_user,
                    note=note,
                    discussion_counted_post_types=_get_discussion_counted_post_types(),
                    user_counted_post_types=_get_user_counted_post_types(),
                    runtime_model=Post,
                )
        return service_moderation.approve_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def reject_post(post: Post, admin_user: Any, note: str = "") -> Post:
        content_posts = get_runtime_content_posts_service(None)
        if content_posts is not None:
            reject = content_posts.get("reject") if isinstance(content_posts, dict) else getattr(content_posts, "reject", None)
            if callable(reject):
                return reject(
                    post.id,
                    admin_user,
                    note=note,
                    discussion_counted_post_types=_get_discussion_counted_post_types(),
                    user_counted_post_types=_get_user_counted_post_types(),
                    runtime_model=Post,
                )
        return service_moderation.reject_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def can_edit_post(post: Post, user: Any) -> bool:
        """检查用户是否可以编辑帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if (
            has_runtime_forum_permission(user, "post.edit")
            or has_runtime_forum_permission(user, "discussion.edit")
        ):
            allowed = True
        elif post.user_id == user.id:
            allowed = (
                has_runtime_forum_permission(user, "post.editOwn")
                or has_runtime_forum_permission(user, "discussion.editOwn")
            )
        return bool(evaluate_extension_policy(
            "post.edit",
            default=allowed,
            user=user,
            post=post,
        ))

    @staticmethod
    def can_delete_post(post: Post, user: Any) -> bool:
        """检查用户是否可以删除帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if (
            has_runtime_forum_permission(user, "post.delete")
            or has_runtime_forum_permission(user, "discussion.delete")
        ):
            allowed = True
        elif post.user_id == user.id:
            allowed = (
                has_runtime_forum_permission(user, "post.deleteOwn")
                or has_runtime_forum_permission(user, "discussion.deleteOwn")
            )
        return bool(evaluate_extension_policy(
            "post.delete",
            default=allowed,
            user=user,
            post=post,
        ))

    @staticmethod
    def can_hide_post(post: Post, user: Any) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if (
            has_runtime_forum_permission(user, "post.hide")
            or has_runtime_forum_permission(user, "discussion.hidePosts")
            or has_runtime_forum_permission(user, "discussion.hide")
        ):
            allowed = True
        elif post.user_id == user.id:
            allowed = PostService._author_can_hide_post(post, user)
        return bool(evaluate_extension_policy(
            "post.hide",
            default=allowed,
            user=user,
            post=post,
        ))

    @staticmethod
    def can_view_post_ip(post: Post, user: Any) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(post, "type", "") != "comment":
            return False
        allowed = has_runtime_forum_permission(user, "discussion.viewIpsPosts")
        return bool(evaluate_extension_policy(
            "post.view_ip",
            default=allowed,
            user=user,
            post=post,
        ))

    @staticmethod
    def _author_can_hide_post(post: Post, user: Any) -> bool:
        hidden_user_id = getattr(post, "hidden_user_id", None)
        if getattr(post, "hidden_at", None) is not None and hidden_user_id != getattr(user, "id", None):
            return False
        discussion = getattr(post, "discussion", None)
        if discussion is None:
            return False
        if not validate_runtime_replyable_discussion(
            post.discussion_id,
            user,
            discussion=discussion,
        ):
            return False
        allow_hiding = str(
            get_extension_settings("posts").get("allow_hide_own_posts", "reply") or "reply"
        ).strip()
        if allow_hiding == "-1":
            return True
        if allow_hiding == "reply":
            return getattr(post, "number", 0) >= getattr(discussion, "last_post_number", 0)
        try:
            allowed_minutes = int(allow_hiding)
        except (TypeError, ValueError):
            return False
        if allowed_minutes <= 0:
            return False
        created_at = getattr(post, "created_at", None)
        if created_at is None:
            return False
        return timezone.now() - created_at < timezone.timedelta(minutes=allowed_minutes)

    @staticmethod
    def _render_markdown(content: str) -> str:
        """
        渲染Markdown为HTML

        Args:
            content: Markdown内容

        Returns:
            str: HTML内容
        """
        from bias_core.extensions.platform import MarkdownService
        return MarkdownService.render(content, sanitize=True)

    @staticmethod
    def resolve_content_html(post: Post) -> str:
        content_html = str(getattr(post, "content_html", "") or "").strip()
        if content_html:
            return content_html
        return PostService._render_markdown(getattr(post, "content", "") or "")

