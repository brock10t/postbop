import gi

gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

class PostBopWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("PostBop")
        self.set_default_size(440, 300)

        label = Gtk.Label(label="PostBop")
        self.set_content(label)