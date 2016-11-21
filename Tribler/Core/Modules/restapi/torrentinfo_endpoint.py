import json
from urllib import url2pathname
from libtorrent import bdecode, bencode
from twisted.internet.defer import Deferred

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import fix_torrent, http_get, parse_magnetlink


class TorrentInfoEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = None

    def render_GET(self, request):
        """
        .. http:get:: /torrentinfo

        A GET request to this endpoint will return information from a torrent found at a provided URI.
        This URI can either represent a file location, a magnet link or a HTTP(S) url.
        - torrent: the URI of the torrent file that should be downloaded. This parameter is required.

            **Example request**:

                .. sourcecode:: none

                    curl -X PUT http://localhost:8085/torrentinfo?torrent=file:/home/me/test.torrent

            **Example response**:

                .. sourcecode:: javascript

                    {"metainfo": <torrent metainfo dictionary>}
        """
        metainfo_deferred = Deferred()

        def on_got_metainfo(metainfo):
            if self.infohash:
                # Save the torrent to our store
                self.session.save_collected_torrent(self.infohash, bencode(metainfo))

            del metainfo['info']['pieces']
            request.write(json.dumps({"metainfo": metainfo}))
            request.finish()

        def on_metainfo_timeout(_):
            request.setResponseCode(http.REQUEST_TIMEOUT)
            request.write(json.dumps({"error": "timeout"}))
            request.finish()

        if 'uri' not in request.args or len(request.args['uri']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "uri parameter missing"})

        uri = unicode(request.args['uri'][0], 'utf-8')
        if uri.startswith('file:'):
            filename = url2pathname(uri[5:])
            torrent_data = fix_torrent(filename)
            metainfo_deferred.callback(bdecode(torrent_data))
        elif uri.startswith('http'):
            def _on_loaded(tdef):
                metainfo_deferred.callback(bdecode(tdef))
            http_get(uri.encode('utf-8')).addCallback(_on_loaded)
        elif uri.startswith('magnet'):
            self.infohash = parse_magnetlink(uri)[1]
            if self.session.has_collected_torrent(self.infohash):
                tdef = TorrentDef.load_from_memory(self.session.get_collected_torrent(self.infohash))
                on_got_metainfo(tdef.get_metainfo())
                return NOT_DONE_YET

            self.session.lm.ltmgr.get_metainfo(uri, callback=metainfo_deferred.callback, timeout=20,
                                               timeout_callback=on_metainfo_timeout, notify=True)
        else:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "invalid uri"})

        metainfo_deferred.addCallback(on_got_metainfo)

        return NOT_DONE_YET
