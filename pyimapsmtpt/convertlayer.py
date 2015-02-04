# coding: utf8

import re
from copy import deepcopy
import logging
import email.message
# pylint: disable=no-name-in-module
# pylint: disable=import-error
from email.MIMEText import MIMEText
from email.Header import decode_header
from email.Utils import parseaddr as email_parseaddr
# pylint: enable=import-error
# pylint: enable=no-name-in-module

from .common import EventProcessed, get_html2text


_log = logging.getLogger(__name__)


def msg_get_header(msg, name):
    """ Get a processed header from an email.Message `msg` """
    val, charset = decode_header(msg[name])[0]
    if charset:
        val = unicode(val, charset, 'replace')
    return val


def extract_headers_from_body(body, preparse_headers):
    """ Helper to allow for headers to be specified within the body.

    Either raises a ValueError if the body is likely a mistake, returns None
    if no headers can be parsed, or return (body, headers) if headers were
    extracted.
    """
    if not preparse_headers:
        return

    body_parts = body.strip().split('\n\n', 1)
    if len(body_parts) == 1:
        return

    body_headers, body_body = body_parts

    required_header = preparse_headers[0]

    body_header_lines = [v.strip() for v in body_headers.split('\n')]
    body_header_lines = [v for v in body_header_lines if v]

    if not body_header_lines:  ## No non-empty lines, nothing to process
        return

    ## For getting a particular one from the whole text:
    # rex = r'(?im)^%s: (.*)$' % (re.escape(name),)

    rex = r'^([^:]+): (.*)$'
    body_header_matches = [
        (line, re.match(rex, line))
        for line in body_header_lines]

    if not all([match for line, match in body_header_matches]):
        ## Header is not headers-only; skip
        return None

    ## NOTE: shouldn't be empty (because of the check above)
    first_line, first_match = body_header_matches[0]
    ## NOTE: match should match because of the check above
    first_header_name, first_header_value = first_match.groups()
    if first_header_name.strip().lower() != required_header:
        raise ValueError((
            "Body seems to contain headers but first header is %r instead"
            " of the required %r") % (first_header_name, required_header))

    headers_list = [match.groups() for line, match in body_header_matches]
    headers = {name.lower(): value for name, value in headers_list}

    disallowed_headers = set(headers) - set(preparse_headers)
    if disallowed_headers:
        disallowed_headers = [
            name for name, value in headers_list
            if name.lower() not in preparse_headers]
        raise ValueError((
            "Body seems to contains headers that are not allowed: %s") % (
                ', '.join(repr(name) for name in disallowed_headers),))

    return body_body, headers


