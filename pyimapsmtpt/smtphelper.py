# coding: utf8

## conjdig-ish
_patch_smtp_logging = True

## ...
import logging
import functools
import smtplib
import email
import email.message
import copy


_log = logging.getLogger(__name__)
_dumpall_log_level = 2
log = functools.partial(_log.log, _dumpall_log_level)


#######
## Stuff for smtp logging patching
#######


## http://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


_smtp_logging_patched = False


#######
## ...
#######


def get_smtpcli(config):

    ## Hacks
    global _smtp_logging_patched
    if _patch_smtp_logging and not _smtp_logging_patched:
        _smtp_logging_patched = True
        if logging.getLogger().level <= logging.DEBUG:
            smtplib.SMTP.debuglevel = 2
        smtplib.stderr = StreamToLogger(
            logging.getLogger('SMTP'),
            log_level=_dumpall_log_level)

    ## TODO?: more persistent connections? memoize & reconnects?
    log("SMTP connecting")
    smtpcli = smtplib.SMTP(config.smtp_server)
    smtpcli.set_debuglevel(1)
    log("SMTP EHLO")
    smtpcli.ehlo()
    if config.smtp_starttls:
        log("SMTP STARTTLS")
        smtpcli.starttls()

    log("SMTP login")
    smtpcli.login(config.smtp_username, config.smtp_password)
    return smtpcli


def send_email(config, to, message, from_=None, auto_headers=None, _copy=True):
    from_ = from_ or config.email_address
    if not hasattr(to, '__iter__'):
        to = [to]

    if not isinstance(message, email.message.Message):
        ## Probably better to do this for any incoming text:
        message = email.message_from_string(message)

    if auto_headers is None:  ## No info, figure out
        if _copy:
            message = copy.deepcopy(message)
        ## At least make sure there's no newlines in the values:
        _escape_value = lambda s: s.replace('\n', r'\n')

        ## Apparently, this will handle well even a message without headers and '\n\n'
        if not message['to'] and not message['envelope-to']:
            message['To'] = ', '.join(to)
        if not message['from']:
            message['From'] = from_
        ## Subject?..

    message_str = message.as_string()
    smtpcli = get_smtpcli(config)
    log("SMTP sending from %r to %r:    %r", from_, to, message_str)
    res = smtpcli.sendmail(from_, to, message_str)
    log("SMTP close")
    smtpcli.close()
    return message, res


class SMTPHelper(object):
    def __init__(self, config, _manager=None):
        self.config = config
        self._manager = _manager

    def send_email(self, to, message, from_=None, **kwa):
        return send_email(self.config, to, message, from_=from_, **kwa)


def main():
    try:
        import pyaux.runlib
        pyaux.runlib.init_logging(level=1)
    except Exception:
        logging.basicConfig(level=1)
    from pyimapsmtpt.confloader import get_config
    config = get_config()
    send_email(config, 'hoverhell@gmail.com', 'Subject: test\n\nsubj.')


if __name__ == '__main__':
    main()
