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
# import signal
import sys
# import time
import logging

from .confloader import get_config
from .common import configure_logging, config_email_utf8, EventProcessed
from .convertlayer import MailJabberLayer
from .smtphelper import SMTPHelper
from .xmpptransport import Transport
from .imapcli import IMAPCli


_log = logging.getLogger(__name__)


class PyIMAPSMTPtWorker(object):

    layer = transport = imapc = None

    def __init__(self, config=None):
        if config is None:
            config = get_config()

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

    def post_run(self, stop_children=True):
        if stop_children:
            self.stop_children()
        if self.config.pidfile:
            os.unlink(self.config.pidfile)

    def setup_signals(self):
        signal.signal(signal.SIGINT, self.sighandler)
        signal.signal(signal.SIGTERM, self.sighandler)

    def sighandler(self):
        if self.transport is not None:
            self.transport.sighandler()

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
        self.layer.email_to_xmpp(msg, **kwa)

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
        gevent.joinall(self.children.values())

    def stop_children():
        gevent.killall(self.children.values())
        if self.imapc is not None:
            self.imapc.stop_event.set()
        if self.transport is not None:
            self.transport.online = False

def main():
    config = get_config()

    worker = PyIMAPSMTPtWorker()

    ## Probably should not be used
    if config.auto_self_restart:
        sys.stderr.write("WARNING: Self-restarting\n")
        sys.stderr.flush()
        args = [sys.executable] + sys.argv
        if os.name == 'nt':
            args = ["\"%s\"" % (a,) for a in args]
        if config.dumpProtocol:
            _log.info("Self-restarting with %r %r", sys.executable, args)
        os.execv(sys.executable, args)


if __name__ == '__main__':
    main()
