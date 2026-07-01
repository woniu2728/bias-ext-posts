from __future__ import annotations

from bias_ext_posts.backend.events import PostHiddenEvent


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


def create_timeline_from_builder(*args, **kwargs):
    return _service_method(get_runtime_service("discussions.timeline"), "create_from_builder")(*args, **kwargs)


def handle_post_hidden_timeline(event: PostHiddenEvent) -> None:
    create_timeline_from_builder(
        event,
        "post_hidden",
        extra={"post_type": "postHidden"},
        update_discussion_last_post=False,
    )
