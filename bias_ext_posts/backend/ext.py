from bias_ext_posts.backend.extenders import (
    admin_extenders,
    event_extenders,
    forum_extenders,
    frontend_extenders,
    model_extenders,
    resource_extenders,
    search_extenders,
    service_extenders,
)


def extend():
    return [
        *frontend_extenders(),
        *forum_extenders(),
        *event_extenders(),
        *admin_extenders(),
        *resource_extenders(),
        *model_extenders(),
        *search_extenders(),
        *service_extenders(),
    ]
