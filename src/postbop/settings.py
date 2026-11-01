import gi
import logging

gi.require_version("Adw", "1")

from gi.repository import Adw
from .storage.preferences import save_preferences

logger = logging.getLogger("postbop.settings")

class PostBopSettingsDialog(Adw.PreferencesDialog):
    def __init__( self, preferences: dict, **kwargs ):
        super().__init__( **kwargs )

        self.preferences = preferences

        self.set_title( "PostBop Settings" )
        self.set_search_enabled( False )

        page = Adw.PreferencesPage()
        page.set_title( "General" )
        page.set_icon_name( "preferences-system-symbolic" )

        general_group = Adw.PreferencesGroup()
        general_group.set_title( "Behavior" )

        self.keep_open_row = Adw.SwitchRow()
        self.keep_open_row.set_title( "Keep PostBop open after a successful Drop" )
        self.keep_open_row.set_subtitle( "Leave the composer window open instead of closing after success." )

        self.keep_open_row.set_active( self.preferences[ "keep_open_after_success" ] )

        self.keep_open_row.connect( "notify::active", self._on_keep_open_changed )

        general_group.add( self.keep_open_row )

        page.add( general_group )

        self.add( page )

    def _on_keep_open_changed(
        self,
        _row,
        _parameter,
    ):
        self.preferences[
            "keep_open_after_success"
        ] = self.keep_open_row.get_active()

        try:
            save_preferences(
                self.preferences
            )

        except OSError:
            logger.exception(
                "Unable to save PostBop settings"
            )