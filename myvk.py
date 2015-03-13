from gi.repository import GObject, RB, Peas, Gio, Gtk, PeasGtk, WebKit
from urllib.parse import parse_qs

SCHEMA_ID = "org.gnome.rhythmbox.plugins.myvk"


class MyVKPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(MyVKPlugin, self).__init__()
        GObject.Object.__init__(self)

    def do_activate(self):
        print("Activating plugin.")
        schema_source = Gio.SettingsSchemaSource.new_from_directory(
            self.plugin_info.get_data_dir(),
            Gio.SettingsSchemaSource.get_default(), False,)
        schema = schema_source.lookup(SCHEMA_ID, False)
        self.settings = Gio.Settings.new_full(schema, None, None)

        shell = self.object
        db = shell.props.db
        entry_type = VKEntryType()
        db.register_entry_type(entry_type)

        iconfile = Gio.File.new_for_path(
            self.plugin_info.get_data_dir() + "/logo.svg")

        self.source = GObject.new(VKSource, shell=shell,
                                  name=_("VK Music"),
                                  entry_type=entry_type,
                                  icon=Gio.FileIcon.new(iconfile))
        # self.source.setup(db, self.settings)
        shell.register_entry_type_for_source(self.source, entry_type)

        group = RB.DisplayPageGroup.get_by_id("library")
        shell.append_display_page(self.source, group)

    def do_deactivate(self):
        print("Deactivating plugin.")
        self.source.delete_thyself()
        self.source = None
        self.settings = None
        self.entry_type = None


class VKEntryType(RB.RhythmDBEntryType):

    def __init__(self):
        RB.RhythmDBEntryType.__init__(self, name='vk-entry-type')


class VKSource(RB.BrowserSource):

    def __init__(self):
        super(VKSource, self).__init__()
        RB.BrowserSource.__init__(self)


class VKRhythmboxConfig(GObject.Object, PeasGtk.Configurable):
    object = GObject.property(type=GObject.GObject)

    def __init__(self):
        GObject.GObject.__init__(self)

    def do_create_configure_widget(self):
        schema_source = Gio.SettingsSchemaSource.new_from_directory(
            self.plugin_info.get_data_dir(),
            Gio.SettingsSchemaSource.get_default(), False,)
        schema = schema_source.lookup(SCHEMA_ID, False)
        self.settings = Gio.Settings.new_full(schema, None, None)
        self.app_id = self.settings.get_string('app-id')

        grid = Gtk.Grid()
        webview = WebKit.WebView()
        oauth_url = (
            "https://oauth.vk.com/oauth/authorize?client_id={0}"
            "&scope=audio,offline&display=popup"
            "&redirect_uri=http://oauth.vk.com/blank.html"
            "&response_type=token".format(self.app_id))
        webview.load_uri(oauth_url)

        def on_uri_changed(webview, prop, grid):
            url = webview.get_property(prop.name)
            params = parse_qs(url)
            if 'access_token' in params:
                self.settings.set_string(
                    'access_token', params["access_token"])
        webview.connect("notify::uri", on_uri_changed, grid)
        grid.attach(webview, 0, 0, 1, 1)
        return grid


GObject.type_register(VKSource)
