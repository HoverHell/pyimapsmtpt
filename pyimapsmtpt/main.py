#!/usr/bin/env python
# coding: utf8
"""
The Main Daemon file.

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
import signal
import sys
import time
import logging

from .common import get_config, configure_logging, config_email_utf8
from .convertlayer import MailJabberLayer


_log = logging.getLogger(__name__)


def PyIMAPSMTPtWorker(object):
    def __init__(self, config=None):
        if config is None:
            config = get_config()

        self.config = config
        pass

    def pre_run():
        if self.config.pidfile:
            with open(config.pidfile, 'wb') as f:
                f.write(str(os.getpid()))

        configure_logging(self.config)

    def post_run():
        if self.config.pidfile:
            if config.pidfile:
                os.unlink(config.pidfile)


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
