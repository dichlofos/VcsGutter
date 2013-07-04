import sublime
import sublime_plugin

try:
    from .view_collection import ViewCollection
except ValueError:
    from view_collection import ViewCollection


def plugin_loaded():
    global _live_mode
    settings = sublime.load_settings('VcsGutter.sublime-settings')
    _live_mode = settings.get('live_mode')

_live_mode = True


class VcsGutterEvents(sublime_plugin.EventListener):
    def __init__(self):
        self.load_settings()

    def on_modified(self, view):
        if not _live_mode:
            return None

        ViewCollection.add(view)

    def on_clone(self, view):
        ViewCollection.add(view)

    def on_post_save(self, view):
        ViewCollection.add(view)

    def on_load(self, view):
        if not _live_mode:
            ViewCollection.add(view)

    def on_activated(self, view):
        if not _live_mode:
            return None

        ViewCollection.add(view)

    def load_settings(self):
        # This works in ST 2 as the API is active when the plugin is loading.
        # For ST 3, the API is active only when the module function plugin_loaded is
        # called. We can tell the difference by testing the returned setting value
        # for None.
        settings = sublime.load_settings('VcsGutter.sublime-settings')
        result = settings.get('live_mode')
        global _live_mode
        if result is None:
            # We're running under ST 3. Set a default here. Actual setting will be
            # read in plugin_loaded() above.
            _live_mode = True
        else:
            _live_mode = result
