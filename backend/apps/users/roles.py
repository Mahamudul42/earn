HUMAN_RATER_GROUP = "human_raters"


def is_human_rater(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=HUMAN_RATER_GROUP).exists()
    )
