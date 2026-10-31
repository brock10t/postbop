import json
import logging
import os
from pathlib import Path


logger = logging.getLogger(
    "postbop.composer_state"
)

DEFAULT_STATE = {
    "text": "",
    "action": "queue",
    "channel_ids": [],
    "organization_id": None,
}

def get_composer_state_path() -> Path:
    state_home = os.environ.get(
        "XDG_STATE_HOME"
    )

    if state_home:
        base_directory = Path(state_home)
    else:
        base_directory = (
            Path.home()
            / ".local"
            / "state"
        )

    return (
        base_directory
        / "postbop"
        / "composer.json"
    )

def load_composer_state() -> dict:
    state = DEFAULT_STATE.copy()

    path = get_composer_state_path()

    if not path.exists():
        return state

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
            "Unable to load composer state"
        )

        return state

    if not isinstance(saved, dict):
        return state

    text = saved.get("text")

    if isinstance(text, str):
        state["text"] = text

    action = saved.get("action")

    if action in {
        "queue",
        "draft",
        "idea",
    }:
        state["action"] = action

    channel_ids = saved.get(
        "channel_ids"
    )

    if (
        isinstance(channel_ids, list)
        and all(
            isinstance(channel_id, str)
            for channel_id in channel_ids
        )
    ):
        state["channel_ids"] = (
            channel_ids
        )

    organization_id = saved.get(
        "organization_id"
    )

    if (
        organization_id is None
        or isinstance(
            organization_id,
            str,
        )
    ):
        state["organization_id"] = (
            organization_id
        )

    return state

def save_composer_state(
    state: dict,
) -> None:
    path = get_composer_state_path()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            state,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)

def clear_composer_state() -> None:
    path = get_composer_state_path()

    try:
        path.unlink()
    except FileNotFoundError:
        pass