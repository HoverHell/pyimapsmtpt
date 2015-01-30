# coding: utf8

import logging
import functools
import smtplib
import email
import email.message


_log = logging.getLogger(__name__)
log = functools.partial(_log.log, 2)


def get_smtpcli(config):
    ## TODO?: more persistent connections? memoize & reconnects?
    log("SMTP connecting")
    smtpcli = smtplib.SMTP(config.smtp_server)
    log("SMTP EHLO")
    smtpcli.ehlo()
    if config.smtp_starttls:
        log("SMTP STARTTLS")
        smtpcli.starttls()

    log("SMTP login")
    smtpcli.login(config.smtp_username, config.smtp_password)
    return smtpcli


def send_email(config, to, message, from_=None, auto_headers=None):
    from_ = from_ or config.email_address
    if not hasattr(to, '__iter__'):
        to = [to]

    if not isinstance(message, email.message.Message):
        ## Probably better to do this for any incoming text:
        message = email.message_from_string(message)

    if auto_headers is None:  ## No info, figure out
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
    smtpcli.sendmail(from_, to, message_str)
    log("SMTP close")
    smtpcli.close()


if __name__ == '__main__':
    logging.basicConfig(level=1)
    import config
    send_email(config, 'hoverhell@gmail.com', 'Subject: test\n\nsubj.')
