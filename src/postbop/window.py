import gi
import logging
import threading
import math
import time

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GLib, Gtk

from .api.buffer_client import (
    create_draft_post,
    create_idea,
    create_queue_post,
    get_account,
    get_channels,
    BufferRateLimitError,
)

from .api.buffer_auth import exchange_authorization_code

from .api.companion import (
    create_oauth_session,
    get_oauth_result,
)

from .api.oauth import (
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
    hash_state,
)

from .storage.credentials import (
    load_access_token,
    load_refresh_token,
)

from .storage.preferences import (
    load_preferences,
    save_preferences,
)

from .storage.composer_state import (
    clear_composer_state,
    load_composer_state,
    save_composer_state,
)

from .settings import PostBopSettingsDialog

logger = logging.getLogger("postbop.window")

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logger.debug("Initializing PostBop window")

        self.channel_buttons = {}
        self.is_submitting = False
        self.organizations = []

        self.auth_in_progress = False

        self.buffer_connected = bool( load_access_token() and load_refresh_token() )

        self.action_keys = [
            "queue",
            "draft",
            "idea",
        ]

        self.preferences = load_preferences()

        self.composer_state = load_composer_state()

        self.has_unfinished_composer = bool(
            self.composer_state["text"].strip()
        )

        self.composer_save_source_id = None
        self.suppress_composer_save = False
        self.destinations_loaded = False

        if self.has_unfinished_composer:
            self.current_action = (
                self.composer_state["action"]
            )
        else:
            self.current_action = (
                self.preferences["last_action"]
            )

        self.retry_action = None
        self.retry_text = None
        self.retry_destinations = []
        self.retry_all_destinations = []

        self.retry_available_at = None
        self.retry_timer_source_id = None

        self.set_title("PostBop")
        self.set_default_size(500, 520)

        self._build_ui()
        if self.buffer_connected:
            self._load_channels()
        else:
            self._show_disconnected_state()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()

        header_bar = Adw.HeaderBar()

        menu = Gio.Menu()
        menu.append( "Open Buffer", "app.open-buffer" )
        menu.append( "Settings", "app.settings" )

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name( "open-menu-symbolic" )
        menu_button.set_tooltip_text( "Main Menu" )
        menu_button.set_menu_model( menu )

        header_bar.pack_end( menu_button )
        toolbar_view.add_top_bar( header_bar )

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

        if self.has_unfinished_composer:
            self.composer.get_buffer().set_text(
                self.composer_state["text"]
            )

        self.composer.get_buffer().connect(
            "changed",
            self._on_composer_changed,
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

        self.connect_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=8 )

        connect_label = Gtk.Label( label=(
            "Connect PostBop to Buffer to choose "
            "channels and start dropping posts."
        ), xalign=0 )
        connect_label.set_wrap( True )
        self.connect_box.append( connect_label )

        self.connect_button = Gtk.Button( label="Connect Buffer" )
        self.connect_button.set_halign( Gtk.Align.START )
        self.connect_button.add_css_class( "suggested-action" )
        self.connect_button.connect( "clicked", self._on_connect_clicked )
        self.connect_box.append( self.connect_button )

        self.destination_stack.add_named( self.connect_box, "connect" )

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

        self.error_revealer = Gtk.Revealer()
        self.error_revealer.set_reveal_child(
            False
        )

        error_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        self.error_label = Gtk.Label(
            label="",
            xalign=0,
        )

        self.error_label.set_wrap(True)
        self.error_label.add_css_class(
            "error"
        )

        error_box.append(
            self.error_label
        )

        self.retry_button = Gtk.Button(
            label="Retry Failed"
        )

        self.retry_button.set_halign(
            Gtk.Align.START
        )

        self.retry_button.connect(
            "clicked",
            self._on_retry_clicked,
        )

        error_box.append(
            self.retry_button
        )

        self.error_revealer.set_child(
            error_box
        )

        root.append(
            self.error_revealer
        )

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

        self.connect(
            "close-request",
            self._on_close_request,
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
        self.buffer_connected = True
        self.suppress_composer_save = True

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

        if self.has_unfinished_composer:
            saved_organization_id = (
                self.composer_state[
                    "organization_id"
                ]
            )
        else:
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

        if self.has_unfinished_composer:
            saved_channel_ids = set(
                self.composer_state[
                    "channel_ids"
                ]
            )
        else:
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
                    self._on_channel_toggled,
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

        self.destinations_loaded = True
        self.suppress_composer_save = False

        self._update_destination_mode()
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
        self._schedule_composer_state_save()


    def _update_destination_mode(self):
        if not self.buffer_connected:
            self.destination_label.set_text( "Buffer Account" )
            self.destination_stack.set_visible_child_name( "connect" )
            return

        if self.current_action == "idea":
            self.destination_label.set_text( "Organization" )
            self.destination_stack.set_visible_child_name( "organization" )
            if not self.is_submitting:
                self.drop_button.set_label( "Drop Idea" )

        else:
            self.destination_label.set_text( "Channels" )
            self.destination_stack.set_visible_child_name( "channels" )
            if not self.is_submitting:
                if self.current_action == "draft":
                    self.drop_button.set_label( "Drop to Draft" )
                else:
                    self.drop_button.set_label( "Drop to Queue" )

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
        self._schedule_composer_state_save()

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
            and self.retry_action is None
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
        all_destinations: list[dict] | None = None,
    ):
        successes = []
        failures = []

        if all_destinations is None:
            all_destinations = destinations

        for index, destination in enumerate(
            destinations
        ):
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

            except BufferRateLimitError as exception:
                logger.warning(
                    "Buffer rate limit reached"
                )

                failures.append({
                    "destination": destination,
                    "error": str(exception),
                    "retry_after": (
                        exception.retry_after
                    ),
                    "rate_limited": True,
                })

                # Don't hammer Buffer with the
                # remaining destinations.
                for remaining in destinations[
                    index + 1:
                ]:
                    failures.append({
                        "destination": remaining,
                        "error": (
                            "Not attempted because "
                            "Buffer's rate limit "
                            "was reached."
                        ),
                        "retry_after": (
                            exception.retry_after
                        ),
                        "rate_limited": True,
                    })

                break

            except Exception as exception:
                logger.exception(
                    "Unable to complete Buffer %s action for %s",
                    action,
                    destination["id"],
                )

                failures.append({
                    "destination": destination,
                    "error": str(exception),
                    "retry_after": None,
                    "rate_limited": False,
                })

        GLib.idle_add(
            self._finish_drop,
            action,
            text,
            all_destinations,
            successes,
            failures,
        )

    def _finish_drop(
        self,
        action: str,
        text: str,
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
            self._set_retry_state(
                action,
                text,
                destinations,
                failures,
            )

            if successes:
                self.status_label.set_text(
                    f"Completed {len(successes)} "
                    f"of {total} destinations."
                )
            else:
                self.status_label.set_text(
                    "Buffer could not complete "
                    "the action."
                )

            return

        self._clear_retry_state()

        self._remember_successful_action(
            action,
            destinations,
        )

        buffer = self.composer.get_buffer()

        self.suppress_composer_save = True
        buffer.set_text("")
        self.suppress_composer_save = False

        clear_composer_state()

        self.composer_state = {
            "text": "",
            "action": "queue",
            "channel_ids": [],
            "organization_id": None,
        }

        self.has_unfinished_composer = False

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

        self._notify_success(
            action,
            len(successes),
        )

        if not self.preferences[ "keep_open_after_success" ]:
            application = self.get_application()

            if application is not None:
                application.remain_alive_for_notification( 5 )
            self.close()
            return

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

    def _on_composer_changed(
        self,
        _buffer,
    ):
        if (
            not self.suppress_composer_save
            and self.retry_action is not None
        ):
            self._clear_retry_state()
            
        self._update_drop_button_state()
        self._schedule_composer_state_save()


    def _on_channel_toggled(
        self,
        _button,
    ):
        self._update_drop_button_state()
        self._schedule_composer_state_save()

    def _schedule_composer_state_save(
        self,
    ):
        if self.suppress_composer_save:
            return

        if self.composer_save_source_id is not None:
            GLib.source_remove(
                self.composer_save_source_id
            )

        self.composer_save_source_id = (
            GLib.timeout_add(
                500,
                self._save_composer_state,
            )
        )


    def _save_composer_state(self):
        self.composer_save_source_id = None

        text = self._get_composer_text()

        if not text.strip():
            clear_composer_state()

            self.has_unfinished_composer = False

            return False

        if self.destinations_loaded:
            channel_ids = [
                channel["id"]
                for channel
                in self._get_selected_channels()
            ]

            organization = (
                self._get_selected_organization()
            )

            organization_id = (
                organization["id"]
                if organization is not None
                else None
            )

        else:
            # Preserve recovered destinations until
            # Buffer data has finished loading.
            channel_ids = (
                self.composer_state[
                    "channel_ids"
                ]
            )

            organization_id = (
                self.composer_state[
                    "organization_id"
                ]
            )

        state = {
            "text": text,
            "action": self.current_action,
            "channel_ids": channel_ids,
            "organization_id": organization_id,
        }

        try:
            save_composer_state(state)

            self.composer_state = state
            self.has_unfinished_composer = True

        except OSError:
            logger.exception(
                "Unable to save unfinished composer"
            )

        return False

    def _on_close_request(
        self,
        _window,
    ):
        if self.composer_save_source_id is not None:
            GLib.source_remove(
                self.composer_save_source_id
            )

            self.composer_save_source_id = None

        self._save_composer_state()

        return False

    def _set_retry_state(
        self,
        action: str,
        text: str,
        all_destinations: list[dict],
        failures: list[dict],
    ):
        self.retry_action = action
        self.retry_text = text
        self.retry_all_destinations = (
            all_destinations
        )

        self.retry_destinations = [
            failure["destination"]
            for failure in failures
        ]

        lines = []

        for failure in failures:
            name = failure[
                "destination"
            ]["name"]

            lines.append(
                f"{name}: "
                f"{failure['error']}"
            )

        self.error_label.set_text(
            "\n".join(lines)
        )

        retry_delays = [
            failure["retry_after"]
            for failure in failures
            if failure.get(
                "retry_after"
            ) is not None
        ]

        if retry_delays:
            retry_after = max(
                retry_delays
            )

            self.retry_available_at = (
                time.monotonic()
                + retry_after
            )
        else:
            self.retry_available_at = None

        self.error_revealer.set_reveal_child(
            True
        )

        self._start_retry_timer()
        self._update_drop_button_state()


    def _clear_retry_state(self):
        self.retry_action = None
        self.retry_text = None
        self.retry_destinations = []
        self.retry_all_destinations = []
        self.retry_available_at = None

        if self.retry_timer_source_id is not None:
            GLib.source_remove(
                self.retry_timer_source_id
            )

            self.retry_timer_source_id = None

        self.error_revealer.set_reveal_child(
            False
        )

        self.retry_button.set_label(
            "Retry Failed"
        )


    def _start_retry_timer(self):
        if self.retry_timer_source_id is not None:
            GLib.source_remove(
                self.retry_timer_source_id
            )

            self.retry_timer_source_id = None

        if self.retry_available_at is None:
            self.retry_button.set_label(
                "Retry Failed"
            )

            self.retry_button.set_sensitive(
                not self.is_submitting
            )

            return

        self.retry_timer_source_id = (
            GLib.timeout_add_seconds(
                1,
                self._update_retry_button,
            )
        )

        self._update_retry_button()


    def _update_retry_button(self):
        if self.retry_action is None:
            self.retry_timer_source_id = None

            return False

        if self.is_submitting:
            self.retry_button.set_sensitive(
                False
            )

            return True

        if self.retry_available_at is None:
            self.retry_button.set_label(
                "Retry Failed"
            )

            self.retry_button.set_sensitive(
                True
            )

            self.retry_timer_source_id = None

            return False

        remaining = math.ceil(
            self.retry_available_at
            - time.monotonic()
        )

        if remaining <= 0:
            self.retry_available_at = None

            self.retry_button.set_label(
                "Retry Failed"
            )

            self.retry_button.set_sensitive(
                True
            )

            self.retry_timer_source_id = None

            return False

        minutes, seconds = divmod(
            remaining,
            60,
        )

        if minutes:
            label = (
                f"Retry in {minutes}m "
                f"{seconds}s"
            )
        else:
            label = (
                f"Retry in {seconds}s"
            )

        self.retry_button.set_label(label)

        self.retry_button.set_sensitive(
            False
        )

        return True

    def _on_retry_clicked(
        self,
        _button,
    ):
        if (
            self.retry_action is None
            or not self.retry_destinations
        ):
            return

        if self.retry_available_at is not None:
            return

        action = self.retry_action
        text = self.retry_text

        retry_destinations = (
            self.retry_destinations.copy()
        )

        all_destinations = (
            self.retry_all_destinations.copy()
        )

        self.status_label.set_text(
            "Retrying failed destinations..."
        )

        self._set_submitting(True)

        thread = threading.Thread(
            target=self._drop_posts_worker,
            args=(
                action,
                text,
                retry_destinations,
                all_destinations,
            ),
            daemon=True,
        )

        thread.start()

    def _notify_success( self, action: str,  count: int ):
        if action == "idea":
            body = "Idea dropped to Buffer."

        elif action == "draft":
            body = (
                f"Dropped to Draft for "
                f"{count} Buffer "
                f"{'channel' if count == 1 else 'channels'}."
            )

        else:
            body = (
                f"Dropped to {count} Buffer "
                f"{'channel' if count == 1 else 'channels'}."
            )

        application = self.get_application()

        if application is not None:
            application.send_drop_success_notification( body )

    def show_settings(self):
        dialog = PostBopSettingsDialog( preferences=self.preferences, on_disconnect=self._on_buffer_disconnected )
        dialog.present(self)

    def _show_disconnected_state(self):
        self.buffer_connected = False
        self.destinations_loaded = False

        self.destination_label.set_text( "Buffer Account" )
        self.destination_stack.set_visible_child_name( "connect" )

        self.status_label.set_text( "No Buffer account connected." )
        self.connect_button.set_sensitive( not self.auth_in_progress )

        self._update_drop_button_state()

    def _on_connect_clicked( self, _button ):
        if self.auth_in_progress:
            return

        self.auth_in_progress = True

        self.connect_button.set_sensitive( False )
        self.connect_button.set_label( "Connecting..." )

        self.status_label.set_text( "Preparing Buffer authorization..." )

        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge( code_verifier )

        state = generate_state()

        authorization_url = build_authorization_url( code_challenge, state )

        thread = threading.Thread(
            target=self._prepare_oauth_worker,
            args=( state, code_verifier, authorization_url ),
            daemon=True,
        )

        thread.start()

    def _prepare_oauth_worker( self, state: str, code_verifier: str, authorization_url: str ):
        try:
            create_oauth_session( hash_state(state) )
        except Exception as exception:
            logger.exception( "Unable to prepare Buffer authorization" )
            GLib.idle_add( self._finish_oauth_error, str(exception) )
            return

        GLib.idle_add( self._open_oauth_browser, state, code_verifier, authorization_url )

    def _open_oauth_browser( self, state: str, code_verifier: str, authorization_url: str ):
        try:
            Gio.AppInfo.launch_default_for_uri( authorization_url, None )
        except GLib.Error as exception:
            logger.exception( "Unable to open Buffer authorization" )
            self._finish_oauth_error( str(exception) )
            return False

        self.status_label.set_text( "Complete authorization in your browser." )
        thread = threading.Thread(
            target=self._poll_oauth_result_worker,
            args=( state, code_verifier ),
            daemon=True,
        )

        thread.start()
        return False

    def _poll_oauth_result_worker( self, state: str, code_verifier: str ):
        deadline = time.monotonic() + 180

        while time.monotonic() < deadline:
            try:
                result = get_oauth_result( state )
                authorization_code = result.get( "code" )
                error = result.get( "error" )

                if error:
                    raise RuntimeError( str(error) )

                if authorization_code:
                    exchange_authorization_code( authorization_code, code_verifier )
                    GLib.idle_add( self._finish_oauth_success )
                    return

            except Exception as exception:
                logger.exception( "Buffer authorization failed" )
                GLib.idle_add( self._finish_oauth_error, str(exception)  )
                return

            time.sleep(1)

        GLib.idle_add( self._finish_oauth_error, "Buffer authorization timed out." )

    def _finish_oauth_success(self):
        self.auth_in_progress = False
        self.buffer_connected = True

        self.connect_button.set_label( "Connect Buffer" )
        self.connect_button.set_sensitive(True)
        self.status_label.set_text( "Connected to Buffer. Loading channels..." )

        self._update_destination_mode()
        self._load_channels()

        return False

    def _finish_oauth_error( self, message: str ):
        self.auth_in_progress = False

        self.connect_button.set_label( "Connect Buffer" )
        self.connect_button.set_sensitive( True )
        self.status_label.set_text( message )

        return False

    def _on_buffer_disconnected( self ):
        self.buffer_connected = False
        self.destinations_loaded = False

        self._clear_retry_state()

        self.organizations = []

        self.organization_model.splice( 0, self.organization_model.get_n_items(), [] )
        self.organization_dropdown.set_sensitive( False )

        self.channel_buttons.clear()
        self._clear_channel_box()

        self.preferences[ "last_channel_ids" ] = []

        self.preferences[ "last_idea_organization_id" ] = None

        try:
            save_preferences( self.preferences )
        except OSError:
            logger.exception( "Unable to save disconnected preferences" )

        self.composer_state[ "channel_ids" ] = []
        self.composer_state[ "organization_id" ] = None

        text = self._get_composer_text()
        if text.strip():
            try:
                save_composer_state( self.composer_state )
            except OSError:
                logger.exception( "Unable to update composer state after Buffer disconnect" )

        self._show_disconnected_state()