class MailJabberLayer(object):
    """ Logic of converting between email messages and xmpp messages both ways """

    def __init__(self, config, xmpp_sink, smtp_sink, _manager=None):
        """ ...

        :param xmpp_sink: function(dict) that accepts messages to be sent over XMPP
        """
        self.config = config
        self.xmpp_sink = xmpp_sink
        self.smtp_sink = smtp_sink
        self._manager = _manager

    def xmpp_to_smtp(self, msg_data, **kwa):
        """ ...

        callbacks self.smtp_sink
        raises EventProcessed
        """
        ## No text - not our business
        if not msg_data['body']:
            return

        jfrom = msg_data['frm']
        jto = msg_data['to']

        mto, headers = self.jto_to_mto(jto, msg_data=msg_data)
        mfrom = self.jfrom_to_mfrom(jfrom, msg_data=msg_data)

        msg_data, headers2 = self.preprocess_xmpp_incoming(
            msg_data, copy=False, headers=headers)
        headers.update(headers2)

        charset = 'utf-8'
        body_bytes = msg_data['body'].encode(charset, 'replace')
        emsg = MIMEText(body_bytes, 'plain', charset)
        subject = msg_data.get('subject')
        if subject:
            emsg['Subject'] = subject
        emsg['From'] = mfrom
        emsg['To'] = mto
        for k, v in headers.items():
            emsg[k] = v

        self.smtp_sink(mto, emsg, frm=mfrom, _msg_data=msg_data, _layer=self)

    def preprocess_xmpp_incoming(self, msg_data, copy=True, **kwa):
        if copy:
            msg_data = deepcopy(msg_data)

        try:
            res = extract_headers_from_body(
                msg_data['body'], self.config.preparse_headers)
        except ValueError as exc:
            self.reply_with_error(exc.args[0], msg_data)  ## raises EventProcessed

        if res is None:
            return msg_data, {}

        res_body, res_headers = res[0], res[1]
        msg_data['body'] = res_body
        return msg_data, res_headers

    def email_to_xmpp(self, msg):
        if not isinstance(msg, email.message.Message):
            _log.warning("`msg` is not an email.message.Message: %r,  %r", type(msg), msg)
        # msg = email.message_from_string(msg)

        if self.config.dump_protocol:
            _log.info('RECEIVING: %r', msg.as_string())

        mfrom = email_parseaddr(msg['From'])[1]
        ## XXXX: re-check this
        mto_base = msg['Envelope-To'] or msg['To']
        mto = email_parseaddr(mto_base)[1]

        ## XXXX/TODO: use `Message-id` or similar for resource (and
        ##   parse it in incoming messages)? Might have to also send
        ##   status updates for those.
        jfrom = self.mfrom_to_jfrom(mfrom, msg=msg)
        jto = self.mto_to_jto(mto, msg=msg)

        subject = msg_get_header(msg, 'subject')

        jmsg_data = dict(to=jto, frm=jfrom, subject=subject)

        body_dict = self.message_to_body(msg)
        jmsg_data.update(body_dict)

        jmsg_data = self.postprocess_xmpp_outgoing(
            jmsg_data, msg=msg, copy=False)

        self.xmpp_sink(jmsg_data, _email_msg=msg, _layer=self)

    def message_to_body(self, top_msg, **kwa):
        """ Get a suitable message body from the whole email message.

        Returns a `dict(body=body)` """
        log = _log.debug

        log("processing email message for body %s", repr(top_msg)[:60])
        msg_plain = msg_html = None
        submessages = top_msg.get_payload()
        for submessage in submessages:
            if not submessage:
                continue
            ctype = submessage.get_content_type()
            # NOTE: 'startswith' might be nore correct, but this should
            # be okay too
            if 'text/html' in ctype:
                log("msg: found text/html")
                msg_html = submessage
            elif 'text/plain' in ctype:
                log("msg: found text/plain")
                msg_plain = submessage
            else:
                log("msg: unprocessed ctype %r", ctype)

        if self.config.preferred_format == 'plaintext':
            log("msg: preferring plaintext")
            msg = msg_plain or msg_html or top_msg  # first whatever
        else:  # html2text or html
            log("msg: preferring html")
            msg = msg_html or msg_plain or top_msg
            log("msg: resulting content_type is %r", msg.get_content_type())

        charset = msg.get_charsets('utf-8')[0]
        body = msg.get_payload(None, True)
        body = unicode(body, charset, 'replace')
        # check for `msg.get_content_subtype() == 'html'` instead?
        if 'text/html' in msg.get_content_type():
            if self.config.preferred_format != 'html':
                log("msg: doing html2text")
                html2text = get_html2text(self.config)
                body = html2text(body)
            # TODO: else compose an XMPP-HTML message? Will require a
            # complicated preprocessor like bs4 though

        return dict(body=body)

    def postprocess_xmpp_outgoing(self, jmsg_data, msg, copy=True, **kwa):
        if copy:
            jmsg_data = deepcopy(jmsg_data)
        prepend_headers = set(self.config.prepend_headers)
        body = jmsg_data['body']
        prepend = []
        force_prepend = False
        if 'to' in prepend_headers:
            force_prepend = True
            to_ = msg_get_header(msg, 'to')
            envelope_to = msg_get_header(msg, 'envelope-to')
            ## Only prepend if it's not the current recipient, basically.
            if ('_always_to' not in prepend_headers
                    and envelope_to and to_ != envelope_to):
                prepend.append(u'To: %s' % (to_,))
        if 'from' in prepend_headers:
            prepend.append(u'From: %s' % (msg_get_header(msg, 'from'),))
        if 'subject' in prepend_headers:
            subject = jmsg_data.pop('subject', None)
            subject = subject or msg_get_header(msg, 'subject')
            prepend.append(u'Subject: %s' % (subject,))

        if prepend or force_prepend:
            body = '%s\n\n%s' % ('\n'.join(prepend), body)

        jmsg_data['body'] = body
        return jmsg_data

    def mfrom_to_jfrom(self, mfrom, msg=None, **kwa):
        """ Overridable method for converting email's 'From' to xmpp's 'from'
        """
        ## The Transport way: email@transport/message-id
        res = '%s@%s' % (mfrom.replace('@', '%'), self.config.xmpp_component_jid)
        if msg is not None:
            ## XXXX: in a better case, this would be a more consistent
            ## conversation-id with a storage for conversation_id <->
            ## last_message_id
            res = '%s/%s' % (res, msg['Message-ID'])
        return res

    def jto_to_mto(self, jto, msg_data=None, **kwa):
        """ ...

        :param jto: dict with 'node', 'domain', 'resource'

        returns: (mto, extra_email_headers)
        """
        ## The transport way: email@transport/message-id
        mto = jto['node'].replace('%', '@')
        ## TODO?: e-mail conversation tracking (reply-to):
        ## support message-id in the resource
        ## (make sure to set it in a validable way, e.g. '.../msgid-%(base64(message_id))')
        ## see also `self.mfrom_to_jfrom`
        return mto, {}

    def mto_to_jto(self, mto, **kwa):
        """ Overridable method for converting email's 'To' to xmpp's 'to' """
        ## Currently, only one user is ever used.
        return self.config.main_jid
        ## Static-mapping way:
        # tosplit = mto.split('@', 1)
        # jto = None
        # for mapping in self.mappings:
        #     if mapping[1] == tosplit[1]:
        #         jto = '%s@%s' % (tosplit [0], mapping[0])
        # if not jto:
        #     jto = self.config.jto_fallback
        # return jto

    def jfrom_to_mfrom(self, jfrom, msg_data=None, **kwa):
        ## Currently, only one user is ever used.
        return self.config.main_jid
        ## Static-mapping way:
        # node, domain = jfrom['node'], jfrom['domain']
        # fromsplit = jfrom['node'], jfrom['domain']
        # mfrom = None
        # for jdomain, mdomain in self.mappings:
        #     if jdomain == domain:
        #         mfrom = '%s@%s' % (node, mdomain)
        # if not mfrom:
        #     self.jabber.send(Error(event, ERR_REGISTRATION_REQUIRED))
        #     return

    def reply_with_error(self, error, msg_data):
        ## TODO: correct XMPP error message (requires error events support
        ## from the sink)
        body = 'ERROR: %s' % (error,)
        jmsg_data = dict(to=msg_data['frm'], frm=msg_data['to'], body=body)
        self.xmpp_sink(jmsg_data, _layer=self)
        raise EventProcessed("replied with error")


## TODO: The bot-version of the MailJabberLayer (probably dependent on
## resources handling, and with 'from' in config.prepend_headers)


def xmpp_sink_example(message_kwa, **kwa):
    ## TODO: support error events
    assert 'to' in message_kwa
    assert 'frm' in message_kwa
    assert 'body' in message_kwa
    from xmpp.browser import Message
    msg = Message(**message_kwa)
    kwa['xmpp_transport'].conn.send(msg)


def smtp_sink_example(to, msg, frm=None, **kwa):
    import smtplib
    self = kwa['_layer']
    try:
        if self.config.dump_protocol:
            _log.info('SENDING: %r', msg.as_string())
        mailserver = smtplib.SMTP(self.config.smtpServer)
        if self.config.dump_protocol:
            mailserver.set_debuglevel(1)
        mailserver.sendmail(frm, to, msg.as_string())
        mailserver.quit()
    except Exception as exc:
        _log.exception("SMTP sink error: %r", exc)
        # self.jabber.send(Error(event, ERR_RECIPIENT_UNAVAILABLE))


def test():
    import os
    os.environ['NO_LOCAL_CONF_REQUIRED'] = '1'
    from .confloader import get_config
    config = get_config()
    ## TODO.
