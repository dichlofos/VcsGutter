import sublime
import sublime_plugin

try:
    from .view_collection import ViewCollection
except ValueError:
    from view_collection import ViewCollection


class VcsGutterEvents(sublime_plugin.EventListener):
    def __init__(self):
        self.load_settings()

    def on_modified(self, view):
        if not self.live_mode:
            return None

        ViewCollection.add(view)

    def on_clone(self, view):
        ViewCollection.add(view)

    def on_post_save(self, view):
        ViewCollection.add(view)

    def on_load(self, view):
        if not self.live_mode:
            ViewCollection.add(view)

    def on_activated(self, view):
        ViewCollection.add(view)

    def load_settings(self):
        self.settings = sublime.load_settings('VcsGutter.sublime-settings')

        self.live_mode = self.settings.get('live_mode', False)
