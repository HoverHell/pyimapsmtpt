#!/usr/bin/env python
# coding: utf8
"""
The Main Daemon file (the glue).

Subcomponents:
  confloader  # config source
  imapcli  # imap connection; email message source
  xmpptransport  # xmpp message source; xmpp sink
  convertlayer  # email <-> xmpp message conversion
  smtphelper  # email message sink

  imapcli -> convertlayer -> xmpptransport
  xmpptransport -> convertlayer -> smtphelper
"""


## Okay, that should make it easier-
import gevent.monkey
gevent.monkey.patch_all()
import gevent

## ...

import os
import signal
import sys
# import time
import logging
from threading import Event

from .confloader import get_config
from .common import configure_logging, config_email_utf8, EventProcessed
from .convertlayer import MailJabberLayer
from .smtphelper import SMTPHelper
from .xmpptransport import Transport
from .imapcli import IMAPCli


_log = logging.getLogger(__name__)


class PyIMAPSMTPtWorker(object):

    layer = transport = imapc = None

    joinall_timeout = 0.1

    def __init__(self, config=None):
        if config is None:
            config = get_config()

        self.stop_event = Event()
        self.config = config
        self.children = {}

    def pre_run(self, instantiate=True):
        config_email_utf8()

        self.setup_signals()

        if self.config.pidfile:
            with open(self.config.pidfile, 'wb') as f:
                f.write(str(os.getpid()))

        configure_logging(self.config)

        if instantiate:
            self._instantiate()

    def setup_signals(self):
        signal.signal(signal.SIGINT, self.sighandler)
        signal.signal(signal.SIGTERM, self.sighandler)

    def sighandler(self, *ar, **kwa):
        _log.info("sighandler called with %r %r", ar, kwa)
        if self.transport is not None:
            _log.info("Calling transport sighandler")
            self.transport.sighandler(*ar, **kwa)
        _log.info("Setting the stop event")
        self.stop_event.set()

    def _instantiate(self):
        self.layer = MailJabberLayer(
            config=self.config, xmpp_sink=self.xmpp_sink,
            smtp_sink=self.smtp_sink, _manager=self)
        self.smtp = SMTPHelper(
            config=self.config, _manager=self)
        self.imapc = IMAPCli(
            config=self.config, mail_callback=self.email_source)
        self.transport = Transport(
            config=self.config,
            message_callback=self.xmpp_source)

    def xmpp_source(self, msg_data, **kwa):
        ## xmpptransport -> convertlayer
        self.layer.xmpp_to_smtp(msg_data, **kwa)

    def email_source(self, msg, **kwa):
        _try_with_pm(lambda: self.layer.email_to_xmpp(msg, **kwa))

    def xmpp_sink(self, msg_data, **kwa):
        ## [imapcli -> | xmpptransport -> ] convertlayer -> xmpptransport,
        ## from-email messages and error messages
        return self.transport.send_message_data(msg_data, **kwa)

    def smtp_sink(self, to, msg, frm=None, **kwa):
        ## [xmpptransport -> ] convertlayer -> smtphelper
        fkwa = {k: v for k, v in kwa.items() if k in ('auto_headers',)}
        return self.smtp.send_email(
            to, msg, from_=frm,
            _copy=False, **fkwa)

    def run(self, pre_run=True, post_run=True):
        if pre_run:
            self.pre_run()
        try:
            self.run_loop()
        finally:
            self.post_run()

    def run_loop(self):
        # self.layer does not have a loop
        # self.smtp does not have a loop (but maybe should)
        child = gevent.spawn(self.imapc.run)
        self.children['imapc'] = child
        child = gevent.spawn(self.transport.run)
        self.children['transport'] = child
        ## The 'loop'
        _log.info("Waiting for the stop event")
        self.stop_event.wait()
        ## ...
        self.stop_children()
        _log.info("Waiting %rs for the children to quit", self.joinall_timeout)
        gevent.joinall(self.children.values(), timeout=self.joinall_timeout)

    def post_run(self, kill_children=True):
        if kill_children:
            self.kill_children()
        if self.config.pidfile:
            os.unlink(self.config.pidfile)

    def stop_children(self):
        _log.info("Stopping children")
        if self.imapc is not None:
            _log.info("Setting the imapc stop event")
            self.imapc.stop_event.set()
        if self.transport is not None:
            _log.info("Setting the transport stop event")
            self.transport.online = False

    def kill_children(self):
        _log.info("Killing %d children", len(self.children))
        gevent.killall(self.children.values())


def _try_with_pm(_func_to_try_with_pm, *ar, **kwa):
    """ Debug-helper to call ipdb.pm in case of an unhandled exception in the
    function"""
    try:
        return _func_to_try_with_pm(*ar, **kwa)
    except Exception:
        _, _, sys.last_traceback = sys.exc_info()
        import traceback; traceback.print_exc()
        import ipdb; ipdb.pm()


def main():
    if 'mark_all' in sys.argv:
        config = get_config()
        configure_logging(config)
        imapcli = IMAPCli(config=config)
        imapcli.mark_all_as_seen()
    worker = PyIMAPSMTPtWorker()
    worker.run()


if __name__ == '__main__':
    main()
