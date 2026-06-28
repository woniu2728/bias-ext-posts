from __future__ import annotations

from bias_core.extensions import PermissionDefinition

from bias_ext_posts.backend.constants import EXTENSION_ID


def permission_definitions():
    return (
        PermissionDefinition(
            code="post.editOwn",
            label="编辑自己的回复",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许作者编辑自己的普通回复。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="post.deleteOwn",
            label="删除自己的回复",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-times",
            description="允许作者删除自己的普通回复。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="post.edit",
            label="编辑任意回复",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许管理任意普通回复内容。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="post.delete",
            label="删除任意回复",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-trash",
            description="允许删除任意普通回复。",
            required_permissions=("discussion.hide",),
        ),
        PermissionDefinition(
            code="discussion.viewIpsPosts",
            label="查看回复 IP",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-network-wired",
            description="允许在回复 API 中查看普通回复的 IP 地址。",
            required_permissions=("viewForum",),
        ),
    )
