from __future__ import annotations

from django.db.models import Q, Subquery

from bias_core.extensions.platform import apply_model_visibility_scope
from bias_ext_posts.backend.models import Post


def apply_runtime_model_visibility(*args, **kwargs):
    from bias_core.extensions.runtime import apply_runtime_model_visibility as runtime_apply_model_visibility

    return runtime_apply_model_visibility(*args, **kwargs)


def can_view_runtime_model_private(*args, **kwargs):
    from bias_core.extensions.runtime import can_view_runtime_model_private as runtime_can_view_model_private

    return runtime_can_view_model_private(*args, **kwargs)


def get_runtime_visible_discussion_ids(*args, **kwargs):
    from bias_core.extensions.runtime import get_runtime_visible_discussion_ids as runtime_get_visible_discussion_ids

    return runtime_get_visible_discussion_ids(*args, **kwargs)


def has_runtime_discussion_visibility(*args, **kwargs):
    from bias_core.extensions.runtime import has_runtime_discussion_visibility as runtime_has_discussion_visibility

    return runtime_has_discussion_visibility(*args, **kwargs)


def has_runtime_forum_permission(*args, **kwargs):
    from bias_core.extensions.runtime import has_runtime_forum_permission as runtime_has_forum_permission

    return runtime_has_forum_permission(*args, **kwargs)


def has_runtime_model_visibility(*args, **kwargs):
    from bias_core.extensions.runtime import has_runtime_model_visibility as runtime_has_model_visibility

    return runtime_has_model_visibility(*args, **kwargs)


def _field(prefix: str, name: str) -> str:
    return f"{prefix}{name}" if prefix else name


def build_post_visibility_q(user=None, prefix: str = "") -> Q:
    can_view_private = can_view_runtime_model_private(Post, user=user)
    return _build_post_visibility_q(user=user, prefix=prefix, include_private=can_view_private)


def apply_post_visibility_scope(queryset, user=None):
    return apply_model_visibility_scope(Post, queryset, user=user, ability="view")


def scope_post_view(queryset, context: dict):
    user = context.get("user")
    base_q = _build_post_visibility_q(user=user, include_private=True, include_hidden=True)
    if _is_staff_user(user):
        return queryset.filter(base_q)

    visible_discussion_ids = get_runtime_visible_discussion_ids(
        user=user,
        ability="view",
        context=context,
    )

    scoped_queryset = queryset.filter(
        base_q,
        discussion_id__in=Subquery(visible_discussion_ids),
    )
    public_queryset = scoped_queryset.filter(is_private=False)
    private_queryset = _apply_private_visibility_branch(
        queryset.model,
        scoped_queryset.filter(is_private=True),
        user=user,
    )
    queryset = (public_queryset | private_queryset).distinct()
    return _apply_post_hidden_visibility_branch(queryset, user=user)


def _build_post_visibility_q(
    user=None,
    prefix: str = "",
    *,
    include_private: bool = False,
    include_hidden: bool = False,
) -> Q:
    approved_q = Q(**{_field(prefix, "approval_status"): Post.APPROVAL_APPROVED})
    if not include_hidden:
        approved_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        approved_q &= Q(**{_field(prefix, "is_private"): False})

    if not user or not getattr(user, "is_authenticated", False):
        return approved_q

    if _is_staff_user(user):
        return Q()

    own_pending_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): Post.APPROVAL_PENDING,
        }
    )
    if not include_hidden:
        own_pending_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        own_pending_q &= Q(**{_field(prefix, "is_private"): False})
    own_rejected_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): Post.APPROVAL_REJECTED,
        }
    )
    if not include_private:
        own_rejected_q &= Q(**{_field(prefix, "is_private"): False})
    return approved_q | own_pending_q | own_rejected_q


def _apply_private_visibility_branch(model, queryset, *, user=None):
    if can_view_runtime_model_private(model, user=user):
        return queryset
    if not has_runtime_model_visibility(model, ability="viewPrivate", exact=True):
        return queryset.none()
    return apply_runtime_model_visibility(
        model,
        queryset,
        {"user": user, "ability": "viewPrivate"},
    )


def _apply_post_hidden_visibility_branch(queryset, *, user=None):
    if _is_staff_user(user) or _has_forum_permission(user, ("discussion.hidePosts", "discussion.hide")):
        return queryset
    visible_queryset = queryset.filter(hidden_at__isnull=True)
    if user and getattr(user, "is_authenticated", False):
        visible_queryset = visible_queryset | queryset.filter(hidden_at__isnull=False, user=user)
    if has_runtime_discussion_visibility(ability="hidePosts", exact=True):
        visible_discussion_ids = get_runtime_visible_discussion_ids(
            user=user,
            ability="hidePosts",
        )
        visible_queryset = visible_queryset | queryset.filter(
            hidden_at__isnull=False,
            discussion_id__in=Subquery(visible_discussion_ids),
        )
    return visible_queryset.distinct()


def _is_staff_user(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _has_forum_permission(user, permission_names) -> bool:
    return has_runtime_forum_permission(user, permission_names)
