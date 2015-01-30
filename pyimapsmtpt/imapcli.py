#!/usr/bin/env python
# coding: utf8


#######
## Monkeys running wild
# import gevent.monkey
# gevent.monkey.patch_all()
## Could be sufficient, though:
# gevent.monkey.patch_socket()
## Or maybe can do this without gevent


#######

import sys
import signal
import logging
import email
import imaplib
import imapclient
from threading import Event

from .common import to_bytes

_log = logging.getLogger('pyimaptst_%s' % (client_id,))


seen_flag = r'Seen_by_%s' % (client_id,)


#######
## HAX: fix imapclient's fault
## Apparently, mere presence of 'imaplib2' makes imapclient use it in place of
## imaplib; however, a couple of things that are required of imaplib are not
## present in imaplib2; so, put them there.
#######

def _fix_imapclient_imaplib2():
    try:
        import imaplib2
    except Exception:
        return
    attrs = ('InternalDate', 'Mon2num')
    for attr in attrs:
        val = getattr(imaplib, attr)
        setattr(imaplib2, attr, val)

_fix_imapclient_imaplib2()


#######
## Monkey-add the client id to the imapclient logging
#######
def _imaplib_add_id_logging(logger, cls=imaplib.IMAP4_SSL):
    def _read_dbg(self, size):
        name = getattr(self, '_x_name', '')
        res = self.file.read(size)
        logger.debug("SOCKET(%r) read: %r", name, res)
        return res

    def _readline_dbg(self):
        name = getattr(self, '_x_name', '')
        res = self.file.readline()
        logger.debug("SOCKET(%r) readline: %r", name, res)
        return res

    _send_orig = getattr(cls, '_send_orig', cls.send)
    def _send_dbg(self, data):
        name = getattr(self, '_x_name', '')
        logger.debug("SOCKET(%r) send: %r", name, data)
        _send_orig(self, data)

    cls._send_orig = _send_orig
    cls.send = _send_dbg
    cls.read = _read_dbg
    cls.readline = _readline_dbg




def config_to_clikwa(config):
    # client_id = 'pyit1'
    server = config.imap_server
    if ':' in server:
        server, port = server.split(':', 1)
        port = int(port)
    else:
        port = getattr(config, 'imap_port', None)
        if port is None:
            port = 993  ## The default, pretty much

    cli_kwa = dict(
        username=config.imap_username,
        password=config.imap_password,
        server=server,
        port=port,
        ssl=config.imap_ssl,
    )
    return cli_kwa

    
def get_imapcli(username, password, server, port=None, cls=imapclient.IMAPClient, **kwa):
    imapcli = cls(server, port, **kwa)

    lr = imapcli.login(username, password)
    _log.debug("IMAP Login res: %r", lr)

    return imapcli


