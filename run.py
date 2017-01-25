import errno
import os
import signal
import sys
from time import time
import logging
from com.dispersy.candidate import LoopbackCandidate
from com.dispersy.crypto import NoVerifyCrypto, NoCrypto
from com.dispersy.discovery.community import DiscoveryCommunity
from com.dispersy.dispersy import Dispersy
from com.dispersy.endpoint import StandaloneEndpoint
from com.dispersy.exception import CommunityNotFoundException
from com.dispersy.tracker.community import TrackerCommunity, TrackerHardKilledCommunity
from com.TestCommunity import ExampleCommunity
from twisted.application.service import IServiceMaker, MultiService
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred, DeferredList
from twisted.internet.task import LoopingCall
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg, ILogObserver, FileLogObserver
from twisted.python.logfile import DailyLogFile
from twisted.python.threadable import isInIOThread
from zope.interface import implements

from com.dispersy.tool.clean_observers import clean_twisted_observers

# Register yappi profiler
from com.dispersy.utils import twistd_yappi

logging.basicConfig(level=logging.DEBUG, filename="logfile", filemode="a+",
                    format="%(asctime)-15s %(levelname)-8s %(message)s")

def start_dispersy():
    # generate a new my-member
    master_key ="3081a7301006072a8648ce3d020106052b81040027038192000407afa96c83660dccfbf02a45b68f4bc" + \
                "4957539860a3fe1ad4a18ccbfc2a60af1174e1f5395a7917285d09ab67c3d80c56caf5396fc5b231d84ceac23627" + \
                "930b4c35cbfce63a49805030dabbe9b5302a966b80eefd7003a0567c65ccec5ecde46520cfe1875b1187d469823d" + \
                 "221417684093f63c33a8ff656331898e4bc853bcfaac49bc0b2a99028195b7c7dca0aea65"
    master_key_hex = master_key.decode("HEX")

    crypto = NoVerifyCrypto()
    ec = crypto.generate_key(u"very-low")
    #in fact the default database filename is u'dispersy.db'
    dispersy = Dispersy(StandaloneEndpoint(1235, '0.0.0.0'), unicode('.'), u'dispersy.db')
    print type(dispersy)
    dispersy.statistics.enable_debug_statistics(True)
    #load the discovery community
    dispersy.start(autoload_discovery=True)

    my_member = dispersy.get_new_member()
    master_member = dispersy.get_member(public_key=master_key_hex)
    #master_member = dispersy.get_member(public_key=crypto.key_to_bin(ec))
    #master_member = dispersy.get_member(private_key=crypto.key_to_bin(ec))
    #master_member = dispersy.get_member(public_key=master_key)


    community = ExampleCommunity.init_community(dispersy, master_member, my_member)



def main():
    reactor.callWhenRunning(start_dispersy)
    reactor.run()

if __name__ == "__main__":
    main()



