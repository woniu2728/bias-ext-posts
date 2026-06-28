from __future__ import annotations

from bias_core.extensions import PostTypeDefinition

from bias_ext_posts.backend.constants import EXTENSION_ID


def post_type_definitions():
    return (
        PostTypeDefinition(
            code="comment",
            label="普通回复",
            module_id=EXTENSION_ID,
            description="默认的讨论回复帖子类型，会参与回复统计、帖子流与全文搜索。",
            icon="far fa-comment",
            is_default=True,
            is_stream_visible=True,
            counts_toward_discussion=True,
            counts_toward_user=True,
            searchable=True,
        ),
        PostTypeDefinition(
            code="postHidden",
            label="回复隐藏状态变更",
            module_id=EXTENSION_ID,
            description="记录回复被隐藏或恢复显示的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-eye-slash",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
    )
