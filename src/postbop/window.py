import gi
import logging

gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

logger = logging.getLogger("postbop.window")

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logger.debug("Initializing PostBop window")

        self.set_title("PostBop")
        self.set_default_size(440, 300)

        label = Gtk.Label(label="PostBop")
        self.set_content(label)