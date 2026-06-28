from __future__ import annotations

from bias_ext_posts.backend.forum_contracts import post_type_definitions


def build_posts_content_search_index_sql() -> str:
    searchable_post_types = ", ".join(
        f"'{definition.code}'"
        for definition in post_type_definitions()
        if definition.searchable
    ) or "'comment'"
    return f"""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS posts_content_fts_idx
        ON posts
        USING GIN (to_tsvector('simple', coalesce(content, '')))
        WHERE type IN ({searchable_post_types})
    """


def search_index_definitions():
    return (
        {
            "name": "posts_content_fts_idx",
            "drop": "DROP INDEX CONCURRENTLY IF EXISTS posts_content_fts_idx",
            "create": build_posts_content_search_index_sql,
            "description": "为可搜索帖子类型的正文提供 PostgreSQL 全文搜索索引。",
        },
    )
