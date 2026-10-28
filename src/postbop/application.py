import gi
import logging

gi.require_version("Adw", "1")

from gi.repository import Adw, GLib

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