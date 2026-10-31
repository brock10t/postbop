import gi
import logging
import threading

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk

from .api.buffer_client import (
    create_queue_post,
    get_account,
    get_channels,
)

logger = logging.getLogger("postbop.window")

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logger.debug("Initializing PostBop window")

        self.channel_buttons = {}
        self.is_submitting = False

        self.set_title("PostBop")
        self.set_default_size(500, 520)

        self._build_ui()
        self._load_channels()

    def _build_ui(self):
        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )

        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)

        title = Gtk.Label(
            label="PostBop",
            xalign=0,
        )
        title.add_css_class("title-2")

        root.append(title)

        composer_label = Gtk.Label(
            label="Post",
            xalign=0,
        )
        composer_label.add_css_class("heading")

        root.append(composer_label)

        self.composer = Gtk.TextView()
        self.composer.set_wrap_mode(
            Gtk.WrapMode.WORD_CHAR
        )

        self.composer.set_top_margin(8)
        self.composer.set_bottom_margin(8)
        self.composer.set_left_margin(8)
        self.composer.set_right_margin(8)

        self.composer.get_buffer().connect(
            "changed",
            self._update_drop_button_state,
        )

        composer_scroll = Gtk.ScrolledWindow()
        composer_scroll.set_min_content_height(150)
        composer_scroll.set_vexpand(True)
        composer_scroll.set_child(self.composer)

        root.append(composer_scroll)

        channel_label = Gtk.Label(
            label="Channels",
            xalign=0,
        )
        channel_label.add_css_class("heading")

        root.append(channel_label)

        self.channel_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        self.loading_label = Gtk.Label(
            label="Loading Buffer channels...",
            xalign=0,
        )

        self.channel_box.append(
            self.loading_label
        )

        channel_scroll = Gtk.ScrolledWindow()
        channel_scroll.set_min_content_height(140)
        channel_scroll.set_child(
            self.channel_box
        )

        root.append(channel_scroll)

        self.status_label = Gtk.Label(
            label="",
            xalign=0,
        )

        self.status_label.set_wrap(True)

        root.append(self.status_label)

        self.drop_button = Gtk.Button(
            label="Drop to Queue"
        )

        self.drop_button.add_css_class(
            "suggested-action"
        )

        self.drop_button.connect(
            "clicked",
            self._on_drop_clicked,
        )
        
        self.drop_button.set_sensitive(False)

        root.append(self.drop_button)

        self.set_content(root)

    def _load_channels(self):
        logger.debug(
            "Starting Buffer channel load"
        )

        thread = threading.Thread(
            target=self._load_channels_worker,
            daemon=True,
        )

        thread.start()

    def _load_channels_worker(self):
        try:
            account = get_account()

            channel_groups = []

            for organization in account.get(
                "organizations",
                [],
            ):
                channels = get_channels(
                    organization["id"]
                )

                channel_groups.append({
                    "organization": organization,
                    "channels": channels,
                })

            GLib.idle_add(
                self._populate_channels,
                channel_groups,
            )

        except Exception as exception:
            logger.exception(
                "Unable to load Buffer channels"
            )

            GLib.idle_add(
                self._show_channel_error,
                str(exception),
            )

    def _clear_channel_box(self):
        child = self.channel_box.get_first_child()

        while child is not None:
            next_child = child.get_next_sibling()

            self.channel_box.remove(child)

            child = next_child

    def _populate_channels(
        self,
        channel_groups,
    ):
        self._clear_channel_box()

        self.channel_buttons.clear()

        if not channel_groups:
            label = Gtk.Label(
                label="No Buffer organizations found.",
                xalign=0,
            )

            self.channel_box.append(label)

            return

        channel_count = 0

        for group in channel_groups:
            organization = group["organization"]
            channels = group["channels"]

            organization_label = Gtk.Label(
                label=organization["name"],
                xalign=0,
            )

            organization_label.add_css_class(
                "heading"
            )

            self.channel_box.append(
                organization_label
            )

            for channel in channels:
                display_name = (
                    channel.get("displayName")
                    or channel.get("name")
                    or "Unnamed channel"
                )

                service = channel.get(
                    "service",
                    "unknown",
                )

                label = (
                    f"{display_name} · "
                    f"{service.title()}"
                )

                unavailable_reason = None

                if channel.get("isDisconnected"):
                    unavailable_reason = (
                        "Disconnected"
                    )
                elif channel.get("isLocked"):
                    unavailable_reason = "Locked"

                if unavailable_reason:
                    label += (
                        f" ({unavailable_reason})"
                    )

                button = Gtk.CheckButton(
                    label=label
                )

                button.connect(
                    "toggled",
                    self._update_drop_button_state,
                )

                if unavailable_reason:
                    button.set_sensitive(False)

                self.channel_box.append(button)

                self.channel_buttons[
                    channel["id"]
                ] = {
                    "button": button,
                    "channel": channel,
                    "organization": organization,
                    "available": unavailable_reason is None,
                }

                channel_count += 1

        logger.info(
            "Loaded %d Buffer channels",
            channel_count,
        )

        self.status_label.set_text(
            f"{channel_count} Buffer "
            f"{'channel' if channel_count == 1 else 'channels'} "
            "available."
        )

        self._update_drop_button_state()

    def _show_channel_error(
        self,
        message: str,
    ):
        self._clear_channel_box()

        label = Gtk.Label(
            label="Unable to load Buffer channels.",
            xalign=0,
        )

        self.channel_box.append(label)

        self.status_label.set_text(message)

    def _get_composer_text(self) -> str:
        buffer = self.composer.get_buffer()

        start, end = buffer.get_bounds()

        return buffer.get_text(
            start,
            end,
            False,
        )

    def _get_selected_channels(self) -> list[dict]:
        selected = []

        for channel_id, entry in self.channel_buttons.items():
            if not entry["button"].get_active():
                continue

            channel = entry["channel"]

            selected.append({
                "id": channel_id,
                "name": (
                    channel.get("displayName")
                    or channel.get("name")
                    or "Unnamed channel"
                ),
                "service": channel.get(
                    "service",
                    "unknown",
                ),
            })

        return selected

    def _update_drop_button_state(self, *_args):
        text = self._get_composer_text()

        has_text = bool(text.strip())
        has_channels = bool(
            self._get_selected_channels()
        )

        self.drop_button.set_sensitive(
            has_text
            and has_channels
            and not self.is_submitting
        )

    def _set_submitting(self, submitting: bool):
        self.is_submitting = submitting

        self.composer.set_sensitive(
            not submitting
        )

        for entry in self.channel_buttons.values():
            entry["button"].set_sensitive(
                entry["available"]
                and not submitting
            )

        if submitting:
            self.drop_button.set_label(
                "Dropping..."
            )
        else:
            self.drop_button.set_label(
                "Drop to Queue"
            )

        self._update_drop_button_state()

    def _on_drop_clicked(self, _button):
        text = self._get_composer_text()
        channels = self._get_selected_channels()

        if not text.strip() or not channels:
            return

        channel_count = len(channels)

        self.status_label.set_text(
            f"Dropping to {channel_count} "
            f"{'channel' if channel_count == 1 else 'channels'}..."
        )

        self._set_submitting(True)

        thread = threading.Thread(
            target=self._drop_posts_worker,
            args=(
                text,
                channels,
            ),
            daemon=True,
        )

        thread.start()

    def _drop_posts_worker(
        self,
        text: str,
        channels: list[dict],
    ):
        successes = []
        failures = []

        for channel in channels:
            try:
                post = create_queue_post(
                    channel["id"],
                    text,
                )

                successes.append({
                    "channel": channel,
                    "post": post,
                })

                logger.info(
                    "Queued post for Buffer channel %s",
                    channel["id"],
                )

            except Exception as exception:
                logger.exception(
                    "Unable to queue post for Buffer channel %s",
                    channel["id"],
                )

                failures.append({
                    "channel": channel,
                    "error": str(exception),
                })

        GLib.idle_add(
            self._finish_drop,
            successes,
            failures,
        )

    def _finish_drop(
        self,
        successes: list[dict],
        failures: list[dict],
    ):
        self._set_submitting(False)

        total = (
            len(successes)
            + len(failures)
        )

        if failures:
            failed_names = ", ".join(
                failure["channel"]["name"]
                for failure in failures
            )

            if successes:
                self.status_label.set_text(
                    f"Dropped to {len(successes)} "
                    f"of {total} channels. "
                    f"Failed: {failed_names}"
                )
            else:
                self.status_label.set_text(
                    f"Unable to drop post. "
                    f"Failed: {failed_names}"
                )

            return

        buffer = self.composer.get_buffer()

        buffer.set_text("")

        self.status_label.set_text(
            f"Dropped to {len(successes)} Buffer "
            f"{'channel' if len(successes) == 1 else 'channels'}."
        )

        self.composer.grab_focus()