import gi
import logging

gi.require_version("Adw", "1")
gi.require_version("Notify", "0.7")

from gi.repository import Adw, Gio, GLib, Notify

from .services.logging import configure_logging
from .window import PostBopWindow

logger = logging.getLogger("postbop.application")

class PostBopApplication(Adw.Application):
    def __init__(self):
        configure_logging()

        super().__init__( application_id="co._10t.PostBop", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE )
        GLib.set_application_name("PostBop")

        if not Notify.init("PostBop"):
            logger.warning( "Unable to initialize desktop notifications" )

        logger.info("PostBop application initialized")

    def do_activate(self):
        logger.debug( "Application activated" )

        window = self.get_active_window()

        if window is None:
            logger.debug( "Creating main window" )
            window = PostBopWindow( application=self )
        else:
            logger.debug( "Presenting existing main window" )

        window.present()

    def do_startup( self ):
        Adw.Application.do_startup( self )

        open_buffer_action = Gio.SimpleAction.new( "open-buffer", None )
        open_buffer_action.connect( "activate", self._on_open_buffer )
        self.add_action( open_buffer_action )

        settings_action = Gio.SimpleAction.new( "settings", None )
        settings_action.connect( "activate", self._on_settings )
        self.add_action( settings_action )

        drop_action = Gio.SimpleAction.new( "drop", None )
        drop_action.connect( "activate", self._on_drop )
        self.add_action( drop_action )

        self.set_accels_for_action( "app.drop", [ "<Primary>Return", "<Primary>KP_Enter" ] )
        self.set_accels_for_action( "app.settings", [ "<Primary>comma" ], )

    def _on_open_buffer( self, _action, _parameter ):
        try:
            Gio.AppInfo.launch_default_for_uri( "https://publish.buffer.com/", None )
        except GLib.Error:
            logger.exception( "Unable to open Buffer" )

    def _on_settings( self, _action, _parameter ):
        window = self.get_active_window()
        if window is None:
            return
        window.show_settings()

    def send_drop_success_notification( self, body: str ) -> None:
        notification = Notify.Notification.new( "PostBop", body, None, )
        notification.set_urgency( Notify.Urgency.NORMAL )
        notification.set_timeout( 5000 )

        try:
            notification.show()
        except Exception:
            logger.exception( "Unable to display desktop notification" )

    def remain_alive_for_notification( self, seconds: int = 5 ) -> None:
        self.hold()
        GLib.timeout_add_seconds( seconds, self._release_notification_hold )


    def _release_notification_hold( self ) -> bool:
        self.release()
        return False

    def do_command_line( self, command_line ):
        arguments = command_line.get_arguments()

        incoming_text = " ".join( arguments[1:] ).strip()

        self.activate()
        window = self.get_active_window()

        if window is not None and incoming_text:
            window.handle_incoming_text( incoming_text )

        return 0

    def _on_drop( self, _action, _parameter ):
        window = self.get_active_window()
        if window is None:
            return
        window.drop_current_post()