from dataclasses import dataclass
from math import ceil
from typing import Any, List, Optional

from bias_core.extensions.platform import apply_model_visibility_scope, can_view_model_instance
from bias_ext_posts.backend.content_models import get_post_model
from bias_ext_posts.backend.models import Post


def get_runtime_service(service_key: str, default=None):
    from bias_core.extensions.runtime import get_runtime_service as runtime_get_service

    return runtime_get_service(service_key, default)


@dataclass
class PostStreamWindow:
    posts: List[Post]
    total: int
    page: int
    limit: int
    current_start: int
    current_end: int
    has_previous: bool
    has_more: bool


def can_view_post(post: Post, user: Optional[Any]) -> bool:
    content_method = _content_posts_method("can_view")
    if content_method is not None:
        return bool(content_method(post, user))
    return can_view_model_instance(get_post_model(), post, user=user, ability="view")


def apply_visibility_filters(queryset, user: Optional[Any] = None):
    content_method = _content_posts_method("apply_visibility")
    if content_method is not None:
        return content_method(queryset, user)
    return apply_model_visibility_scope(queryset.model, queryset, user=user, ability="view")


def build_visible_post_queryset(
    discussion_id: int,
    *,
    stream_post_types,
    user: Optional[Any] = None,
    preload=None,
):
    content_method = _content_posts_method("build_visible_queryset")
    if content_method is not None:
        return content_method(
            discussion_id,
            stream_post_types=stream_post_types,
            user=user,
            preload=preload,
        )
    PostModel = get_post_model()
    queryset = PostModel.objects.filter(
        discussion_id=discussion_id,
        type__in=stream_post_types,
    )
    if preload is not None:
        queryset = preload(queryset)
    queryset = apply_visibility_filters(queryset, user)
    return queryset.order_by("number")


def get_post_window(
    discussion_id: int,
    *,
    stream_post_types,
    limit: int = 20,
    page: int = 1,
    near: Optional[int] = None,
    before: Optional[int] = None,
    after: Optional[int] = None,
    user: Optional[Any] = None,
    preload=None,
) -> PostStreamWindow:
    content_method = _content_posts_method("get_window")
    if content_method is not None:
        window = content_method(
            discussion_id,
            stream_post_types=stream_post_types,
            limit=limit,
            page=page,
            near=near,
            before=before,
            after=after,
            user=user,
            preload=preload,
        )
        return PostStreamWindow(
            posts=list(getattr(window, "posts", []) or []),
            total=int(getattr(window, "total", 0) or 0),
            page=int(getattr(window, "page", 1) or 1),
            limit=int(getattr(window, "limit", limit) or limit),
            current_start=int(getattr(window, "current_start", 0) or 0),
            current_end=int(getattr(window, "current_end", 0) or 0),
            has_previous=bool(getattr(window, "has_previous", False)),
            has_more=bool(getattr(window, "has_more", False)),
        )
    queryset = build_visible_post_queryset(
        discussion_id=discussion_id,
        stream_post_types=stream_post_types,
        user=user,
        preload=preload,
    )
    total = queryset.count()

    if total <= 0:
        return PostStreamWindow(
            posts=[],
            total=0,
            page=1,
            limit=limit,
            current_start=0,
            current_end=0,
            has_previous=False,
            has_more=False,
        )

    mode_count = sum(1 for value in (near, before, after) if value is not None)
    if mode_count > 1:
        raise ValueError("near、before、after 只能传一个")

    page_limit = max(1, int(limit or 20))
    fetch_limit = page_limit + 1
    has_previous = False
    has_more = False

    if near is not None:
        posts = list(queryset.filter(number__gte=near).order_by("number")[:fetch_limit])
        has_more = len(posts) > page_limit
        posts = posts[:page_limit]
        if not posts:
            posts = list(queryset.order_by("-number")[:page_limit])
            posts.reverse()
            has_previous = total > len(posts)
        else:
            has_previous = queryset.filter(number__lt=posts[0].number).exists()
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
    elif before is not None:
        posts = list(queryset.filter(number__lt=before).order_by("-number")[:fetch_limit])
        has_previous = len(posts) > page_limit
        posts = posts[:page_limit]
        posts.reverse()
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
        if posts:
            has_more = queryset.filter(number__gt=current_end).exists()
    elif after is not None:
        posts = list(queryset.filter(number__gt=after).order_by("number")[:fetch_limit])
        has_more = len(posts) > page_limit
        posts = posts[:page_limit]
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
        if posts:
            has_previous = queryset.filter(number__lt=current_start).exists()
    else:
        offset = (page - 1) * page_limit
        posts = list(queryset[offset:offset + fetch_limit])
        has_more = len(posts) > page_limit
        posts = posts[:page_limit]
        has_previous = offset > 0 and bool(posts)
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0

    resolved_page = page
    if current_end and (near is not None or before is not None or after is not None):
        resolved_position = queryset.filter(number__lte=current_end).count()
        resolved_page = max(1, ceil(resolved_position / page_limit))

    return PostStreamWindow(
        posts=posts,
        total=total,
        page=resolved_page,
        limit=page_limit,
        current_start=current_start,
        current_end=current_end,
        has_previous=has_previous,
        has_more=has_more,
    )


def get_page_for_near_post(
    discussion_id: int,
    near: int,
    *,
    stream_post_types,
    limit: int = 20,
    user: Optional[Any] = None,
) -> int:
    content_method = _content_posts_method("get_page_for_near_post")
    if content_method is not None:
        return int(content_method(
            discussion_id,
            near,
            stream_post_types=stream_post_types,
            limit=limit,
            user=user,
        ) or 1)
    PostModel = get_post_model()
    queryset = PostModel.objects.filter(
        discussion_id=discussion_id,
        number__lte=near,
        type__in=stream_post_types,
    )

    queryset = apply_visibility_filters(queryset, user)

    position = queryset.count()
    if position <= 0:
        return 1

    return max(1, ceil(position / limit))


def _content_posts_method(name: str):
    service = get_runtime_service("content.posts", None)
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None) if service is not None else None
    return method if callable(method) else None

