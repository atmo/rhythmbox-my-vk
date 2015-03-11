from gi.repository import GObject, RB, Peas, Gio


class MyVKPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(MyVKPlugin, self).__init__()

    def do_activate(self):
        print("Plugin activated.")

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
        shell.register_entry_type_for_source(self.source, entry_type)

        group = RB.DisplayPageGroup.get_by_id("library")
        shell.append_display_page(self.source, group)

    def do_deactivate(self):
        self.source.delete_thyself()
        self.source = None
        self.settings = None
        self.entry_type = None
        print("Plugin deactivated.")


class VKEntryType(RB.RhythmDBEntryType):

    def __init__(self):
        RB.RhythmDBEntryType.__init__(self, name='vk-entry-type')


class VKSource(RB.BrowserSource):

    def __init__(self):
        super(VKSource, self).__init__()
        RB.BrowserSource.__init__(self)


GObject.type_register(VKSource)
