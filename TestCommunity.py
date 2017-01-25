from com.dispersy.community import Community
from com.Tribler.community.multichain.community import MultiChainCommunity
from com.dispersy.authentication import MemberAuthentication
from com.dispersy.community import Community
from com.dispersy.conversion import DefaultConversion
from com.dispersy.destination import CommunityDestination
from com.dispersy.distribution import DirectDistribution
from com.dispersy.message import Message, DelayMessageByProof
from com.dispersy.resolution import PublicResolution
from time import time
from com.dispersy.candidate import Candidate, WalkCandidate
from com.dispersy.requestcache import RequestCache, SignatureRequestCache, IntroductionRequestCache
from com.Tribler.community.multichain.conversion import MultiChainConversion
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ExampleCommunity(MultiChainCommunity):

    def initialize(self):
        super(ExampleCommunity, self).initialize()
        self._logger.info("Example community initialized")
    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]
    #rewrite take_step:
    def take_step(self):
        now = time()
        self._logger.debug("previous sync was %.1f seconds ago",
                           now - self._last_sync_time if self._last_sync_time else -1)
        #print("previous sync was %.1f seconds ago",
                           #now - self._last_sync_time if self._last_sync_time else -1)
        candidate = self.dispersy_get_walk_candidate()
        #if candidate:
            #print "candidate address is:"+str(candidate.sock_addr)
        print "now I have following candidates:"
        for candidate in self._candidates.itervalues():
            print candidate.sock_addr
        if candidate:
            self._logger.debug("%s %s taking step towards %s",
                               self.cid.encode("HEX"), self.get_classification(), candidate)
            self.create_introduction_request(candidate, self.dispersy_enable_bloom_filter_sync)
        else:
            self._logger.debug("%s %s no candidate to take step", self.cid.encode("HEX"), self.get_classification())
        self._last_sync_time = time()


    #rewrite create_introduction request, try to simplify it
    def create_introduction_request(self, destination, allow_sync, forward=True, is_fast_walker=False, extra_payload=None):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]
        assert not extra_payload or isinstance(extra_payload, list), 'extra_payload is not a list %s' % type(extra_payload)

        cache = self.request_cache.add(IntroductionRequestCache(self, destination))
        destination.walk(time())

        # decide if the requested node should introduce us to someone else
        # advice = random() < 0.5 or len(community.candidates) <= 5
        advice = True

        # in this test, I don't want any sync
        sync=None

        args_list = [destination.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, sync, cache.number]
        if extra_payload is not None:
            args_list += extra_payload
        args_list = tuple(args_list)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=args_list)

        if forward:
            if sync:
                time_low, time_high, modulo, offset, _ = sync
                self._logger.debug("%s %s sending introduction request to %s [%d:%d] %%%d+%d",
                                   self.cid.encode("HEX"), type(self), destination,
                                   time_low, time_high, modulo, offset)
            else:
                self._logger.debug("%s %s sending introduction request to %s",
                                   self.cid.encode("HEX"), type(self), destination)

            self._dispersy._forward([request])

        return request


    def on_introduction_request(self, messages, extra_payload=None):
        assert not extra_payload or isinstance(extra_payload, list), 'extra_payload is not a list %s' % type(extra_payload)

        meta_introduction_response = self.get_meta_message(u"dispersy-introduction-response")
        meta_puncture_request = self.get_meta_message(u"dispersy-puncture-request")
        responses = []
        requests = []
        now = time()

        #
        # make all candidates available for introduction
        #
        for message in messages:
            candidate = self.create_or_update_walkcandidate(message.candidate.sock_addr, message.payload.source_lan_address, message.payload.source_wan_address, message.candidate.tunnel, message.payload.connection_type, message.candidate)
            candidate.stumble(now)
            message._candidate = candidate

            # apply vote to determine our WAN address
            self._dispersy.wan_address_vote(message.payload.destination_address, candidate)

            self.filter_duplicate_candidate(candidate)
            self._logger.debug("received introduction request from %s", candidate)
            print "receive introduction request from: "+str(candidate.sock_addr)
        #
        # process the walker part of the request
        #
        for message in messages:
            payload = message.payload
            candidate = message.candidate
            if not candidate:
                continue
            if payload.advice:
                introduced = self.dispersy_get_introduce_candidate(candidate)
                if introduced is None:
                    self._logger.debug("no candidates available to introduce")
            else:
                introduced = None

            if introduced:
                self._logger.debug("telling %s that %s exists %s", candidate, introduced, type(self))

                introduction_args_list = [candidate.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, introduced.lan_address, introduced.wan_address, self._dispersy._connection_type, introduced.tunnel, payload.identifier]
                if extra_payload is not None:
                    introduction_args_list += extra_payload
                introduction_args_list = tuple(introduction_args_list)

                # create introduction response
                responses.append(meta_introduction_response.impl(authentication=(self.my_member,), distribution=(self.global_time,), destination=(candidate,), payload=introduction_args_list))

                # create puncture request
                requests.append(meta_puncture_request.impl(distribution=(self.global_time,), destination=(introduced,), payload=(payload.source_lan_address, payload.source_wan_address, payload.identifier)))

            else:
                self._logger.debug("responding to %s without an introduction %s", candidate, type(self))

                none = ("0.0.0.0", 0)

                introduction_args_list = [candidate.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, none, none, self._dispersy._connection_type, False, payload.identifier]
                if extra_payload is not None:
                    introduction_args_list += extra_payload
                introduction_args_list = tuple(introduction_args_list)

                responses.append(meta_introduction_response.impl(authentication=(self.my_member,), distribution=(self.global_time,), destination=(candidate,), payload=introduction_args_list))

        if responses:
            self._dispersy._forward(responses)
        if requests:
            self._dispersy._forward(requests)

        #
        # process the bloom filter part of the request
        #
        messages_with_sync = []
        for message in messages:
            payload = message.payload
            candidate = message.candidate
            if not candidate:
                continue

            if payload.sync:
                # 07/05/12 Boudewijn: for an unknown reason values larger than 2^63-1 cause
                # overflow exceptions in the sqlite3 wrapper

                # 11/11/13 Niels: according to http://www.sqlite.org/datatype3.html integers are signed and max
                # 8 bytes, hence the max value is 2 ** 63 - 1 as one bit is used for the sign
                time_low = min(payload.time_low, 2 ** 63 - 1)
                time_high = min(payload.time_high if payload.has_time_high else self.global_time, 2 ** 63 - 1)

                offset = long(payload.offset)
                modulo = long(payload.modulo)

                messages_with_sync.append((message, time_low, time_high, offset, modulo))

        if messages_with_sync:
            for message, generator in self._get_packets_for_bloomfilters(messages_with_sync, include_inactive=False):
                payload = message.payload
                # we limit the response by byte_limit bytes
                byte_limit = self.dispersy_sync_response_limit

                packets = []
                for packet, in payload.bloom_filter.not_filter(generator):
                    packets.append(packet)
                    byte_limit -= len(packet)
                    if byte_limit <= 0:
                        self._logger.debug("bandwidth throttle")
                        break

                if packets:
                    self._logger.debug("syncing %d packets (%d bytes) to %s",
                                       len(packets), sum(len(packet) for packet in packets), message.candidate)
                    self._dispersy._send_packets([message.candidate], packets, self, "-caused by sync-")


    def on_introduction_response(self, messages):
        now = time()

        for message in messages:
            payload = message.payload
            candidate = self.create_or_update_walkcandidate(message.candidate.sock_addr, payload.source_lan_address, payload.source_wan_address, message.candidate.tunnel, payload.connection_type, message.candidate)
            candidate.walk_response(now)
            print "the introduced candidate is: "+str(message.candidate.sock_addr)

            self.filter_duplicate_candidate(candidate)
            self._logger.debug("introduction response from %s", candidate)

            # apply vote to determine our WAN address
            self._dispersy.wan_address_vote(payload.destination_address, candidate)

            # get cache object linked to this request and stop timeout from occurring
            cache = self.request_cache.get(u"introduction-request", message.payload.identifier)
            cache.on_introduction_response()

            # handle the introduction
            lan_introduction_address = payload.lan_introduction_address
            wan_introduction_address = payload.wan_introduction_address
            if not (lan_introduction_address == ("0.0.0.0", 0) or wan_introduction_address == ("0.0.0.0", 0)):
                # we need to choose either the lan or wan address to be used as the sock_addr
                # currently we base this decision on the wan ip, if its the same as ours we're probably behind the same NAT and hence must use the lan address
                sock_introduction_addr = lan_introduction_address if wan_introduction_address[0] == self._dispersy._wan_address[0] else wan_introduction_address
                introduced = self.create_or_update_walkcandidate(sock_introduction_addr, lan_introduction_address, wan_introduction_address, payload.tunnel, u"unknown")
                introduced.intro(now)

                self.filter_duplicate_candidate(introduced)
                self._logger.debug("received introduction to %s from %s", introduced, candidate)

                cache.response_candidate = introduced

                # update statistics
                if self._dispersy._statistics.received_introductions is not None:
                    self._dispersy._statistics.received_introductions[candidate.sock_addr][introduced.sock_addr] += 1

            else:
                # update statistics
                if self._dispersy._statistics.received_introductions is not None:
                    self._dispersy._statistics.received_introductions[candidate.sock_addr]['-ignored-'] += 1

    def on_puncture_request(self, messages):
        meta_puncture = self.get_meta_message(u"dispersy-puncture")
        punctures = []
        for message in messages:
            lan_walker_address = message.payload.lan_walker_address
            wan_walker_address = message.payload.wan_walker_address
            assert is_valid_address(lan_walker_address), lan_walker_address
            assert is_valid_address(wan_walker_address), wan_walker_address

            # we are asked to send a message to a -possibly- unknown peer get the actual candidate
            # or create a dummy candidate
            sock_addr = lan_walker_address if wan_walker_address[0] == self._dispersy._wan_address[0] else wan_walker_address
            candidate = self.get_candidate(sock_addr, replace=False, lan_address=lan_walker_address)
            if candidate is None:
                # assume that tunnel is disabled
                tunnel = False
                candidate = Candidate(sock_addr, tunnel)

            punctures.append(meta_puncture.impl(authentication=(self.my_member,), distribution=(self.global_time,), destination=(candidate,), payload=(self._dispersy._lan_address, self._dispersy._wan_address, message.payload.identifier)))
            self._logger.debug("%s asked us to send a puncture to %s", message.candidate, candidate)
            print "the candidate to puncture is: "+str(candidate.sock_addr)

        self._dispersy._forward(punctures)


    def on_puncture(self, messages):
        now = time()

        for message in messages:
            cache = self.request_cache.get(u"introduction-request", message.payload.identifier)
            cache.on_puncture()

            if not (message.payload.source_lan_address == ("0.0.0.0", 0) or message.payload.source_wan_address == ("0.0.0.0", 0)):
                candidate = self.create_or_update_walkcandidate(message.candidate.sock_addr, message.payload.source_lan_address, message.payload.source_wan_address, message.candidate.tunnel, u"unknown", message.candidate)
                candidate.intro(now)

                self._logger.debug("received punture from %s", candidate)
                cache.puncture_candidate = candidate