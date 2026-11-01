import gi
import logging

gi.require_version("Adw", "1")
gi.require_version("Notify", "0.7")

from gi.repository import Adw, GLib, Notify

from .services.logging import configure_logging
from .window import PostBopWindow

logger = logging.getLogger("postbop.application")

class PostBopApplication(Adw.Application):
    def __init__(self):
        configure_logging()

        super().__init__(
            application_id="co._10t.PostBop"
        )

        GLib.set_application_name("PostBop")

        if not Notify.init("PostBop"):
            logger.warning(
                "Unable to initialize desktop notifications"
            )

        logger.info("PostBop application initialized")

    def do_activate(self):
        logger.debug("Application activated")

        window = self.get_active_window()

        if window is None:
            logger.debug("Creating main window")
            window = PostBopWindow(application=self)
        else:
            logger.debug("Presenting existing main window")

        window.present()

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