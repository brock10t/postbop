import gi
import logging
import threading
import math
import time

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .api.buffer_client import ( create_draft_post, create_idea, create_queue_post,
                                get_account, get_channels, _build_link_metadata, 
                                BufferRateLimitError, BufferSubmissionUncertainError )
from .api.buffer_auth import exchange_authorization_code
from .api.companion import ( activate_media_credential, create_oauth_session, get_oauth_result )
from .api.oauth import ( build_authorization_url, generate_code_challenge, generate_code_verifier,
                            generate_state, hash_state )
from .api.media_client import ( upload_image, MediaUploadError )

from .storage.credentials import ( clear_tokens, load_access_token, load_refresh_token, store_media_token )
from .storage.preferences import ( load_preferences, save_preferences )
from .storage.composer_state import ( clear_composer_state, load_composer_state, save_composer_state )
from .storage.media_cache import ( cache_image, delete_cached_image, get_cached_image )

from .validation import ( check_selected_channels )

from .settings import PostBopSettingsDialog

from pathlib import Path

logger = logging.getLogger("postbop.window")

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logger.debug( "Initializing PostBop window" )

        self.channel_buttons = {}
        self.is_submitting = False
        self.organizations = []

        self.auth_in_progress = False

        self.buffer_connected = bool( load_access_token() and load_refresh_token() )

        self.action_keys = [ "queue", "draft", "idea", ]

        self.preferences = load_preferences()

        self.composer_state = load_composer_state()

        saved_image = self.composer_state.get( "image" )
        cached_image_path = None

        if saved_image is not None:
            cached_image_path = get_cached_image( saved_image["cached_filename"] )

        self.has_unfinished_composer = bool(
            self.composer_state["text"].strip()
            or cached_image_path is not None
            or self.composer_state.get("link_url", "").strip()
        )

        self.composer_save_source_id = None
        self.suppress_composer_save = False
        self.destinations_loaded = False

        if self.has_unfinished_composer:
            self.current_action = ( self.composer_state["action"] )
        else:
            self.current_action = ( self.preferences["last_action"] )

        self.retry_action = None
        self.retry_text = None
        self.retry_destinations = []
        self.retry_all_destinations = []
        self.retry_image_path = None
        self.retry_image_url = None
        self.retry_link_url = None
        self.retry_uncertain = []
        self.retry_failures = []

        self.retry_available_at = None
        self.retry_timer_source_id = None

        self.set_title( "PostBop" )
        self.set_default_size( 500, 520 )

        self.selected_image_path: Path | None = None
        self.selected_image_original_filename: str | None = None

        self._build_ui()
        self._restore_cached_image()
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

        root = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=12 )

        root.set_margin_top( 18 )
        root.set_margin_bottom( 18 )
        root.set_margin_start( 18 )
        root.set_margin_end( 18 )

        composer_label = Gtk.Label( label="Post", xalign=0 )
        composer_label.add_css_class( "heading" )

        root.append( composer_label )

        self.composer = Gtk.TextView()
        self.composer.set_wrap_mode( Gtk.WrapMode.WORD_CHAR )

        self.composer.set_top_margin( 8 )
        self.composer.set_bottom_margin( 8 )
        self.composer.set_left_margin( 8 )
        self.composer.set_right_margin( 8 )

        if self.has_unfinished_composer:
            self.composer.get_buffer().set_text( self.composer_state["text"] )

        self.composer.get_buffer().connect( "changed", self._on_composer_changed )

        composer_scroll = Gtk.ScrolledWindow()
        composer_scroll.set_min_content_height( 150 )
        composer_scroll.set_max_content_height( 180 )
        composer_scroll.set_vexpand( False )
        composer_scroll.set_child( self.composer )

        root.append( composer_scroll )

        self.character_status_label = Gtk.Label( label="", xalign=0 )
        self.character_status_label.set_wrap( True )
        self.character_status_label.add_css_class( "dim-label" )

        root.append( self.character_status_label )

        image_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=8 )

        self.attach_image_button = Gtk.Button( label="Attach Image" )
        self.attach_image_button.set_halign( Gtk.Align.START )
        self.attach_image_button.connect( "clicked", self._on_attach_image_clicked )

        image_box.append( self.attach_image_button )

        drop_zone = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )
        drop_zone.set_size_request( -1, 64 )
        drop_zone.add_css_class( "card" )
        drop_zone.set_valign( Gtk.Align.CENTER )

        drop_label = Gtk.Label( label="Drop an image here" )
        drop_label.add_css_class( "dim-label" )

        drop_zone.append( drop_label )

        drop_target = Gtk.DropTarget.new( Gdk.FileList, Gdk.DragAction.COPY )
        drop_target.connect( "drop", self._on_image_dropped, )
        drop_zone.add_controller( drop_target )

        image_box.append( drop_zone )

        self.image_preview_box = Gtk.Box( orientation=Gtk.Orientation.HORIZONTAL, spacing=12 )
        self.image_preview_box.set_visible( False )
        self.image_preview = Gtk.Picture()
        self.image_preview.set_size_request( 96, 96 )
        self.image_preview.set_content_fit( Gtk.ContentFit.CONTAIN )
        self.image_preview.set_can_shrink( True )

        self.image_preview_box.append( self.image_preview )

        image_details = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )
        image_details.set_hexpand( True )
        image_details.set_valign( Gtk.Align.CENTER )

        self.image_filename_label = Gtk.Label( label="", xalign=0 )
        self.image_filename_label.set_wrap( True )
        self.image_filename_label.set_max_width_chars( 35 )

        image_details.append( self.image_filename_label )

        self.remove_image_button = Gtk.Button( label="Remove Image" )
        self.remove_image_button.set_halign( Gtk.Align.START )
        self.remove_image_button.connect( "clicked", self._on_remove_image_clicked )

        image_details.append( self.remove_image_button )

        self.image_preview_box.append( image_details )

        image_box.append( self.image_preview_box )

        root.append( image_box )

        link_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )
        link_label = Gtk.Label( label="Link Attachment", xalign=0 )
        link_box.append(link_label)

        self.link_entry = Gtk.Entry()
        self.link_entry.set_placeholder_text( "https://example.com/article" )
        self.link_entry.set_input_purpose( Gtk.InputPurpose.URL )
        self.link_entry.set_max_length( 2048 )
        self.link_entry.set_text( self.composer_state.get("link_url", "") )

        self.link_entry.connect( "changed", self._on_link_changed )

        link_box.append(self.link_entry)

        self.link_status_label = Gtk.Label( label="", xalign=0 )
        self.link_status_label.set_wrap(True)
        self.link_status_label.add_css_class("dim-label")
        self.link_status_label.set_visible(False)

        link_box.append(self.link_status_label)

        root.append(link_box)

        action_label = Gtk.Label( label="Action", xalign=0 )
        action_label.add_css_class( "heading" )

        root.append( action_label )

        self.action_dropdown = Gtk.DropDown.new_from_strings([ "Drop to Queue", "Drop to Draft", "Drop Idea" ])
        self.action_dropdown.set_selected( self.action_keys.index( self.current_action ) )
        self.action_dropdown.connect( "notify::selected", self._on_action_changed )

        root.append( self.action_dropdown )

        self.destination_label = Gtk.Label( label="Channels", xalign=0 )

        self.destination_label.add_css_class( "heading" )

        root.append( self.destination_label )

        self.destination_stack = Gtk.Stack()

        self.connect_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=8 )

        connect_label = Gtk.Label( label=(
            "Connect PostBop to Buffer to choose  channels and start dropping posts."
        ), xalign=0 )
        connect_label.set_wrap( True )
        self.connect_box.append( connect_label )

        self.connect_button = Gtk.Button( label="Connect Buffer" )
        self.connect_button.set_halign( Gtk.Align.START )
        self.connect_button.add_css_class( "suggested-action" )
        self.connect_button.connect( "clicked", self._on_connect_clicked )
        self.connect_box.append( self.connect_button )

        self.destination_stack.add_named( self.connect_box, "connect" )

        self.channel_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )
        self.loading_label = Gtk.Label( label="Loading Buffer channels...", xalign=0 )

        self.channel_box.append( self.loading_label )

        channel_scroll = Gtk.ScrolledWindow()
        channel_scroll.set_min_content_height( 140 )
        channel_scroll.set_child( self.channel_box )

        self.destination_stack.add_named( channel_scroll, "channels" )

        self.organization_model = Gtk.StringList()
        self.organization_dropdown = Gtk.DropDown( model=self.organization_model )
        self.organization_dropdown.set_sensitive( False )

        self.organization_dropdown.connect( "notify::selected", self._on_organization_changed )
        organization_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )

        organization_box.append( self.organization_dropdown )

        self.destination_stack.add_named( organization_box, "organization" )
        self.destination_stack.set_visible_child_name( "channels" )

        root.append( self.destination_stack )

        self.status_label = Gtk.Label( label="", xalign=0 )
        self.status_label.set_wrap( True )

        root.append( self.status_label )

        self.error_revealer = Gtk.Revealer()
        self.error_revealer.set_reveal_child( False )

        error_box = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, spacing=6 )

        self.error_label = Gtk.Label( label="", xalign=0 )
        self.error_label.set_wrap(True)
        self.error_label.add_css_class( "error" )

        error_box.append( self.error_label )

        self.retry_button = Gtk.Button( label="Retry Failed" )
        self.retry_button.set_halign( Gtk.Align.START )
        self.retry_button.connect( "clicked", self._on_retry_clicked )

        error_actions = Gtk.Box( orientation=Gtk.Orientation.HORIZONTAL, spacing=6 )

        error_actions.set_halign(Gtk.Align.START)
        error_actions.append(self.retry_button)

        self.open_buffer_error_button = Gtk.Button( label="Open Buffer" )
        self.open_buffer_error_button.set_visible(False)
        self.open_buffer_error_button.connect( "clicked", self._on_open_buffer_for_verification )
        error_actions.append( self.open_buffer_error_button )

        self.resolve_unknown_button = Gtk.Button( label="Resolve Unknown" )
        self.resolve_unknown_button.set_visible(False)
        self.resolve_unknown_button.connect( "clicked", self._on_resolve_unknown_clicked )
        error_actions.append( self.resolve_unknown_button )

        error_box.append( error_actions )

        self.error_revealer.set_child( error_box )

        root.append( self.error_revealer )

        self.drop_button = Gtk.Button( label="Drop to Queue" )
        self.drop_button.add_css_class( "suggested-action" )
        self.drop_button.connect( "clicked", self._on_drop_clicked )
        self.drop_button.set_sensitive( False )

        bottom_bar = Gtk.Box( orientation=Gtk.Orientation.VERTICAL, )

        bottom_bar.add_css_class( "toolbar" )

        bottom_bar.set_margin_top( 8 )
        bottom_bar.set_margin_bottom( 8 )
        bottom_bar.set_margin_start( 18 )
        bottom_bar.set_margin_end( 18 )

        bottom_bar.append( self.drop_button )

        toolbar_view.add_bottom_bar( bottom_bar )

        main_scroll = Gtk.ScrolledWindow()

        main_scroll.set_policy( Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC )

        main_scroll.set_vexpand( True )
        main_scroll.set_child( root )

        toolbar_view.set_content( main_scroll )

        self.set_content( toolbar_view )

        self.connect( "close-request", self._on_close_request )

        self._update_destination_mode()

    def _load_channels(self):
        logger.debug( "Starting Buffer channel load" )
        thread = threading.Thread( target=self._load_channels_worker, daemon=True )
        thread.start()

    def _load_channels_worker(self):
        try:
            account = get_account()
            channel_groups = []
            for organization in account.get(
                "organizations",
                [],
            ):
                channels = get_channels( organization["id"] )
                channel_groups.append({
                    "organization": organization,
                    "channels": channels,
                })

            GLib.idle_add( self._populate_channels, account, channel_groups )
        except Exception as exception:
            logger.exception( "Unable to load Buffer channels" )
            GLib.idle_add( self._show_channel_error, str(exception) )

    def _clear_channel_box(self):
        child = self.channel_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.channel_box.remove(child)
            child = next_child

    def _populate_channels( self, account, channel_groups ):
        self.buffer_connected = True
        self.suppress_composer_save = True

        self._clear_channel_box()

        self.organizations = account.get(
            "organizations",
            [],
        )

        self.organization_model.splice( 0, self.organization_model.get_n_items(), [] )

        for organization in self.organizations:
            self.organization_model.append( organization["name"] )
        
        self.organization_dropdown.set_sensitive( bool(self.organizations) )

        self.channel_buttons.clear()

        if self.has_unfinished_composer:
            saved_organization_id = ( self.composer_state[ "organization_id" ] )
        else:
            saved_organization_id = ( self.preferences[ "last_idea_organization_id" ] )

        selected_organization = 0

        for index, organization in enumerate( self.organizations ):
            if ( organization["id"] == saved_organization_id ):
                selected_organization = index
                break

        if self.organizations:
            self.organization_dropdown.set_selected( selected_organization )

        self.channel_buttons.clear()

        if self.has_unfinished_composer:
            saved_channel_ids = set( self.composer_state[ "channel_ids" ] )
        else:
            saved_channel_ids = set( self.preferences[ "last_channel_ids" ] )

        if not channel_groups:
            label = Gtk.Label( label="No Buffer organizations found.", xalign=0)
            self.channel_box.append(label)
            return

        channel_count = 0

        for group in channel_groups:
            organization = group["organization"]
            channels = group["channels"]

            organization_label = Gtk.Label( label=organization["name"], xalign=0 )
            organization_label.add_css_class( "heading" )

            self.channel_box.append( organization_label )

            for channel in channels:
                display_name = ( channel.get("displayName") or channel.get("name") or "Unnamed channel" )

                service = channel.get( "service", "unknown" )

                label = ( f"{display_name} · {service.title()}" )

                unavailable_reason = None

                if channel.get("isDisconnected"):
                    unavailable_reason = ( "Disconnected" )
                elif channel.get("isLocked"):
                    unavailable_reason = "Locked"

                if unavailable_reason:
                    label += ( f" ({unavailable_reason})" )

                button = Gtk.CheckButton( label=label )
                button.set_active( channel["id"] in saved_channel_ids )
                button.connect( "toggled", self._on_channel_toggled )

                if unavailable_reason:
                    button.set_sensitive(False)

                self.channel_box.append(button)

                self.channel_buttons[ channel["id"] ] = {
                    "button": button,
                    "channel": channel,
                    "organization": organization,
                    "available": unavailable_reason is None,
                }

                channel_count += 1

        logger.info( "Loaded %d Buffer channels", channel_count )

        self.status_label.set_text(
            f"{channel_count} Buffer {'channel' if channel_count == 1 else 'channels'}  available."
        )

        self.destinations_loaded = True
        self.suppress_composer_save = False

        self._update_destination_mode()
        self._update_drop_button_state()

    def _show_channel_error( self, message: str ):
        self._clear_channel_box()
        label = Gtk.Label( label="Unable to load Buffer channels.", xalign=0 )
        self.channel_box.append(label)
        self.status_label.set_text(message)

    def _on_action_changed( self, _dropdown, _parameter ):
        selected = self.action_dropdown.get_selected()

        if selected >= len(self.action_keys):
            return

        self.current_action = self.action_keys[ selected ]

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

    def _get_selected_organization( self ) -> dict | None:
        selected = ( self.organization_dropdown.get_selected() )
        
        if selected >= len(self.organizations):
            return None
        
        return self.organizations[selected]


    def _on_organization_changed( self, _dropdown, _parameter ):
        self._update_drop_button_state()
        self._schedule_composer_state_save()

    def _get_composer_text(self) -> str:
        buffer = self.composer.get_buffer()

        start, end = buffer.get_bounds()

        return buffer.get_text( start, end, False )

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
        has_image = ( self.selected_image_path is not None )
        link_url = self._get_link_url()
        has_link = link_url is not None

        has_content = has_text or has_image or has_link

        channels = []

        if self.current_action == "idea":
            has_destination = ( self._get_selected_organization() is not None )
            character_checks = []
        else:
            channels = self._get_selected_channels()
            has_destination = bool(channels)
            character_checks = check_selected_channels( text,   channels )

        link_destinations = (
            []
            if self.current_action == "idea"
            else channels
        )

        link_error = self._link_validation_error(
            self.current_action,
            link_destinations,
            self.selected_image_path,
            link_url,
        )

        self.link_status_label.set_visible(
            link_error is not None
        )

        self.link_status_label.set_text(
            link_error or ""
        )

        summaries = []

        for check in character_checks:
            label = ( f"{check.service.title()} ({check.channel_name})" )

            if check.remaining is not None:
                if check.remaining >= 0:
                    remaining_text = ( f"{check.remaining:,} left" )
                else:
                    remaining_text = ( f"{abs(check.remaining):,} over" )

                if not check.exact:
                    remaining_text += " (estimate)"

                summaries.append( f"{label}: {remaining_text}" )

            elif check.note:
                summaries.append( f"{label}: {check.note}" )

        has_character_errors = any(
            check.over_limit
            for check in character_checks
        )

        if hasattr( self, "character_status_label" ):
            if self.current_action == "idea":
                self.character_status_label.set_visible( False )
            else:
                self.character_status_label.set_visible( bool(summaries) )
               
                if has_character_errors:
                    details = ", ".join(
                        f"{check.channel_name} ({abs(check.remaining):,} over)"
                        for check in character_checks
                        if check.over_limit
                    )

                    self.character_status_label.set_text( f"Character limit exceeded: {details}")
                    self.character_status_label.add_css_class("error")

                else:
                    self.character_status_label.set_text( "\r\n".join(summaries) )
                    self.character_status_label.remove_css_class("error")

        self.drop_button.set_sensitive(
            has_content
            and has_destination
            and not self.is_submitting
            and self.retry_action is None
            and not has_character_errors
            and not link_error
            and not (
                self.current_action == "idea"
                and has_image
            )
        )

    def _set_submitting(self, submitting: bool):
        self.is_submitting = submitting

        self.composer.set_sensitive( not submitting )

        self.action_dropdown.set_sensitive( not submitting )
        self.attach_image_button.set_sensitive( not submitting )
        self.remove_image_button.set_sensitive( not submitting )

        self.organization_dropdown.set_sensitive( bool(self.organizations) and not submitting )

        for entry in self.channel_buttons.values():
            entry["button"].set_sensitive( entry["available"] and not submitting )

        if submitting:
            self.drop_button.set_label( "Dropping..." )
        else:
            self._update_destination_mode()

        self._update_drop_button_state()

    def _on_drop_clicked(self, _button):
        text = self._get_composer_text()

        if self.is_submitting or self.retry_action is not None:
            return

        image_path = self.selected_image_path
        link_url = self._get_link_url()

        if not text.strip() and image_path is None and link_url is None:
            return

        action = self.current_action

        if action == "idea" and image_path is not None:
            return

        if action == "idea":
            organization = self._get_selected_organization()

            if organization is None:
                return

            destinations = [{
                "id": organization["id"],
                "name": organization["name"],
            }]

        else:
            destinations = self._get_selected_channels()

            if not destinations:
                return

        if action != "idea":
            character_checks = check_selected_channels( text, destinations )

            invalid_channels = [
                check
                for check in character_checks
                if check.over_limit
            ]

            if invalid_channels:
                details = ", ".join(
                    f"{check.channel_name} "
                    f"({abs(check.remaining):,} characters over)"
                    for check in invalid_channels
                )

                self.status_label.set_text( f"Post exceeds character limits: {details}" )

                self._update_drop_button_state()
                return

        link_error = self._link_validation_error(
            action,
            destinations,
            image_path,
            link_url,
        )

        if link_error:
            self.status_label.set_text(link_error)
            self._update_drop_button_state()
            return

        destination_count = len(destinations)

        if action == "idea":
            self.status_label.set_text( "Dropping Idea..." )

        elif action == "draft":
            self.status_label.set_text(
                f"Dropping to Draft for {destination_count} "
                f"{'channel' if destination_count == 1 else 'channels'}..."
            )
        else:
            self.status_label.set_text(
                f"Dropping to {destination_count} "
                f"{'channel' if destination_count == 1 else 'channels'}..."
            )

        self._set_submitting(True)

        thread = threading.Thread(
            target=self._drop_posts_worker,
            args=(
                action,
                text,
                destinations,
                None,
                image_path,
                None,
                link_url,
            ),
            daemon=True,
        )

        thread.start()

    def _drop_posts_worker( self, action: str, text: str, destinations: list[dict], all_destinations: list[dict] | None = None,
                        image_path: Path | None = None, image_url: str | None = None, link_url: str | None = None ):

        successes = []
        failures = []

        if all_destinations is None:
            all_destinations = destinations

        if image_path is not None and image_url is None:
            try:
                hosted_image = upload_image( image_path )
                image_url = hosted_image.url
                logger.info( "Image uploaded successfully: media ID %s", hosted_image.media_id )

            except Exception as exception:
                logger.exception( "Unable to upload image before Drop" )

                if isinstance(exception, MediaUploadError):
                    message = str(exception)
                else:
                    message = ( "An unexpected error occurred while uploading the image." )

                failures = [
                    {
                        "destination": destination,
                        "error": message,
                        "retry_after": None,
                        "rate_limited": False,
                    }
                    for destination in destinations
                ]

                GLib.idle_add(
                    self._finish_drop,
                    action,
                    text,
                    all_destinations,
                    [],
                    failures,
                    image_path,
                    None,
                    link_url,
                )

                return

        for index, destination in enumerate( destinations ):
            try:
                if action == "idea":
                    result = create_idea(
                        destination["id"],
                        text
                    )

                elif action == "draft":
                    result = create_draft_post(
                        destination["id"],
                        text,
                        image_url=image_url,
                        link_url=link_url,
                        service=destination.get("service"),
                    )

                else:
                    result = create_queue_post(
                        destination["id"],
                        text,
                        image_url=image_url,
                        link_url=link_url,
                        service=destination.get("service"),
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

            except BufferSubmissionUncertainError as exception:
                logger.warning(
                    "Uncertain Buffer %s submission for %s: %s",
                    action,
                    destination["id"],
                    exception,
                )

                failures.append({
                    "destination": destination,
                    "error": (
                        "Submission status unknown. "
                        "Check Buffer before trying this channel again."
                    ),
                    "retry_after": None,
                    "rate_limited": False,
                    "uncertain": True,
                })

                # These destinations were definitely not attempted.
                # They can be retried safely.
                for remaining in destinations[index + 1:]:
                    failures.append({
                        "destination": remaining,
                        "error": (
                            "Not attempted because a previous "
                            "submission could not be confirmed."
                        ),
                        "retry_after": None,
                        "rate_limited": False,
                        "uncertain": False,
                    })

                break

            except BufferRateLimitError as exception:
                logger.warning( "Buffer rate limit reached" )

                failures.append({
                    "destination": destination,
                    "error": str(exception),
                    "retry_after": exception.retry_after,
                    "rate_limited": True,
                })

                # Don't hammer Buffer with the remaining destinations.
                for remaining in destinations[index + 1:]:
                    failures.append({
                        "destination": remaining,
                        "error": (
                            "Not attempted because Buffer's rate limit was reached."
                        ),
                        "retry_after": exception.retry_after,
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
            image_path,
            image_url,
            link_url,
        )

    def _finish_drop( self, action: str, text: str, destinations: list[dict], successes: list[dict],
                  failures: list[dict], image_path: Path | None = None, image_url: str | None = None,
                  link_url: str | None = None ):

        self._set_submitting(False)

        if self.retry_action is not None:
            failure_ids = {
                failure["destination"]["id"]
                for failure in failures
            }

            for uncertain in self.retry_uncertain:
                channel_id = ( uncertain["destination"]["id"] )

                if channel_id not in failure_ids:
                    failures.append( uncertain )

        if failures:
            self._set_retry_state(
                action,
                text,
                destinations,
                failures,
                image_path,
                image_url,
                link_url,
            )

            return

        self._complete_drop_success(
            action,
            destinations,
        )

    def _remember_successful_action( self, action: str, destinations: list[dict] ):
        self.preferences[ "last_action" ] = action

        if action == "idea":
            self.preferences[ "last_idea_organization_id" ] = destinations[0]["id"]
        else:
            self.preferences[ "last_channel_ids"] = [
                destination["id"] for destination in destinations
            ]

        try:
            save_preferences( self.preferences )
        except OSError:
            logger.exception( "Unable to save PostBop preferences" )

    def _on_composer_changed( self, _buffer ):
        if ( not self.suppress_composer_save and self.retry_action is not None ):
            self._clear_retry_state()
            
        self._update_drop_button_state()
        self._schedule_composer_state_save()

    def _on_channel_toggled( self, _button ):
        self._update_drop_button_state()
        self._schedule_composer_state_save()

    def _schedule_composer_state_save( self ):
        if self.suppress_composer_save:
            return

        if self.composer_save_source_id is not None:
            GLib.source_remove( self.composer_save_source_id )

        self.composer_save_source_id = ( GLib.timeout_add( 500, self._save_composer_state ) )

    def _save_composer_state(self):
        # Called by the GLib debounce timer.
        self.composer_save_source_id = None
        self._persist_composer_state()
        return False # Don't repeat the timer.


    def _save_composer_state_now(self) -> bool:
        # Cancel any pending debounced save because we're about to persist the current state immediately.
        if self.composer_save_source_id is not None:
            GLib.source_remove( self.composer_save_source_id )
            self.composer_save_source_id = None

        return self._persist_composer_state()


    def _persist_composer_state(self) -> bool:
        text = self._get_composer_text()

        has_text = bool(text.strip())
        has_image = self.selected_image_path is not None
        has_link = self._get_link_url() is not None

        if not has_text and not has_image and not has_link:
            try:
                clear_composer_state()
            except OSError:
                logger.exception( "Unable to clear unfinished composer" )
                return False

            self.has_unfinished_composer = False
            self.composer_state["image"] = None

            return True

        if self.destinations_loaded:
            channel_ids = [
                channel["id"]
                for channel in self._get_selected_channels()
            ]

            organization = self._get_selected_organization()

            organization_id = (
                organization["id"]
                if organization is not None
                else None
            )

        else:
            # Preserve recovered destinations until Buffer data has finished loading.
            channel_ids = self.composer_state["channel_ids"]

            organization_id = ( self.composer_state["organization_id"] )

        image_state = None

        if self.selected_image_path is not None:
            image_state = {
                "cached_filename": self.selected_image_path.name,
                "original_filename": (
                    self.selected_image_original_filename
                    or self.selected_image_path.name
                ),
            }

        state = {
            "text": text,
            "action": self.current_action,
            "channel_ids": channel_ids,
            "organization_id": organization_id,
            "image": image_state,
            "link_url": self._get_link_url() or "",
        }

        try:
            save_composer_state(state)
        except OSError:
            logger.exception( "Unable to save unfinished composer" )
            return False

        self.composer_state = state
        self.has_unfinished_composer = True

        return True

    def _on_close_request( self, _window ):
        if self.composer_save_source_id is not None:
            GLib.source_remove( self.composer_save_source_id)
            self.composer_save_source_id = None

        self._save_composer_state()

        return False

    def _set_retry_state( self, action: str, text: str, all_destinations: list[dict], failures: list[dict],
                      image_path: Path | None = None, image_url: str | None = None,
                      link_url: str | None = None ):

        self.retry_action = action
        self.retry_text = text
        self.retry_image_path = image_path
        self.retry_image_url = image_url
        self.retry_link_url = link_url

        self.retry_all_destinations = ( all_destinations.copy() )

        self.retry_failures = [
            failure.copy()
            for failure in failures
        ]

        retry_delays = [
            failure["retry_after"]
            for failure in failures
            if failure.get("retry_after") is not None
        ]

        if retry_delays:
            self.retry_available_at = ( time.monotonic() + max(retry_delays) )
        else:
            self.retry_available_at = None

        self._refresh_retry_display()

    def _refresh_retry_display(self):
        self.retry_uncertain = [
            failure
            for failure in self.retry_failures
            if failure.get("uncertain", False)
        ]

        self.retry_destinations = [
            failure["destination"]
            for failure in self.retry_failures
            if not failure.get("uncertain", False)
        ]

        lines = []

        for failure in self.retry_failures:
            name = failure["destination"]["name"]
            message = failure["error"]

            if failure.get("uncertain", False):
                lines.append( f"{name}: UNKNOWN — {message}" )
            else:
                lines.append( f"{name}: {message}" )

        self.error_label.set_text( "\n".join(lines) )

        has_uncertain = bool( self.retry_uncertain )

        self.resolve_unknown_button.set_visible( has_uncertain )
        self.open_buffer_error_button.set_visible( has_uncertain )
        self.retry_button.set_visible( bool(self.retry_destinations) )
        self.error_revealer.set_reveal_child( bool(self.retry_failures) )

        total = len( self.retry_all_destinations )

        completed = total - len( self.retry_failures )

        if has_uncertain:
            self.status_label.set_text(
                f"Completed {completed} of {total} destinations. "
                f"{len(self.retry_uncertain)} require verification."
            )

        else:
            self.status_label.set_text( f"Completed {completed} of {total} destinations." )

        self._start_retry_timer()
        self._update_drop_button_state()

    def _clear_retry_state(self):
        self.retry_action = None
        self.retry_text = None
        self.retry_destinations = []
        self.retry_all_destinations = []
        self.retry_available_at = None
        self.retry_image_path = None
        self.retry_image_url = None
        self.retry_link_url = None
        self.retry_uncertain = []
        self.retry_failures = []

        self.resolve_unknown_button.set_visible(False)
        self.open_buffer_error_button.set_visible(False)

        if self.retry_timer_source_id is not None:
            GLib.source_remove( self.retry_timer_source_id )
            self.retry_timer_source_id = None

        self.error_revealer.set_reveal_child( False )

        self.retry_button.set_label( "Retry Failed" )

    def _start_retry_timer(self):
        if self.retry_timer_source_id is not None:
            GLib.source_remove( self.retry_timer_source_id )
            self.retry_timer_source_id = None

        if (
            self.retry_available_at is not None
            and self.retry_destinations
        ):
            self.retry_timer_source_id = (
                GLib.timeout_add_seconds( 1, self._update_retry_button )
            )

        self._update_retry_button()

    def _update_retry_button(self):
        can_retry = (
            self.retry_action is not None
            and bool(self.retry_destinations)
            and not self.is_submitting
        )

        if self.retry_available_at is not None:
            remaining = max(
                0, math.ceil( self.retry_available_at - time.monotonic() )
            )

            if remaining > 0:
                self.retry_button.set_label( f"Retry Failed ({remaining}s)" )
                self.retry_button.set_sensitive(False)
                return True

            self.retry_available_at = None

        self.retry_button.set_label( "Retry Failed" )

        self.retry_button.set_sensitive( can_retry )
        self.retry_timer_source_id = None

        return False

    def _on_retry_clicked( self, _button ):
        if ( self.retry_action is None or not self.retry_destinations ):
            return

        if self.retry_available_at is not None:
            return

        action = self.retry_action
        text = self.retry_text

        retry_destinations = ( self.retry_destinations.copy() )
        all_destinations = ( self.retry_all_destinations.copy() )

        self.status_label.set_text( "Retrying failed destinations..." )

        self._set_submitting(True)

        thread = threading.Thread(
            target=self._drop_posts_worker,
            args=(
                action,
                text,
                retry_destinations,
                all_destinations,
                self.retry_image_path,
                self.retry_image_url,
                self.retry_link_url,
            ),
            daemon=True,
        )

        thread.start()

    def _notify_success( self, action: str,  count: int ):
        if action == "idea":
            body = "Idea dropped to Buffer."
        elif action == "draft":
            body = ( f"Dropped to Draft for {count} Buffer {'channel' if count == 1 else 'channels'}." )
        else:
            body = ( f"Dropped to {count} Buffer {'channel' if count == 1 else 'channels'}." )

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
                media_token = result.get( "media_token" )
                error = result.get( "error" )

                if error:
                    raise RuntimeError( str(error) )

                if authorization_code:
                    if ( not isinstance(media_token, str) or not media_token ):
                        raise RuntimeError( "Companion did not return a media credential" )
                    try:
                        tokens = exchange_authorization_code( authorization_code, code_verifier )
                        activate_media_credential( media_token, tokens["access_token"] )
                        store_media_token( media_token )
                    except Exception:
                        clear_tokens()
                        raise

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
        self._save_composer_state()
        self._show_disconnected_state()

    def handle_incoming_text( self, incoming_text: str ):
        if not incoming_text:
            return

        current_text = self._get_composer_text()

        if not current_text.strip():
            self._replace_composer_text( incoming_text )
            return

        dialog = Adw.AlertDialog.new(
            "Composer Already Has Text",
            ( "PostBop already contains unsent content.  Would you like to append the incoming text or replace the current composer?" ),
        )

        dialog.add_response( "cancel", "Cancel" )
        dialog.add_response( "append", "Append" )
        dialog.add_response( "replace", "Replace" )

        dialog.set_default_response( "append" )
        dialog.set_close_response( "cancel" )

        dialog.set_response_appearance( "append", Adw.ResponseAppearance.SUGGESTED )
        dialog.set_response_appearance( "replace", Adw.ResponseAppearance.DESTRUCTIVE )

        dialog.connect( "response", self._on_incoming_text_response, incoming_text )

        dialog.present(self)

    def _on_incoming_text_response( self, _dialog, response: str, incoming_text: str ):
        if response == "replace":
            self._replace_composer_text( incoming_text )
            return

        if response == "append":
            current_text = ( self._get_composer_text() )
            combined_text = ( f"{current_text.rstrip()}\n\n{incoming_text.lstrip()}" )

            self._replace_composer_text( combined_text )

    def _replace_composer_text( self, text: str ):
        buffer = self.composer.get_buffer()
        buffer.set_text( text )
        end = buffer.get_end_iter()
        buffer.place_cursor( end )
        self.composer.grab_focus()

    def drop_current_post(self):
        if not self.drop_button.get_sensitive():
            return
        self._on_drop_clicked( self.drop_button )

    def _on_attach_image_clicked( self, _button ):
        dialog = Gtk.FileDialog()

        dialog.set_title( "Select an Image" )

        image_filter = Gtk.FileFilter()
        image_filter.set_name( "Supported Images" )

        image_filter.add_mime_type( "image/jpeg" )
        image_filter.add_mime_type( "image/png" )
        image_filter.add_mime_type( "image/webp" )

        filters = Gio.ListStore.new( Gtk.FileFilter )

        filters.append( image_filter )

        dialog.set_filters( filters )

        dialog.set_default_filter( image_filter )

        dialog.open( self, None, self._on_image_file_selected )

    def _on_image_file_selected( self, dialog, result ):
        try:
            file = dialog.open_finish( result )            
        except GLib.Error:
            # The user canceled the file picker.
            return

        path = file.get_path()

        if path is None:
            self.status_label.set_text( "Please select a local image file." )
            return

        self._attach_image_from_path( Path(path) )

    def _on_remove_image_clicked(self, _button):
        if self.is_submitting:
            return

        previous_image = self.selected_image_path
        previous_filename = ( self.selected_image_original_filename )

        if previous_image is None:
            return

        # Temporarily remove the attachment from the in-memory composer state.
        self.selected_image_path = None
        self.selected_image_original_filename = None

        if not self._save_composer_state_now():
            self.selected_image_path = previous_image
            self.selected_image_original_filename = ( previous_filename )
            self.status_label.set_text( "Unable to save the attachment removal. Your image was preserved." )
            return

        if self.retry_action is not None:
            self._clear_retry_state()

        try:
            delete_cached_image(previous_image)
        except (OSError, ValueError):
            logger.exception( "Unable to remove cached image" )

        self.image_preview.set_paintable(None)
        self.image_filename_label.set_text("")
        self.image_preview_box.set_visible(False)

        self.attach_image_button.set_label( "Attach Image" )

        self._update_drop_button_state()

    def _restore_cached_image( self ):
        image_state = self.composer_state.get( "image" )
        if image_state is None:
            return

        cached_path = get_cached_image( image_state["cached_filename"] )

        if cached_path is None:
            logger.warning( "Previously cached image is missing" )
            self.composer_state["image"] = None
            self._schedule_composer_state_save()
            return

        file = Gio.File.new_for_path( str(cached_path) )

        try:
            texture = Gdk.Texture.new_from_file( file )

        except GLib.Error:
            logger.exception( "Unable to restore cached image" )
            self.composer_state["image"] = None
            self._schedule_composer_state_save()
            return

        self.selected_image_path = cached_path
        self.selected_image_original_filename = ( image_state["original_filename"] )
        self.image_preview.set_paintable( texture )
        self.image_filename_label.set_text( self.selected_image_original_filename )
        self.image_preview_box.set_visible( True )
        self.attach_image_button.set_label( "Change Image" )
        self._update_drop_button_state()

        logger.info( "Restored cached image attachment" )

    def _attach_image_from_path( self, image_path: Path ) -> bool:
        if self.is_submitting:
            return False

        try:
            cached_path = cache_image(image_path)
        except (OSError, ValueError) as exception:
            logger.warning( "Unable to attach image: %s", exception )
            self.status_label.set_text( str(exception) )
            return False

        file = Gio.File.new_for_path( str(cached_path) )

        try:
            texture = Gdk.Texture.new_from_file(file)
        except GLib.Error:
            logger.exception( "Unable to preview cached image" )

            try:
                delete_cached_image(cached_path)
            except (OSError, ValueError):
                logger.exception( "Unable to clean up invalid cached image" )

            self.status_label.set_text( "Unable to preview the selected image." )

            return False

        previous_image = self.selected_image_path

        previous_filename = ( self.selected_image_original_filename)

        self.selected_image_path = cached_path
        self.selected_image_original_filename = ( image_path.name )

        if not self._save_composer_state_now():
            # Saving failed. Restore the previous selection and leave its cached file untouched.
            self.selected_image_path = previous_image
            self.selected_image_original_filename = ( previous_filename )

            try:
                delete_cached_image(cached_path)
            except (OSError, ValueError):
                logger.exception( "Unable to clean up unsaved image" )

            self.status_label.set_text( "Unable to save the image attachment. Your previous attachment was preserved." )

            return False

        if self.retry_action is not None:
            self._clear_retry_state()

        self.image_preview.set_paintable(texture)
        self.image_filename_label.set_text( image_path.name )
        self.image_preview_box.set_visible(True)

        self.attach_image_button.set_label( "Change Image" )

        self.status_label.set_text( "Image attached." )

        self._update_drop_button_state()

        # Only delete the previous cached image after the new image state has been saved.
        if previous_image is not None:
            try:
                delete_cached_image(previous_image)
            except (OSError, ValueError):
                logger.exception( "Unable to remove previous cached image" )

        return True

    def _on_image_dropped( self, _target, value, _x, _y ) -> bool:
        if self.is_submitting:
            return False

        if not isinstance( value, Gdk.FileList ):
            return False

        files = value.get_files()

        if not files:
            return False

        if len(files) != 1:
            self.status_label.set_text( "Please drop only one image." )
            return True

        file = files[0]

        path = file.get_path()

        if path is None:
            self.status_label.set_text( "Please drop a local image file." )

            return True

        return self._attach_image_from_path( Path(path) )

    def _on_open_buffer_for_verification( self, _button ):
        try:
            Gio.AppInfo.launch_default_for_uri( "https://publish.buffer.com", None )
        except GLib.Error:
            logger.exception( "Unable to open Buffer" )
            self.status_label.set_text( "Unable to open Buffer in the browser." )

    def _on_resolve_unknown_clicked( self, _button ):
        if (
            self.is_submitting
            or not self.retry_uncertain
        ):
            return

        failure = self.retry_uncertain[0]
        destination = failure["destination"]

        dialog = Adw.AlertDialog.new(
            "Resolve Unknown Submission",
            (
                f"PostBop could not confirm whether Buffer "
                f"created the post for {destination['name']}.\n\n"
                "Check the appropriate channel in Buffer "
                "before choosing an action.\n\n"
                "Found the post: mark this destination complete.\n"
                "Post not found: allow another attempt, "
                "understanding that a duplicate is still possible."
            ),
        )

        dialog.add_response( "cancel", "Cancel" )
        dialog.add_response( "posted", "Mark as Posted" )
        dialog.add_response( "retry", "Allow Retry" )

        dialog.set_default_response( "cancel" )
        dialog.set_close_response( "cancel" )

        dialog.set_response_appearance( "retry", Adw.ResponseAppearance.DESTRUCTIVE )

        dialog.connect( "response", self._on_uncertain_resolution, destination["id"] )

        dialog.present(self)

    def _on_uncertain_resolution( self, _dialog, response: str, channel_id: str ):
        if response == "cancel":
            return

        if (
            self.is_submitting
            or self.retry_action is None
        ):
            return

        failure = next(
            (
                item
                for item in self.retry_failures
                if (
                    item.get("uncertain", False)
                    and item["destination"]["id"]
                    == channel_id
                )
            ),
            None,
        )

        if failure is None:
            return

        if response == "posted":
            # The user verified the post in Buffer. There is nothing to resubmit.
            self.retry_failures.remove( failure )

        elif response == "retry":
            # The user explicitly authorized another attempt.
            failure["uncertain"] = False
            failure["rate_limited"] = False
            failure["retry_after"] = None

            failure["error"] = ( "Manually cleared for retry. A duplicate remains possible." )

        else:
            return

        if not self.retry_failures:
            # Every destination is now confirmed or manually verified.
            self._complete_drop_success(
                self.retry_action,
                self.retry_all_destinations,
            )

            return

        self._refresh_retry_display()

    def _complete_drop_success( self, action: str, destinations: list[dict] ):
        total = len(destinations)

        self._clear_retry_state()
        self._remember_successful_action( action, destinations )

        buffer = self.composer.get_buffer()

        self.suppress_composer_save = True

        buffer.set_text("")
        self.link_entry.set_text("")

        if self.selected_image_path is not None:
            try:
                delete_cached_image( self.selected_image_path )

            except (OSError, ValueError):
                logger.exception( "Unable to clean up cached image after successful Drop" )

            self.selected_image_path = None
            self.selected_image_original_filename = None

            self.image_preview.set_paintable(None)
            self.image_filename_label.set_text("")
            self.image_preview_box.set_visible(False)

            self.attach_image_button.set_label( "Attach Image" )

        self.suppress_composer_save = False

        clear_composer_state()

        self.composer_state = {
            "text": "",
            "action": "queue",
            "channel_ids": [],
            "organization_id": None,
            "image": None,
            "link_url": "",
        }

        self.has_unfinished_composer = False

        if action == "idea":
            self.status_label.set_text( "Idea dropped to Buffer." )

        elif action == "draft":
            self.status_label.set_text(
                f"Dropped to Draft for {total} Buffer {'channel' if total == 1 else 'channels'}."
            )

        else:
            self.status_label.set_text(
                f"Dropped to {total} Buffer {'channel' if total == 1 else 'channels'}."
            )

        self._update_drop_button_state()

        self._notify_success( action, total )

        if not self.preferences["keep_open_after_success"]:
            application = self.get_application()

            if application is not None:
                application.remain_alive_for_notification( 5 )

            self.close()
            return

        self.composer.grab_focus()

    def _get_link_url(self) -> str | None:
        url = self.link_entry.get_text().strip()
        return url or None


    def _on_link_changed(self, _entry):
        if self.suppress_composer_save:
            return

        self._schedule_composer_state_save()
        self._update_drop_button_state()

    def _link_validation_error( self, action: str, destinations: list[dict], 
                               image_path: Path | None, link_url: str | None, ) -> str | None:
        if not link_url:
            return None

        if image_path is not None:
            return ( "Remove the image before attaching a link." )

        if action == "idea":
            return ( "Link attachments are available for Queue and Draft only." )

        for destination in destinations:
            try:
                _build_link_metadata( link_url, destination.get("service") )

            except ValueError as exception:
                return ( f"{destination['name']}: {exception}" )

        return None