import os
import sublime
import subprocess
import re

try:
    from . import vcs_helpers
except ValueError:
    import vcs_helpers

try:
    from .view_collection import ViewCollection
except ValueError:
    from view_collection import ViewCollection


class VcsGutterHandler(object):
    def __init__(self, view, exc_path):
        self.view = view
        self.exc_path = exc_path
        self.vcs_temp_file = ViewCollection.vcs_tmp_file(self.view)
        self.buf_temp_file = ViewCollection.buf_tmp_file(self.view)

        vcs_helper = self.get_vcs_helper()
        if self.on_disk():
            self.vcs_tree = vcs_helper.vcs_tree(self.view)
            self.vcs_dir = vcs_helper.vcs_dir(self.vcs_tree)
            self.vcs_path = vcs_helper.vcs_file_path(self.view, self.vcs_tree)

    def on_disk(self):
        # if the view is saved to disk
        return self.view.file_name() is not None

    def get_vcs_path(self):
        return self.vcs_path

    def reset(self):
        if self.on_disk() and self.vcs_path and self.view.window() is not None:
            self.view.window().run_command('vcs_gutter')

    def _get_view_encoding(self):
        # get encoding and clean it for python ex: "Western (ISO 8859-1)"
        # original author for this fix : https://github.com/maelnor/
        pattern = re.compile(r'.+\((.*)\)')
        encoding = self.view.encoding()
        if pattern.match(encoding):
            encoding = pattern.sub(r'\1', encoding)

        encoding = encoding.replace('with BOM', '')
        encoding = encoding.replace('Windows', 'cp')
        encoding = encoding.replace('-', '_')
        encoding = encoding.replace(' ', '')
        return encoding

    def update_buf_file(self):
        chars = self.view.size()
        region = sublime.Region(0, chars)

        # Try conversion
        try:
            contents = self.view.substr(region).encode(self._get_view_encoding())
        except UnicodeError:
            # Fallback to utf8-encoding
            contents = self.view.substr(region).encode('utf-8')

        contents = contents.replace(b'\r\n', b'\n')
        f = open(self.buf_temp_file.name, 'wb')
        f.write(contents)
        f.close()

    def total_lines(self):
        chars = self.view.size()
        region = sublime.Region(0, chars)
        lines = self.view.lines(region)
        lines_count = len(lines)
        return range(1, lines_count + 1)

    def update_vcs_file(self):
        # the git repo won't change that often
        # so we can easily wait 5 seconds
        # between updates for performance
        if ViewCollection.vcs_time(self.view) > 5:
            open(self.vcs_temp_file.name, 'w').close()
            status_args = self.get_status_args()
            status = None
            try:
                # XY file-name
                contents, errors = self.run_command(status_args)
                status = self.process_status_line(contents)
                ViewCollection.update_vcs_status(self.view, status)
            except Exception as e:
                # print e
                pass

            args = self.get_diff_args()
            try:
                if status == 'M':
                    contents, errors = self.run_command(args)
                    contents = contents.replace(b'\r\n', b'\n')
                    contents = contents.replace(b'\r', b'\n')
                    # TODO: remove copy-and-paste here
                    f = open(self.vcs_temp_file.name, 'wb')
                    f.write(contents)
                    f.close()
                    ViewCollection.update_vcs_time(self.view)
            except Exception as e:
                print ("Unable to write file for diff ", e)

    def process_diff(self, diff_str):
        inserted = []
        modified = []
        deleted = []
        pattern = re.compile(b'(\d+),?(\d*)(.)(\d+),?(\d*)')
        lines = diff_str.splitlines()
        for line in lines:
            m = pattern.match(line)
            if not m:
                continue
            kind = m.group(3)
            line_start = int(m.group(4))
            if len(m.group(5)) > 0:
                line_end = int(m.group(5))
            else:
                line_end = line_start
            if kind == b'c':
                modified += range(line_start, line_end + 1)
            elif kind == b'a':
                inserted += range(line_start, line_end + 1)
            elif kind == b'd':
                if line == 1:
                    deleted.append(line_start)
                else:
                    deleted.append(line_start + 1)
        if inserted == self.total_lines():
            # All lines are "inserted"
            # this means this file is either:
            # - New and not being tracked *yet*
            # - Or it is a *gitignored* file
            if ViewCollection.vcs_status(self.view) == 'U':
                # use special region 'unknown'
                return ([], [], [], inserted)
            return (inserted, modified, deleted, [])
        else:
            return (inserted, modified, deleted, [])

    def diff(self):
        if self.on_disk() and self.vcs_path:
            self.update_vcs_file()
            self.update_buf_file()
            args = [
                'diff',
                self.vcs_temp_file.name,
                self.buf_temp_file.name,
            ]
            results, errors = self.run_command(args)
            # print errors
            return self.process_diff(results)
        else:
            return ([], [], [], [])

    def run_command(self, args):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                startupinfo=startupinfo)
        return proc.stdout.read(), proc.stderr.read()


class GitGutterHandler(VcsGutterHandler):
    def get_vcs_helper(self):
        return vcs_helpers.GitHelper()

    def get_diff_args(self):
        args = [
            self.exc_path,
            '--git-dir=' + self.vcs_dir,
            '--work-tree=' + self.vcs_tree,
            'show',
            'HEAD:' + self.vcs_path,
        ]
        return args

    def get_status_args(self):
        args = [
            self.exc_path,
            '--git-dir=' + self.vcs_dir,
            '--work-tree=' + self.vcs_tree,
            'status',
            '--ignored',
            '--porcelain',
            self.vcs_path,
        ]
        return args

    def process_status_line(self, st):
        st = st[0:2]
        if st == '!!':
            return 'I'
        elif st == '??':
            return 'U'
        else:
            return 'M'
            # all other states we may consider as modified


class HgGutterHandler(VcsGutterHandler):
    def get_vcs_helper(self):
        return vcs_helpers.HgHelper()

    def get_diff_args(self):
        args = [
            self.exc_path,
            '--repository',
            self.vcs_tree,
            'cat',
            os.path.join(self.vcs_tree, self.vcs_path),
        ]
        return args


class SvnGutterHandler(VcsGutterHandler):
    def get_vcs_helper(self):
        return vcs_helpers.SvnHelper()

    def get_diff_args(self):
        args = [
            self.exc_path,
            'cat',
            os.path.join(self.vcs_tree, self.vcs_path),
        ]
        return args
