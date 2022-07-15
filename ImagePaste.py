from tempfile import tempdir
import sublime
import sublime_plugin
import os
import sys
import re
import subprocess
import shutil
from imp import reload

# print(sys.getdefaultencoding())
reload(sys)
# sys.setdefaultencoding('utf-8')

def is_windows():
	return sys.platform == 'win32'

def is_mac():
	return sys.platform == 'darwin'

if is_windows() or is_mac():
	package_file = os.path.normpath(os.path.abspath(__file__))
	package_path = os.path.dirname(package_file)
	lib_path =  os.path.join(package_path, "lib")
	if lib_path not in sys.path:
	    sys.path.append(lib_path)
	    print(sys.path)
	from PIL import ImageGrab
	from PIL import ImageFile
	from PIL import Image

def get_settings():
	return sublime.load_settings('imagepaste.sublime-settings')

def get_image_dir_name(settings):
	return settings.get('image_dir_name', '$doc_name')

def get_image_file_name(settings):
	return settings.get('image_file_name', '$doc_name-$num[03]')

def add_quote_to_path(path):
	if path[0] == '\"' or path[0] == '\'':
		return path
	else:
		return '\'' + path + '\''

# Allows $num, $num[03] (to print 001, etc.)
def replace_num_token(in_string, value):
	def replacement(match):
		if match.group(2):
			return ("%" + match.group(2) + "d") % value
		else:
			return str(value)
	return re.sub('\$num(\[([\d\w]*)\])?', replacement, in_string)


class ImageCommand(object):
	def __init__(self, *args, **kwgs):
		super(ImageCommand, self).__init__(*args, **kwgs)

	def run_command(self, cmd):
		print('#1', cmd)
		cwd = os.path.dirname(self.view.file_name())
		print("cmd %r" % cmd)
		proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=os.environ)

		try:
		    outs, errs = proc.communicate(timeout=15)
		    print("outs %r %r" % (outs, proc))
		except Exception:
		    proc.kill()
		    outs, errs = proc.communicate()
		print("outs %r, errs %r" % (b'\n'.join(outs.split(b'\r\n')), errs))
		if errs is None or len(errs) == 0:
			return outs.decode()

	def get_filename(self):
		settings = get_settings()
		image_dir_name = get_image_dir_name(settings)
		image_file_name = get_image_file_name(settings)

		view = self.view
		filename = view.file_name()
		base_path = os.path.dirname(filename)
		base_name, _ = os.path.splitext(os.path.basename(filename))

		rel_path = image_dir_name.replace('$doc_name', base_name)
		full_path = os.path.join(base_path, rel_path)
		if not os.path.lexists(full_path):
			os.mkdir(full_path)
		i = 1
		while True:
			file_name = replace_num_token(image_file_name.replace('$doc_name', base_name), i) + '.png'
			rel_filename = os.path.join(rel_path, file_name)
			abs_filename = os.path.join(full_path, file_name)
			if not os.path.exists(abs_filename):
				break
			i += 1

		print("save file: " + abs_filename + "\nrel " + rel_filename)
		return abs_filename, rel_filename

class ImagePasteCommand(ImageCommand, sublime_plugin.TextCommand):

	def run(self, edit):
		view = self.view
		rel_fn = self.paste()

		if not rel_fn:
			view.run_command("paste")
			return
		for pos in view.sel():
			# print("scope name: %r" % (view.scope_name(pos.begin())))
			if 'text.html.markdown' in view.scope_name(pos.begin()):
				view.insert(edit, pos.begin(), "![](%s)" % rel_fn)
			else:
				view.insert(edit, pos.begin(), "%s" % rel_fn)
			# only the first cursor add the path
			break


	def paste(self):
		if not is_windows() and not is_mac():
			dirname = os.path.dirname(__file__)
			command = ['/usr/bin/python3', add_quote_to_path(os.path.join(dirname, 'bin/imageutil.py')), 'save']
			abs_fn, rel_fn = self.get_filename()
			command.append(abs_fn)

			out = self.run_command(" ".join(command))
			if out and out[:4] == "save":
				return rel_fn
		else: # win32
			ImageFile.LOAD_TRUNCATED_IMAGES = True
			im = ImageGrab.grabclipboard()
			if im:
				abs_fn, rel_fn = self.get_filename()
				im.save(abs_fn,'PNG')
				return rel_fn

		print('clipboard buffer is not image!')
		return None