class Worker(object):

    ## TODO: cleanup
    sync_msg_limit = 3  ## NOTE.
    ## Timeout for the IDLE command
    ## 28 minutes, slightly below the RFC-recommended-maximum of 29 minutes
    idle_timeout = 28 * 60
    mailbox = 'INBOX'
    retry_working = None
    working = None
    cli = idle_cli = mark_all_cli = None

    def __init__(self, config, cli_kwa=None):
        self.config = config
        if cli_kwa is None:
            cli_kwa = config_to_clikwa(config)
        self.cli_kwa = cli_kwa

        self.stop_event = Event()
        self.events_pending = Event()

        self.log = _log.getChild('Worker')

    def mark_all_as_seen(self, debug=True):
        cli = self.get_client(name='mark_all_cli')
        return self.sync(limit=None, process=False, debug=debug)

    def get_client(self, cli_kwa=None, name='cli', cached=False):
        """ ...

        'name' is the name of the attribute on `self` it will be saved on.
        """
        if cached:
            cli = getattr(self, name, None)
            if cli is not None:
                self.log.debug("get_client(%r): cached", name)
                return cli

        cli_kwa = cli_kwa or self.cli_kwa
        self.log.debug("get_client(%r): creating", name)
        cli = get_imapcli(**cli_kwa)

        ## Add the client name to the client for logging (for
        ## _imaplib_add_id_logging)
        ## NOTE: get_imapcli will do a bit of socket-talking before the
        ## name is set, resulting in `SOCKET('')`
        cli._x_name = name
        cli._imap._x_name = name

        ## NOTE: done regardless of the 'cached' param.
        setattr(self, name, cli)

        resp = cli.select_folder(
            self.mailbox,
            ## We are writing flags for no-local-state, alas.
            # readonly=1,
        )
        self.log.debug("imapcli(%r).select_folder: %r", name, resp)
        return cli

    def run_with_retry(self):
        self.pre_run()
        self.retry_working = True
        while self.retry_working:
            try:
                self.run(pre_run=False)
            except imaplib.IMAP4.abort as exc:
                ## `raise self.abort('socket error: EOF')`
                ## In practice, that exception should've'been caught in the imapclient.py
                self.log.exception("run() error 'abort': %r", exc)
                self.log.info("Re-`run()`ning")
            except Exception as exc:
                self.log.exception("run() error: %r", exc)
                self.log.info("Re-`run()`ning")

    def pre_run(self, setup_signals=True, sockdbg=True):
        if setup_signals:
            self.setup_signals()
        ## From pymailt. Not sure what it should do.
        email.Charset.add_charset('utf-8', email.Charset.SHORTEST, None, None)
        if sockdbg:
            _imaplib_add_id_logging(self.log)

    def run(self, pre_run=True):
        if pre_run:
            self.pre_run()
        cli = self.get_client()
        self.get_client(name='idle_cli')
        try:
            # self.sync()  ## Not necessary
            return self.run_loop()
        finally:
            self.log.debug("run() done")
            # self.cli.close()
            # cli.logout()
            # self.log.debug("imapcli close done")

    def setup_signals(self):
        """ Set the sigint handler to the sigterm handler so that C-c in
        the terminal works same as killing the daemon """
        handler = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, handler)

        def ipdb_on_sig(signal, frame):
            import ipdb
            ipdb.set_trace()

        # signal.signal(ipdb_on_sig, handler)

    def run_loop(self):
        self.working = True
        while self.working:
            if self.stop_event.isSet():
                return

            ## XXX: is extra reconnection handling necessary?
            self.work()

    def work(self):
        """ Synopsis:
        (re)start the IDLE (on the `idle_cli`). Sync (on the `cli`). Check the
        IDLE results (wait for them).
        """
        self.log.info("work()")
        idle_cli = self.get_client(name='idle_cli', cached=True)
        self.log.info("work: idle_cli.idle()")
        idle_cli.idle()
        self.sync()  ## Should use self.cli
        self.log.info('idle_check for %r', self.idle_timeout)
        resp = idle_cli.idle_check(timeout=self.idle_timeout)
        self.log.debug('got idle resp: %r', resp)
        resp = idle_cli.idle_done()
        self.log.debug('got idle_done resp: %r', resp)

    def sync(self, limit=True, process=True, cli=None, debug=False):
        """ ...

        NOTE: `limit=None, process=False` is used for mark_all_as_seen
        """
        self.log.info("sync()")
        cli = cli or self.get_client(name='cli', cached=True)
        ## TODO: filter out by internaldate > now - some_max_val ( SINCE ... )
        msgids = cli.search('(UNKEYWORD %s)' % (seen_flag,))
        ## Hopefully, the newest will be the last in the list.
        assert msgids == sorted(msgids)
        msgids = list(reversed(msgids))
        if limit is True:
            msgids = msgids[:self.sync_msg_limit]  ## NOTE
        elif limit:
            msgids = msgids[:limit]

        dbgres = []

        messages = cli.fetch(msgids, ['INTERNALDATE', 'FLAGS', 'RFC822'])
        for msgid in msgids:
            self.log.debug("Message %r", msgid)
            try:
                message = messages[msgid]
                msg_content = message['RFC822']
                if process:
                    self.handle_msg(
                        msg_content, msgid=msgid, msgids=msgids, message=message)
                ## NOTE: if handle_msg excepts, this will not be done, this way.
                resp = cli.add_flags(msgid, seen_flag)
                if debug:
                    dbgres.append(dict(msgid=msgid, message=message, flag_resp=resp))
                self.log.debug("add_flags resp: %r", resp)
            except Exception as exc:
                self.log.exception("Error handling msg: %r", exc)
        return dbgres

    def handle_msg(self, msg_content, **kwa):
        ## Storytime.
        ## Apparently, IMAPClient decodes the message whenever possible;
        ## however, email.message_from_string puts it into StringIO which
        ## expects bytes() and thus tries to encode the unicode string into
        ## ascii and thus fails.
        msg_content = to_bytes(msg_content)
        msg = email.message_from_string(msg_content)

        ## XXXXXXXXXXXXXXXX: TODO.
        print repr(msg_content)[:300]


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    worker = Worker(cli_kwa)
    if args and 'mark_all' in args:
        return worker.mark_all_as_read()

    # worker.run()
    worker.run_with_retry()

    return worker


if __name__ == '__main__':
    try:
        from pyaux.runlib import init_logging
        init_logging(
            level=1,
        )
        main()
    except Exception:
        _, _, sys.last_traceback = sys.exc_info()
        import traceback; traceback.print_exc()
        import ipdb
        ipdb.pm()
