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
import os
# import signal
import sys
# import time
import logging

from .confloader import get_config
from .common import configure_logging, config_email_utf8
from .convertlayer import MailJabberLayer
from .smtphelper import SMTPHelper


_log = logging.getLogger(__name__)


class PyIMAPSMTPtWorker(object):

    layer = transport = imapc = None

    def __init__(self, config=None):
        if config is None:
            config = get_config()

        self.config = config
        raise Exception("TODO")

    def pre_run(self, instantiate=True):
        config_email_utf8()

        if self.config.pidfile:
            with open(self.config.pidfile, 'wb') as f:
                f.write(str(os.getpid()))

        configure_logging(self.config)

        if instantiate:
            self._instantiate()

    def post_run(self):
        if self.config.pidfile:
            os.unlink(self.config.pidfile)

    def _instantiate(self):
        self.imapc = None  ## TODO
        self.transport = None  ## TODO
        self.layer = MailJabberLayer(
            config=self.config, xmpp_sink=self.xmpp_sink,
            smtp_sink=self.smtp_sink, _manager=self)
        self.smtp = SMTPHelper(config=self.config, _manager=self)

    def xmpp_sink(self, message_kwa, **kwa):
        raise Exception("TODO")

    def smtp_sink(self, to, msg, frm=None, **kwa):
        raise Exception("TODO")


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
