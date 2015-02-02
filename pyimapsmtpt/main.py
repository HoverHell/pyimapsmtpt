#!/usr/bin/python
# coding: utf8
import os
import signal
import sys
import time
import xmpp
import logging
from xmpp.browser import (
    ERR_JID_MALFORMED,
    ERR_ITEM_NOT_FOUND,
    Browser,
    NS_VERSION,
    NS_COMMANDS,
    Error,
    NodeProcessed,
    Presence,
)

from .confloader import get_config
from .common import configure_logging, config_email_utf8
from .convertlayer import MailJabberLayer


_log = logging.getLogger(__name__)



class Transport(object):

    online = 1

    ## Message to be posted to XMPP server as the status when going offline
    offlinemsg = ''

    ## For future filling
    disco = None

    def __init__(self, config, jabber):
        self.config = config
        self.jid = config.xmpp_component_jid
        self.jabber = jabber
        self.layer = MailJabberLayer(config=config)
        config_email_utf8()

    #######
    ## Daemonstuff
    #######

    def setup_signals(self):
        signal.signal(signal.SIGINT, self.sighandler)
        signal.signal(signal.SIGTERM, self.sighandler)

    def sighandler(self, signum, frame):
        self.offlinemsg = 'Signal handler called with signal %s' % (signum,)
        _log.info('Signal handler called with signal %s', signum)
        self.online = 0

    #######
    ## XMPP stuff
    #######

    def register_handlers(self):
        self.jabber.RegisterHandler('message', self.xmpp_message)
        self.jabber.RegisterHandler('presence', self.xmpp_presence)
        self.disco = Browser()
        self.disco.PlugIn(self.jabber)
        self.disco.setDiscoHandler(
            self.xmpp_base_disco, node='',
            jid=self.jid)

    def xmpp_base_disco(self, con, event, ev_type):
        fromjid = str(event.getFrom())
        to = event.getTo()
        node = event.getQuerynode()

        # Type is either 'info' or 'items'
        if to == self.jid:
            if node == None:
                if ev_type == 'info':
                    return dict(
                        ids=[dict(
                            category='gateway', type='smtp',
                            name=self.config.xmpp_disco_name)],
                        features=[NS_VERSION, NS_COMMANDS])
                if ev_type == 'items':
                    return []
            else:
                self.jabber.send(Error(event, ERR_ITEM_NOT_FOUND))
                raise NodeProcessed
        else:
            self.jabber.send(Error(event, ERR_JID_MALFORMED))
            raise NodeProcessed

    def xmpp_presence(self, con, event):
        # Add ACL support
        fromjid = event.getFrom()
        ev_type = event.getType()
        to = event.getTo()
        if ev_type in ('subscribe', 'subscribed', 'unsubscribe', 'unsubscribed', 'unavailable'):
            self.jabber.send(Presence(to=fromjid, frm=to, typ=ev_type))
        elif ev_type == 'probe':
            self.jabber.send(Presence(to=fromjid, frm=to))
        elif ev_type == 'error':
            return
        else:
            self.jabber.send(Presence(to=fromjid, frm=to))

    def xmpp_message(self, con, event):
        self.layer.xmpp_to_smtp(event, connection=con)

    def xmpp_connect(self):
        connected = self.jabber.connect((
            self.config.xmpp_main_server, self.config.xmpp_component_port))
        _log.info("connected: %r", connected)
        while not connected:
            time.sleep(5)
            connected = self.jabber.connect((
                self.config.xmpp_main_server, self.config.xmpp_component_port))
            _log.info("connected: %r", connected)
        self.register_handlers()
        _log.info("trying auth")
        connected = self.jabber.auth(
            self.config.xmpp_sasl_username, self.config.xmpp_secret)
        _log.info("auth return: %r", connected)
        return connected

    def xmpp_disconnect(self):
        ## Augh.
        time.sleep(5)
        if not self.jabber.reconnectAndReauth():
            time.sleep(5)
            self.xmpp_connect()


def main():
    config = get_config()
    if config.pidfile:
        with open(config.pidfile, 'wb') as f:
            f.write(str(os.getpid()))

    configure_logging(config)

    if config.xmpp_sasl_username:
        sasl = 1
    else:
        config.xmpp_sasl_username = config.jid
        sasl = 0

    if config.dump_protocol:
        debug = ['always', 'nodebuilder']
    else:
        debug = []

    xmpp_connection = xmpp.client.Component(
        config.xmpp_component_jid, config.xmpp_component_port,
        debug=debug,
        sasl=sasl,
        bind=config.use_component_binding,
        route=config.use_route_wrap)

    xmpp_transport = Transport(config, xmpp_connection)
    if not xmpp_transport.xmpp_connect():
        _log.error("Could not connect to server, or password mismatch!")
        sys.exit(1)

    xmpp_transport.setup_signals()

    while xmpp_transport.online:
        try:
            xmpp_connection.Process(1)
        except KeyboardInterrupt:
            _pendingException = sys.exc_info()
            raise _pendingException[0], _pendingException[1], _pendingException[2]
        except IOError:
            xmpp_transport.xmpp_disconnect()
        except Exception as exc:
            _log.error("xmpp process error: %r", exc)

        if not xmpp_connection.isConnected():
            xmpp_transport.xmpp_disconnect()

    xmpp_connection.disconnect()

    if config.pidfile:
        os.unlink(config.pidfile)

    ## Probably should not be used
    if config.auto_self_restart:
        args = [sys.executable] + sys.argv
        if os.name == 'nt':
            args = ["\"%s\"" % (a,) for a in args]
        if config.dumpProtocol:
            _log.info("Self-restarting with %r %r", sys.executable, args)
        os.execv(sys.executable, args)


if __name__ == '__main__':
    main()
