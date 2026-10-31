import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("postbop.preferences")

VALID_ACTIONS = {
    "queue",
    "draft",
    "idea",
}

DEFAULT_PREFERENCES = {
    "last_action": "queue",
    "last_channel_ids": [],
    "last_idea_organization_id": None,
}

def get_preferences_path() -> Path:
    config_home = os.environ.get(
        "XDG_CONFIG_HOME"
    )

    if config_home:
        base_directory = Path(config_home)
    else:
        base_directory = (
            Path.home()
            / ".config"
        )

    return (
        base_directory
        / "postbop"
        / "preferences.json"
    )

def load_preferences() -> dict:
    preferences = DEFAULT_PREFERENCES.copy()

    path = get_preferences_path()

    if not path.exists():
        return preferences

    try:
        saved = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        logger.exception(
            "Unable to load PostBop preferences"
        )

        return preferences

    if not isinstance(saved, dict):
        return preferences

    action = saved.get("last_action")

    if action in VALID_ACTIONS:
        preferences["last_action"] = action

    channel_ids = saved.get(
        "last_channel_ids"
    )

    if (
        isinstance(channel_ids, list)
        and all(
            isinstance(channel_id, str)
            for channel_id in channel_ids
        )
    ):
        preferences[
            "last_channel_ids"
        ] = channel_ids

    organization_id = saved.get(
        "last_idea_organization_id"
    )

    if (
        organization_id is None
        or isinstance(
            organization_id,
            str,
        )
    ):
        preferences[
            "last_idea_organization_id"
        ] = organization_id

    return preferences

def save_preferences(
    preferences: dict,
) -> None:
    path = get_preferences_path()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            preferences,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)