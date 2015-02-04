#!/usr/bin/env python
# coding: utf8

import re
import xmpp
import logging
from xmpp.browser import (
    ERR_ITEM_NOT_FOUND,
    ERR_JID_MALFORMED,
    NS_COMMANDS,
    NS_VERSION,
    NodeProcessed,
    Browser,
    Error,
    Presence,
)

from .common import jid_to_data


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
        config_email_utf8()

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
            bind=config.use_component_binding,
            route=config.use_route_wrap)
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

    def pre_run(self):
        self.setup_signals()
        if not xmpp_transport.xmpp_connect():
            _log.error("Could not connect to server, or password mismatch!")
            sys.exit(1)

    def run(self, pre_run=True):
        if pre_run:
            self.pre_run()
        try:
            return self.run_loop()
        finally:
            pass

    def run_loop(self):
        while self.online:
            try:
                self.conn.Process(self.process_timeout)
            except KeyboardInterrupt:
                raise
            except IOError:
                xmpp_transport.xmpp_reconnect()
            except Exception as exc:
                _log.error("xmpp process error: %r", exc)

            if not self.conn.isConnected():
                self.xmpp_reconnect()


    #######
    ## XMPP stuff
    #######

    def register_handlers(self):
        self.conn.RegisterHandler('message', self.xmpp_message)
        self.conn.RegisterHandler('presence', self.xmpp_presence)
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
                self.conn.send(Error(event, ERR_ITEM_NOT_FOUND))
                raise NodeProcessed
        else:
            self.conn.send(Error(event, ERR_JID_MALFORMED))
            raise NodeProcessed

    def xmpp_presence(self, con, event):
        # Add ACL support
        fromjid = event.getFrom()
        ev_type = event.getType()
        to = event.getTo()
        if ev_type in ('subscribe', 'subscribed', 'unsubscribe', 'unsubscribed', 'unavailable'):
            self.conn.send(Presence(to=fromjid, frm=to, typ=ev_type))
        elif ev_type == 'probe':
            self.conn.send(Presence(to=fromjid, frm=to))
        elif ev_type == 'error':
            return
        else:
            self.conn.send(Presence(to=fromjid, frm=to))

    def xmpp_connect(self):
        connected = self.conn.connect((
            self.config.xmpp_main_server, self.config.xmpp_component_port))
        _log.info("connected: %r", connected)
        while not connected:
            time.sleep(5)
            connected = self.conn.connect((
                self.config.xmpp_main_server, self.config.xmpp_component_port))
            _log.info("connected: %r", connected)
        self.register_handlers()
        _log.info("trying auth")
        connected = self.conn.auth(
            self.config.xmpp_sasl_username or self.config.jid,
            self.config.xmpp_secret)
        _log.info("auth return: %r", connected)
        return connected

    def xmpp_reconnect(self):
        ## XXXX: ...Augh.
        time.sleep(5)
        if not self.conn.reconnectAndReauth():
            time.sleep(5)
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
            self.conn.send(Error(event, ERR_ITEM_NOT_FOUND))
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
        self.message_callback(**msg_kwa)


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
