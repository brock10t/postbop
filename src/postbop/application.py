import gi

gi.require_version("Adw", "1")

from gi.repository import Adw, GLib

from .window import PostBopWindow

class PostBopApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="co._10t.PostBop"
        )

        GLib.set_application_name("PostBop")

    def do_activate(self):
        window = self.get_active_window()

        if window is None:
            window = PostBopWindow(application=self)

        window.present()