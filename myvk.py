from gi.repository import GObject, RB, Peas, Gio,\
    Gtk, PeasGtk, GdkPixbuf, WebKit
from urllib.parse import parse_qs
from urllib.request import urlopen
import json

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
                                  name="VK Music",
                                  entry_type=entry_type,
                                  icon=Gio.FileIcon.new(iconfile))
        self.source.setup(db, self.settings)
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
        self.audio_ids = {}

    def on_access_token_changed(self, settings, key):
        self.access_token = settings.get_string(key)
        self.check_token()

    def on_app_id_changed(self, settings, key):
        self.app_id = settings.get_string(key)

    def on_user_id_changed(self, settings, key):
        self.user_id = settings.get_string(key)

    def setup(self, db, settings):
        self.initialised = False
        self.configured = False

        self.db = db
        self.settings = settings
        self.access_token = self.settings.get_string('access-token')
        self.app_id = self.settings.get_string('app-id')
        self.user_id = self.settings.get_string('user-id')

        self.settings.connect(
            "changed::access-token", self.on_access_token_changed)
        self.settings.connect("changed::app-id", self.on_app_id_changed)
        self.settings.connect("changed::user-id", self.on_user_id_changed)

        search_line = Gtk.HBox()
        refresh_button = Gtk.Button("Refresh")
        refresh_button.connect("clicked", self.refresh_button_clicked)
        search_line.pack_start(
            refresh_button, expand=False, fill=True, padding=2)

        search_line.show_all()
        self.get_children()[0].get_children()[1].get_children()[1].hide()
        self.get_children()[0].get_children()[1].attach_next_to(
            search_line, self.get_children()[
                0].get_children()[1].get_children()[0],
            Gtk.PositionType.LEFT, 3, 1)

    def refresh_button_clicked(self, buttont):
        if not self.configured:
            self.show_warning()
            return

        url = ("https://api.vk.com/method/audio.get.json?"
              "access_token={0}&owner_id={1}"
              .format(self.access_token, self.user_id))
        request = urlopen(url)   
        encoding = request.headers.get_content_charset()
        document = json.loads(request.read().decode(encoding))  
        response = document['response']
        audios = response[1:]
        for i, audio in enumerate(audios[:2]):
            audio['track_number'] = i+1
            self.add_entry(audio)


    def show_warning(self, err_code=-1, err_msg=""):
        dialog = Gtk.Dialog(buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK))
        label = Gtk.Label("Incorrect vk.com access token\n"
                          "Please reconfigure your plugin.")
        dialog.vbox.pack_start(label, expand=False, fill=False, padding=0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def add_entry(self, audio):
        audio_id = (audio['artist'] + audio['title'] + str(audio['duration'])).lower()
        if audio_id in self.audio_ids:
            return

        self.audio_ids[audio_id] = True
        try:
            entry = self.db.entry_lookup_by_location(audio['url'])
            if entry is not None:
                return
            entry = RB.RhythmDBEntry.new(self.db, self.props.entry_type, audio['url'])
            
            self.db.commit()
            if entry is not None:
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.TRACK_NUMBER, audio['track_number'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.TITLE, audio['title'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.DURATION, audio['duration'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.ARTIST, audio['artist'])
            self.db.commit()
        except Exception as e:  # This happens on duplicate uris being added
            sys.excepthook(*sys.exc_info())
            print("Couldn't add %s - %s" % (audio['artist'], audio['title']), e)

    def do_selected(self):
        if not self.initialised:
            self.initialised = True
            self.check_token()

    def check_token(self):
        self.configured = False
        if (len(self.access_token) == 0):
            return
        url = ("https://api.vk.com/method/users.isAppUser.json?"
               "access_token={0}".format(self.access_token))
        request = urlopen(url)        
        encoding = request.headers.get_content_charset()
        document = json.loads(request.read().decode(encoding))
        response = document.get("response")
        if not response or len(response) == 0 \
                or response != "1":
            error = document["error"]
            print(error)
            return
        self.configured = True
        return


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
            if 'access_token' in url:
                args = url.split("#", 1)[1]
                params = parse_qs(args)
                self.settings.set_string(
                    'access-token', params["access_token"][0])
                self.settings.set_string(
                    'user-id', params["user_id"][0])
        webview.connect("notify::uri", on_uri_changed, grid)
        grid.attach(webview, 0, 0, 1, 1)
        return grid


GObject.type_register(VKSource)
