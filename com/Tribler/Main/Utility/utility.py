# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import os
import sys
import logging
from random import gauss

from Tribler.Core.defaults import tribler_defaults
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.simpledefs import STATEDIR_GUICONFIG, UPLOAD, DOWNLOAD
from Tribler.Core.version import version_id
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig

logger = logging.getLogger(__name__)

#
# Generic "glue" class that contains commonly used helper functions
#
class Utility(object):

    def __init__(self, abcpath, configpath, app=None, session=None):

        self.version = version_id
        self.abcpath = abcpath

        # Find the directory to save config files, etc.
        self.dir_root = configpath

        self.setupConfig()

        # Is ABC in the process of shutting down?
        self.abcquitting = False

        self.app = app
        self.session = session

    def setupConfig(self):
        self.configfilepath = os.path.join(self.getConfigPath(), STATEDIR_GUICONFIG)
        self.config = CallbackConfigParser()

        # Load the config file.
        if os.path.exists(self.configfilepath):
            self.config.read_file(self.configfilepath, 'utf-8-sig')

        if not self.config.has_section('Tribler'):
            self.config.add_section('Tribler')

        # Tribler.conf also contains the default download config. So we need to merge it now.
        if not self.config.has_section('downloadconfig'):
            self.config.add_section('downloadconfig')
            for k, v in DefaultDownloadStartupConfig.getInstance().dlconfig._sections['downloadconfig'].iteritems():
                self.config.set('downloadconfig', k, v)

        # Make sure we use the same ConfigParser instance for both Utility and DefaultDownloadStartupConfig.
        DefaultDownloadStartupConfig.getInstance().dlconfig = self.config

    def getVersion(self):
        return self.version

    def getConfigPath(self):
        return self.dir_root

    def getPath(self):
        return self.abcpath

    def set_session(self, session):
        self.session = session

    def set_app(self, app):
        self.app = app

    def read_config(self, option, section='Tribler', literal_eval=True):
        if not self.config.has_option(section, option):
            return tribler_defaults.get(section, {}).get(option, None)

        return self.config.get(section, option, literal_eval=literal_eval)

    def write_config(self, option, value, section='Tribler', flush=True):
        self.config.set(section, option, value)
        if flush:
            self.flush_config()

    def flush_config(self):
        self.config.write_file(self.configfilepath)


def speed_format(s):
    text = ''
    if s is not None:
        s_abs = abs(s)
        if s_abs < 102400:
            text = '%2.1f KB/s' % (s / 1024.0)
        elif s_abs < 1022797:
            text = '%d KB/s' % (s // 1024)
        elif s_abs < 104857600:
            text = '%2.1f MB/s' % (s / 1048576.0)
        elif s_abs < 1047527425:
            text = '%d MB/s' % (s // 1048576)
        elif s_abs < 107374182400:
            text = '%2.1f GB/s' % (s / 1073741824.0)
        elif s_abs < 1072668082177:
            text = '%d GB/s' % (s // 1073741824)
        else:
            text = '%2.1f TB/s' % (s / 1099511627776.0)
    return text


def round_range(x):
    returnar = set()
    for _ in range(2500):
        value = int(gauss(x, 100))
        if value < 0:
            continue

        diff = abs(value - x)
        if diff < 2:
            pass
        elif diff < 10 and x < 50:
            value = int(round(value / 3.0) * 3)
        elif diff < 75:
            value = int(round(value / 25.0) * 25)
        elif diff < 450:
            value = int(round(value / 75.0) * 75)
        else:
            value = int(round(value / 150.0) * 150)

        returnar.add(value)
    returnar = sorted(returnar)
    return returnar


def eta_value(n, truncate=3):
    if n == -1:
        return u'<unknown>'
    if not n:
        return u''
    n = int(n)
    week, r1 = divmod(n, 60 * 60 * 24 * 7)
    day, r2 = divmod(r1, 60 * 60 * 24)
    hour, r3 = divmod(r2, 60 * 60)
    minute, sec = divmod(r3, 60)

    if week > 1000:
        return u'<unknown>'

    weekstr = u'%d' % week + u'w'
    daystr = u'%d' % day + u'd'
    hourstr = u'%d' % hour + u'h'
    minutestr = u'%d' % minute + u'm'
    secstr = u'%02d' % sec + u's'

    if week > 0:
        text = weekstr
        if truncate > 1:
            text += u":" + daystr
        if truncate > 2:
            text += u"-" + hourstr
    elif day > 0:
        text = daystr
        if truncate > 1:
            text += u"-" + hourstr
        if truncate > 2:
            text += u":" + minutestr
    elif hour > 0:
        text = hourstr
        if truncate > 1:
            text += u":" + minutestr
        if truncate > 2:
            text += u":" + secstr
    else:
        text = minutestr
        if truncate > 1:
            text += u":" + secstr

    return text


def size_format(s, truncate=None, stopearly=None, applylabel=True, rawsize=False,
                showbytes=False, labelonly=False, textonly=False):
    if truncate is None:
        truncate = 2

    s_abs = abs(s)

    if ((s_abs < 1024) and showbytes and stopearly is None) or stopearly == "Byte" or stopearly == "B":
        truncate = 0
        size = s
        text = u"Byte"
    elif ((s_abs < 1048576) and stopearly is None) or stopearly == "KB":
        size = (s / 1024.0)
        text = u"KB"
    elif ((s_abs < 1073741824) and stopearly is None) or stopearly == "MB":
        size = (s / 1048576.0)
        text = u"MB"
    elif ((s_abs < 1099511627776) and stopearly is None) or stopearly == "GB":
        size = (s / 1073741824.0)
        text = u"GB"
    else:
        size = (s / 1099511627776.0)
        text = u"TB"

    if textonly:
        return text

    label = u"B" if text == u"Byte" else text
    if labelonly:
        return label

    if rawsize:
        return size

    # At this point, only accepting 0, 1, or 2
    if truncate == 0:
        text = (u'%.0f' % size)
    elif truncate == 1:
        text = (u'%.1f' % size)
    else:
        text = (u'%.2f' % size)

    if applylabel:
        text += u' ' + label

    return text


def get_download_upload_speed(dslist):
    total_down, total_up = 0.0, 0.0
    for ds in dslist:
        total_down += ds.get_current_speed(DOWNLOAD)
        total_up += ds.get_current_speed(UPLOAD)
    return total_down, total_up


def initialize_x11_threads():
    if sys.platform == 'linux2' and os.environ.get("TRIBLER_INITTHREADS", "true").lower() == "true":
        for module in ['wx', 'wxversion', 'Tribler.vlc', 'vlc']:
            assert module not in sys.modules, "Called initialize_x11_threads after importing X related module: %s" % module
        try:
            import ctypes
            x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
            if not x11.XInitThreads():
                logger.error("Failed to initialize XInitThreads")
            os.environ["TRIBLER_INITTHREADS"] = "False"
        except OSError as e:
            logger.error("Failed to call XInitThreads '%s'", str(e))
        except Exception as e:
            logger.exception("Failed to call xInitThreads: '%s'", repr(e))