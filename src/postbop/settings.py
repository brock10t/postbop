import gi
import logging

from collections.abc import Callable

gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from .storage.credentials import clear_tokens
from .storage.preferences import save_preferences

logger = logging.getLogger("postbop.settings")

class PostBopSettingsDialog(Adw.PreferencesDialog):
    def __init__( self, preferences: dict, on_disconnect: Callable[[], None] | None = None, **kwargs ):
        super().__init__( **kwargs )

        self.preferences = preferences
        self.on_disconnect = on_disconnect

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

        account_group = Adw.PreferencesGroup()
        account_group.set_title("Buffer Account")

        disconnect_row = Adw.ActionRow()
        disconnect_row.set_title( "Disconnect Buffer Account" )
        disconnect_row.set_subtitle( "Remove the saved Buffer account from PostBop." )

        disconnect_button = Gtk.Button( label="Disconnect" )
        disconnect_button.add_css_class( "destructive-action" )
        disconnect_button.set_valign( Gtk.Align.CENTER )

        disconnect_button.connect( "clicked", self._on_disconnect_clicked )
        
        disconnect_row.add_suffix( disconnect_button )

        account_group.add( disconnect_row )

        page.add( general_group )
        page.add( account_group )

        self.add( page )

    def _on_keep_open_changed( self, _row, _parameter ):
        self.preferences[ "keep_open_after_success" ] = self.keep_open_row.get_active()

        try:
            save_preferences( self.preferences )

        except OSError:
            logger.exception( "Unable to save PostBop settings" )

    def _on_disconnect_clicked( self, _button ):
        dialog = Adw.AlertDialog.new( "Disconnect Buffer Account? ",
            (
                "This removes the saved Buffer credentials "
                "from PostBop. You can reconnect afterward "
                "and choose a different Buffer account.\n\n"
                "This does not revoke PostBop's authorization "
                "from your Buffer account."
            ),
        )
        dialog.add_response( "cancel", "Cancel" )
        dialog.add_response( "disconnect", "Disconnect" )
        
        dialog.set_default_response( "cancel" )
        dialog.set_close_response( "cancel" )

        dialog.set_response_appearance( "disconnect", Adw.ResponseAppearance.DESTRUCTIVE )

        dialog.connect( "response", self._on_disconnect_response )

        dialog.present( self )

    def _on_disconnect_response( self, _dialog, response:str ):
        if response != "disconnect":
            return

        try:
            clear_tokens()
        except Exception:
            logger.exception( "Unable to clear Buffer credentials" )
            self.add_toast( Adw.Toast.new( "Unable to disconnect Buffer account." ) )
            return

        logger.info( "Buffer credentials removed" )
        if self.on_disconnect is not None:
            self.on_disconnect()

        self.close()