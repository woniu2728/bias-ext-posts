from __future__ import annotations

from bias_core.extensions import FrontendExtender


def frontend_extender():
    return FrontendExtender(
        admin_entry="extensions/posts/frontend/admin/index.js",
        forum_entry="extensions/posts/frontend/forum/index.js",
    )
