from gi.repository import GObject, RB, Peas, Gio,\
    Gtk, PeasGtk, WebKit
from urllib.parse import parse_qs
from urllib.request import urlopen

from utils import asynchronous_call

import rb
import json
import sys
import vk

SCHEMA_ID = "org.gnome.rhythmbox.plugins.myvk"

def create_settings(data_dir):
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        data_dir,
        Gio.SettingsSchemaSource.get_default(), False,)
    schema = schema_source.lookup(SCHEMA_ID, False)
    return Gio.Settings.new_full(schema, None, None)

class MyVKPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(MyVKPlugin, self).__init__()
        GObject.Object.__init__(self)

    def do_activate(self):
        print("Activating plugin.")
        self.settings = create_settings(self.plugin_info.get_data_dir())

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

        self.entry_view = self.get_entry_view()
        self.entry_view.set_sorting_order("Track", Gtk.SortType.ASCENDING)

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

        asynchronous_call(self.download_audios, self.on_audios_downloaded)()
        

    def download_audios(self):
        url = ("https://api.vk.com/method/audio.get.json?access_token={0}&owner_id={1}"
            .format(self.access_token, self.user_id))
        request = urlopen(url)
        encoding = request.headers.get_content_charset()
        document = json.loads(request.read().decode(encoding))
        response = document['response']
        return response

    def on_audios_downloaded(self, result):
        audios = result[1:]
        for i, audio in enumerate(audios):
            audio['track_number'] = i + 1
            self.add_entry(audio)
        self.db.commit()
        # self.props.query_model.set_sort_order(
        #     RB.RhythmDBQueryModel.track_sort_func, None, False)

    def show_warning(self, err_code=-1, err_msg=""):
        dialog = Gtk.Dialog(buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK))
        label = Gtk.Label("Incorrect vk.com access token\n"
                          "Please reconfigure your plugin.")
        dialog.vbox.pack_start(label, expand=False, fill=False, padding=0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def add_entry(self, audio):
        audio_id = (
            audio['artist'] + audio['title'] + str(audio['duration'])).lower()
        if audio_id in self.audio_ids:
            return

        self.audio_ids[audio_id] = True
        try:
            entry = self.db.entry_lookup_by_location(audio['url'])
            if entry is not None:
                return
            entry = RB.RhythmDBEntry.new(
                self.db, self.props.entry_type, audio['url'])
            if entry is not None:
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.TRACK_NUMBER,
                    audio['track_number'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.TITLE, audio['title'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.DURATION, audio['duration'])
                self.db.entry_set(
                    entry, RB.RhythmDBPropType.ARTIST, audio['artist'])
        except Exception as e:  # This happens on duplicate uris being added
            sys.excepthook(*sys.exc_info())
            print("Couldn't add %s - %s" %
                  (audio['artist'], audio['title']), e)

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
        self.settings = create_settings(self.plugin_info.get_data_dir())
        self.ui = Gtk.Builder()
        self.ui.add_from_file(rb.find_plugin_file(self, 'myvk-prefs.ui'))
        self.config_dialog = self.ui.get_object('config')

        self.username = self.ui.get_object("username_entry")
        self.username.set_text(self.settings['username'])

        self.password = self.ui.get_object("password_entry")
        self.password.set_visibility(False)
        self.password.set_text(self.settings['password'])

        self.username.connect('changed', self.username_changed_cb)
        self.password.connect('changed', self.password_changed_cb)


        self.authorize_button = self.ui.get_object("authorize_button")
        self.authorize_button.connect('clicked', asynchronous_call(self.do_authorize, self.on_authorized))

        self.progress_label = self.ui.get_object("progress_label")

        return self.config_dialog

    def username_changed_cb(self, widget):
        self.settings['username'] = self.username.get_text()

    def password_changed_cb(self, widget):
        self.settings['password'] = self.password.get_text()

    def do_authorize(self, arg):
        self.progress_label.set_text("Please wait...")
        session = vk.AuthSession(app_id=self.settings['app-id'], 
            user_login=self.settings['username'],
            user_password=self.settings['password'],
            scope="audio,offline")
        api = vk.API(session)
        response = api.users.get()[0]
        self.settings.set_string('user-id', str(response['uid']))
        self.settings.set_string('access-token', session.get_access_token())


        
    def on_authorized(self, callback_result):
        self.progress_label.set_text("Done!")


GObject.type_register(VKSource)
