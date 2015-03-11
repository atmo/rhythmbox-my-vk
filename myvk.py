from gi.repository import GObject, RB, Peas


class MyVKPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(MyVKPlugin, self).__init__()

    def do_activate(self):
        print("Plugin activated.")

    def do_deactivate(self):
        print("Deactivating...")