class ImageGrabCommand(ImageCommand, sublime_plugin.TextCommand):
	def run(self, edit):
		view = self.view
		rel_fn = self.paste()
		if not rel_fn:
			view.run_command("paste")
			return
		for pos in view.sel():
			# print("scope name: %r" % (view.scope_name(pos.begin())))
			if 'text.html.markdown' in view.scope_name(pos.begin()):
				view.insert(edit, pos.begin(), "![](%s)" % rel_fn)
			else:
				view.insert(edit, pos.begin(), "%s" % rel_fn)
			# only the first cursor add the path
			break


	def paste(self):
		# ImageFile.LOAD_TRUNCATED_IMAGES = True
		dirname = os.path.dirname(__file__)
		command = ['/usr/bin/python3', add_quote_to_path(os.path.join(dirname, 'bin/imageutil.py')), 'grab']
		abs_fn, rel_fn = self.get_filename()
		tempfile1 = "/tmp/imagepaste1.png"
		command.append(tempfile1)
		print("command: ", command)

		out = self.run_command(" ".join(command))
		if out and out[:4] == "grab":
			ret = sublime.ok_cancel_dialog("save to file?")
			print("ret %r" % ret)
			if ret:
				shutil.move(tempfile1, abs_fn)
				return rel_fn
			else:
				return None
		# im = ImageGrab.grabclipboard()
		# if im:
		# 	abs_fn, rel_fn = self.get_filename()
		# 	im.save(abs_fn,'PNG')
		# 	return rel_fn
		else:
			print('clipboard buffer is not image!')
			return None


class ImagePreviewCommand(ImageCommand, sublime_plugin.TextCommand):
	def __init__(self, *args):
	#	self.view = view
		super(ImagePreviewCommand, self).__init__(*args)
		# self.phantom_set = sublime.PhantomSet(self.view)
		self.displayed = False




	def get_line(self):
		v = self.view
		rows, _ = v.rowcol(v.size())
		for row in range(rows+1):
			pt = v.text_point(row, 0)
			tp_line = v.line(pt)
			line = v.substr(tp_line)
			yield tp_line, line
		raise StopIteration

	def run(self, edit):
		print("run phantom")
		view = self.view
		dirname = os.path.dirname(__file__)
		for tp, line in self.get_line():
			m=re.search(r'!\[([^\]]*)\]\(([^)]*)\)', line)
			if m:
				name, file1 = m.group(1), m.group(2)
				message = ""
				file2 = os.path.join(os.path.dirname(view.file_name()), file1)
				# print("%s = %s" % (name, file1))
				region = tp

				command = ['/usr/bin/python3', add_quote_to_path(os.path.join(dirname, 'bin/imageutil.py')), 'size']
				command.append(file2)

				out = self.run_command(" ".join(command))
				widthstr, heightstr = out.split(',')
				# with Image.open(file2) as im:
				# print("file: %s with size: %d %d" % (file1, im.width, im.height))
				message = '''<body>
				<img width="%s" height="%s" src="file://%s"></img>
				</body>''' % (widthstr, heightstr, file2)
				if len(name) == 0:
					name = file1

		# phantom = sublime.Phantom(region, messag e, sublime.LAYOUT_BLOCK)
				print("message %s" % message)
				if not self.displayed:
					self.view.add_phantom(name, region, message, sublime.LAYOUT_BLOCK)
				else:
					self.view.erase_phantoms(name)
		# self.phantom_set.update([phantom])
		# view.show_popup('<img src="file://c://msys64/home/chenyu/diary/diary/diary8.jpg">')
		self.displayed = not self.displayed

