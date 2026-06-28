from bias_core.extensions import setting_field


def setting_field_definitions():
    return (
        setting_field({
            "key": "allow_hide_own_posts",
            "label": "作者可隐藏自己的回复",
            "type": "select",
            "default": "reply",
            "help_text": "控制回复作者在发布后是否仍可隐藏自己的回复。",
            "order": 10,
            "options": (
                {"value": "reply", "label": "成为最后回复时"},
                {"value": "-1", "label": "始终允许"},
                {"value": "0", "label": "不允许"},
                {"value": "10", "label": "10 分钟内"},
                {"value": "60", "label": "1 小时内"},
            ),
        }),
    )
