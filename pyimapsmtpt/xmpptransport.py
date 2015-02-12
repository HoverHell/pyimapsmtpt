#!/usr/bin/env python
# coding: utf8

import logging
import signal
import time
import xmpp
from xmpp.browser import (
    ERR_ITEM_NOT_FOUND,
    ERR_JID_MALFORMED,
    NS_COMMANDS,
    NS_VERSION,
    Browser,
    Error,
    Message,
    NodeProcessed,
    Presence,
)

from .common import jid_to_data


_log = logging.getLogger(__name__)


def event_to_data(event, add_event=True):
    """ XMPP event to abstractised data """
    res = dict(
        _event=event,
        _type=event.getType(),
        frm=jid_to_data(event.getFrom()),
        to=jid_to_data(event.getTo()),
        body=event.getBody(),
        subject=event.getSubject(),
    )
    return res

#######
## The Transport
#######

class Transport(object):
    """ ...

    Stopping: `this.online = False`, wait.
    """

    online = 1
    process_timeout = 5

    ## Message to be posted to XMPP server as the status when going offline
    offlinemsg = ''

    ## For future filling
    disco = None

    def __init__(self, config, message_callback=None):
        self.config = config
        self.jid = config.xmpp_component_jid
        self.conn = self._mk_conn(config)
        if message_callback is None:
            message_callback = lambda *ar, **kwa: None
        self.message_callback = message_callback

    def _mk_conn(self, config):
        sasl = bool(config.xmpp_sasl_username)

        if config.dump_protocol:
            debug = ['always', 'nodebuilder']
        else:
            debug = []

        xmpp_connection = xmpp.client.Component(
            config.xmpp_component_jid, config.xmpp_component_port,
            debug=debug,
            sasl=sasl,
            bind=config.xmpp_use_component_binding,
            route=config.xmpp_use_route_wrap)
        return xmpp_connection

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

    def pre_run(self, setup_signals=False, **kwa):
        if setup_signals:
            self.setup_signals()
        if not self.xmpp_connect():
            _msg = "Could not connect to XMPP server, or password mismatch."
            _log.error(_msg)
            raise Exception(_msg)

    def run(self, pre_run=True, **kwa):
        if pre_run:
            self.pre_run(**kwa)
        try:
            return self.run_loop(**kwa)
        finally:
            pass

    def run_loop(self, **kwa):
        while self.online:
            try:
                conn = self.conn
                conn.Process(  # pylint: disable=no-member
                    self.process_timeout)
            except KeyboardInterrupt:
                raise
            except IOError:
                self.xmpp_reconnect()
            except Exception as exc:
                _log.error("xmpp process error: %r", exc)

            if not self.conn.isConnected():
                self.xmpp_reconnect()


    #######
    ## XMPP stuff
    #######

    def send_message_data(self, msg_data, **kwa):
        ## TODO: support error events
        msg = Message(**msg_data)
        self.send_message(msg)

    def send_message(self, msg, **kwa):
        conn = self.conn
        return conn.send(  # pylint: disable=no-member
            msg, **kwa)

    def register_handlers(self):
        conn = self.conn
        conn.RegisterHandler(  # pylint: disable=no-member
            'message', self.xmpp_message)
        conn.RegisterHandler(  # pylint: disable=no-member
            'presence', self.xmpp_presence)
        self.disco = Browser()
        self.disco.PlugIn(self.conn)
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
                self.send_message(Error(event, ERR_ITEM_NOT_FOUND))
                raise NodeProcessed
        else:
            self.send_message(Error(event, ERR_JID_MALFORMED))
            raise NodeProcessed

    def xmpp_presence(self, con, event):
        # Add ACL support
        fromjid = event.getFrom()
        ev_type = event.getType()
        to = event.getTo()
        if ev_type in ('subscribe', 'subscribed', 'unsubscribe', 'unsubscribed', 'unavailable'):
            self.send_message(Presence(to=fromjid, frm=to, typ=ev_type))
        elif ev_type == 'probe':
            self.send_message(Presence(to=fromjid, frm=to))
        elif ev_type == 'error':
            return
        else:
            self.send_message(Presence(to=fromjid, frm=to))

    def xmpp_connect(self):
        connected = self.conn.connect((
            self.config.xmpp_main_server, self.config.xmpp_component_port))
        _log.info("connected: %r", connected)
        while not connected:
            time.sleep(5)  ## XXXX: ...
            connected = self.conn.connect((
                self.config.xmpp_main_server, self.config.xmpp_component_port))
            _log.info("connected: %r", connected)
        self.register_handlers()
        _log.info("trying auth")
        connected = self.conn.auth(
            self.config.xmpp_sasl_username or self.jid,
            self.config.xmpp_secret)
        _log.info("auth return: %r", connected)
        return connected

    def xmpp_reconnect(self):
        ## XXXX: ...Augh.
        time.sleep(5)  ## XXXX: ...
        if not self.conn.reconnectAndReauth():
            time.sleep(5)  ## XXXX: ...
            self.xmpp_connect()

    def xmpp_message_preprocess(self, event, con=None):
        ev_type = event.getType()
        to = event.getTo()

        ## skip 'error' messages
        ##  (example: recipient not found, `<message from='…'
        ##  to='…@pymailt.…' type='error' id='1'>…<error code='503'
        ##  type='cancel'>…<service-unavailable
        ##  xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>…`)
        if ev_type == 'error':
            _log.error("Error XMPP message: %r, %r", event, str(event))
            return

        ## Messages to nowhere are irrelevant
        if to.getNode() == '':
            self.send_message(Error(event, ERR_ITEM_NOT_FOUND))
            return

        ## XXXX: unclear. Probably makes sure an empty subject is presented as `None`
        try:
            if (event.getSubject() or '').strip() == '':
                event.setSubject(None)
        except AttributeError:
            pass

        event_data = event_to_data(event)
        return event_data

    def xmpp_message(self, con, event):
        event_data = self.xmpp_message_preprocess(event, con=con)
        if not event_data:
            return

        msg_kwa = dict(event_data, _event=event, _connection=con, _transport=self)
        self.message_callback(msg_kwa)


def main():
    from .confloader import get_config

    config = get_config()

    def debug_callback(event, **kwa):
        print('\n  '.join('%s: %r' % (a, b) for a, b in [
            ("Event", event),
            ("type", event.getType()),
            ("from", event.getFrom()),
            ("to", event.getTo()),
            ("...", event.__dict__),
        ]))

    xmpp_transport = Transport(
        config=config, message_callback=debug_callback)
    xmpp_transport.run()


if __name__ == '__main__':
    main()
