import gi
import logging
import threading

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk

from .api.buffer_client import (
    create_draft_post,
    create_idea,
    create_queue_post,
    get_account,
    get_channels,
)

from .storage.preferences import (
    load_preferences,
    save_preferences,
)

logger = logging.getLogger("postbop.window")

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logger.debug("Initializing PostBop window")

        self.channel_buttons = {}
        self.is_submitting = False
        self.organizations = []

        self.action_keys = [
            "queue",
            "draft",
            "idea",
        ]

        self.preferences = load_preferences()

        self.current_action = (
            self.preferences["last_action"]
        )

        self.set_title("PostBop")
        self.set_default_size(500, 520)

        self._build_ui()
        self._load_channels()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()

        header_bar = Adw.HeaderBar()

        toolbar_view.add_top_bar(
            header_bar
        )

        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )

        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)

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

        action_label = Gtk.Label(
            label="Action",
            xalign=0,
        )
        action_label.add_css_class("heading")

        root.append(action_label)

        self.action_dropdown = Gtk.DropDown.new_from_strings([
            "Drop to Queue",
            "Drop to Draft",
            "Drop Idea",
        ])

        self.action_dropdown.set_selected(
            self.action_keys.index(
                self.current_action
            )
        )

        self.action_dropdown.connect(
            "notify::selected",
            self._on_action_changed,
        )

        root.append(self.action_dropdown)

        self.destination_label = Gtk.Label(
            label="Channels",
            xalign=0,
        )

        self.destination_label.add_css_class(
            "heading"
        )

        root.append(
            self.destination_label
        )

        self.destination_stack = Gtk.Stack()

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

        self.destination_stack.add_named(
            channel_scroll,
            "channels",
        )

        self.organization_model = Gtk.StringList()

        self.organization_dropdown = Gtk.DropDown(
            model=self.organization_model,
        )

        self.organization_dropdown.set_sensitive(
            False
        )

        self.organization_dropdown.connect(
            "notify::selected",
            self._on_organization_changed,
        )

        organization_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        organization_box.append(
            self.organization_dropdown
        )

        self.destination_stack.add_named(
            organization_box,
            "organization",
        )

        self.destination_stack.set_visible_child_name(
            "channels"
        )

        root.append(
            self.destination_stack
        )

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

        toolbar_view.set_content(root)

        self.set_content(
            toolbar_view
        )

        self._update_destination_mode()

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
                account,
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
        account,
        channel_groups,
    ):
        self._clear_channel_box()

        self.organizations = account.get(
            "organizations",
            [],
        )

        self.organization_model.splice(
            0,
            self.organization_model.get_n_items(),
            [],
        )

        for organization in self.organizations:
            self.organization_model.append(
                organization["name"]
            )

        self.organization_dropdown.set_sensitive(
            bool(self.organizations)
        )

        self.channel_buttons.clear()

        saved_organization_id = (
            self.preferences[
                "last_idea_organization_id"
            ]
        )

        selected_organization = 0

        for index, organization in enumerate(
            self.organizations
        ):
            if (
                organization["id"]
                == saved_organization_id
            ):
                selected_organization = index
                break

        if self.organizations:
            self.organization_dropdown.set_selected(
                selected_organization
            )

        self.channel_buttons.clear()

        saved_channel_ids = set(
            self.preferences[
                "last_channel_ids"
            ]
        )

        if not channel_groups:
            label = Gtk.Label(
                label="No Buffer organizations found.",
                xalign=0,
            )

            self.channel_box.append(label)

            return

        saved_channel_ids = set(
            self.preferences[
                "last_channel_ids"
            ]
        )

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

                button.set_active(
                    channel["id"]
                    in saved_channel_ids
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

    def _on_action_changed(
        self,
        _dropdown,
        _parameter,
    ):
        selected = self.action_dropdown.get_selected()

        if selected >= len(self.action_keys):
            return

        self.current_action = self.action_keys[
            selected
        ]

        self._update_destination_mode()
        self._update_drop_button_state()


    def _update_destination_mode(self):
        if self.current_action == "idea":
            self.destination_label.set_text(
                "Organization"
            )

            self.destination_stack.set_visible_child_name(
                "organization"
            )

            if not self.is_submitting:
                self.drop_button.set_label(
                    "Drop Idea"
                )

        else:
            self.destination_label.set_text(
                "Channels"
            )

            self.destination_stack.set_visible_child_name(
                "channels"
            )

            if not self.is_submitting:
                if self.current_action == "draft":
                    self.drop_button.set_label(
                        "Drop to Draft"
                    )
                else:
                    self.drop_button.set_label(
                        "Drop to Queue"
                    )

    def _get_selected_organization(
        self,
    ) -> dict | None:
        selected = (
            self.organization_dropdown.get_selected()
        )

        if selected >= len(self.organizations):
            return None

        return self.organizations[selected]


    def _on_organization_changed(
        self,
        _dropdown,
        _parameter,
    ):
        self._update_drop_button_state()

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

        if self.current_action == "idea":
            has_destination = (
                self._get_selected_organization()
                is not None
            )
        else:
            has_destination = bool(
                self._get_selected_channels()
            )

        self.drop_button.set_sensitive(
            has_text
            and has_destination
            and not self.is_submitting
        )

    def _set_submitting(self, submitting: bool):
        self.is_submitting = submitting

        self.composer.set_sensitive(
            not submitting
        )

        self.action_dropdown.set_sensitive(
            not submitting
        )

        self.organization_dropdown.set_sensitive(
            bool(self.organizations)
            and not submitting
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
            self._update_destination_mode()

        self._update_drop_button_state()

    def _on_drop_clicked(self, _button):
        text = self._get_composer_text()

        if not text.strip():
            return

        action = self.current_action

        if action == "idea":
            organization = (
                self._get_selected_organization()
            )

            if organization is None:
                return

            destinations = [{
                "id": organization["id"],
                "name": organization["name"],
            }]

        else:
            destinations = (
                self._get_selected_channels()
            )

            if not destinations:
                return

        destination_count = len(
            destinations
        )

        if action == "idea":
            self.status_label.set_text(
                "Dropping Idea..."
            )

        elif action == "draft":
            self.status_label.set_text(
                f"Dropping to Draft for "
                f"{destination_count} "
                f"{'channel' if destination_count == 1 else 'channels'}..."
            )

        else:
            self.status_label.set_text(
                f"Dropping to "
                f"{destination_count} "
                f"{'channel' if destination_count == 1 else 'channels'}..."
            )

        self._set_submitting(True)

        thread = threading.Thread(
            target=self._drop_posts_worker,
            args=(
                action,
                text,
                destinations,
            ),
            daemon=True,
        )

        thread.start()

    def _drop_posts_worker(
        self,
        action: str,
        text: str,
        destinations: list[dict],
    ):
        successes = []
        failures = []

        for destination in destinations:
            try:
                if action == "idea":
                    result = create_idea(
                        destination["id"],
                        text,
                    )

                elif action == "draft":
                    result = create_draft_post(
                        destination["id"],
                        text,
                    )

                else:
                    result = create_queue_post(
                        destination["id"],
                        text,
                    )

                successes.append({
                    "destination": destination,
                    "result": result,
                })

                logger.info(
                    "Completed Buffer %s action for %s",
                    action,
                    destination["id"],
                )

            except Exception as exception:
                logger.exception(
                    "Unable to complete Buffer %s action for %s",
                    action,
                    destination["id"],
                )

                failures.append({
                    "destination": destination,
                    "error": str(exception),
                })

        GLib.idle_add(
            self._finish_drop,
            action,
            destinations,
            successes,
            failures,
        )

    def _finish_drop(
        self,
        action: str,
        destinations: list[dict],
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
                failure[
                    "destination"
                ]["name"]
                for failure in failures
            )

            if successes:
                self.status_label.set_text(
                    f"Completed {len(successes)} "
                    f"of {total}. "
                    f"Failed: {failed_names}"
                )
            else:
                self.status_label.set_text(
                    f"Unable to complete action. "
                    f"Failed: {failed_names}"
                )

            # Preserve the composer and selections.
            return

        self._remember_successful_action(
            action,
            destinations,
        )

        buffer = self.composer.get_buffer()

        buffer.set_text("")

        if action == "idea":
            self.status_label.set_text(
                "Idea dropped to Buffer."
            )

        elif action == "draft":
            self.status_label.set_text(
                f"Dropped to Draft for "
                f"{len(successes)} Buffer "
                f"{'channel' if len(successes) == 1 else 'channels'}."
            )

        else:
            self.status_label.set_text(
                f"Dropped to {len(successes)} Buffer "
                f"{'channel' if len(successes) == 1 else 'channels'}."
            )

        self.composer.grab_focus()

    def _remember_successful_action(
        self,
        action: str,
        destinations: list[dict],
    ):
        self.preferences[
            "last_action"
        ] = action

        if action == "idea":
            self.preferences[
                "last_idea_organization_id"
            ] = destinations[0]["id"]

        else:
            self.preferences[
                "last_channel_ids"
            ] = [
                destination["id"]
                for destination in destinations
            ]

        try:
            save_preferences(
                self.preferences
            )

        except OSError:
            logger.exception(
                "Unable to save PostBop preferences"
            )