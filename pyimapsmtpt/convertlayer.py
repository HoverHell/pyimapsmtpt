# coding: utf8

from email.MIMEText import MIMEText
from email.Header import decode_header


class MailJabberLayer(object):
    """ Logic of converting between email messages and xmpp messages both ways
    """

    def __init__(self, config=None):
        pass

    def xmpp_to_smtp(self, event, connection=None):
        ev_type = event.getType()
        fromjid = event.getFrom()
        fromstripped = fromjid.getStripped()
        to = event.getTo()

        ## TODO? skip 'error' messages?
        ##  (example: recipient not found, `<message from='…'
        ##  to='…@pymailt.…' type='error' id='1'>…<error code='503'
        ##  type='cancel'>…<service-unavailable
        ##  xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>…`)
        if ev_type == 'error':
            _log.error("Error XMPP message: %r, %r", event, str(event))
            return

        try:
            if event.getSubject.strip() == '':
                event.setSubject(None)
        except AttributeError:
            pass
        if event.getBody() == None:
            return

        if to.getNode() == '':
            self.jabber.send(Error(event, ERR_ITEM_NOT_FOUND))
            return
        mto = to.getNode().replace('%', '@')

        fromsplit = fromstripped.split('@', 1)
        mfrom = None
        for mapping in self.mappings:
            if mapping[0] == fromsplit[1]:
                mfrom = '%s@%s' % (fromsplit[0], mapping[1])

        if not mfrom:
            self.jabber.send(Error(event, ERR_REGISTRATION_REQUIRED))
            return

        subject = event.getSubject()
        body = event.getBody()
        ## TODO: Make it possible to ender subject as a part of message
        ##   (e.g.  `Sobject: ...` in the first line)
        ## TODO?: e-mail conversation tracking (reply-to)

        charset = 'utf-8'
        body = body.encode(charset, 'replace')

        msg = MIMEText(body, 'plain', charset)
        if subject:
            msg['Subject'] = subject
        msg['From'] = mfrom
        msg['To'] = mto

        ## XXXXXXXXXXXXXXXXXXXXXXXXXXXX
        try:
            if self.config.dump_protocol:
                _log.info('SENDING: %r', msg.as_string())
            mailserver = smtplib.SMTP(self.config.smtpServer)
            if self.config.dump_protocol:
                mailserver.set_debuglevel(1)
            mailserver.sendmail(mfrom, mto, msg.as_string())
            mailserver.quit()
        except:
            logError()
            self.jabber.send(Error(event, ERR_RECIPIENT_UNAVAILABLE))

    def email_to_xmpp(self, msg):
        # msg = email.message_from_file(fp)

        if self.config.dump_protocol:
            _log.info('RECEIVING: %r', msg.as_string())

        mfrom = email.Utils.parseaddr(msg['From'])[1]
        ## XXXX: re-check this
        mto_base = msg['Envelope-To'] or msg['To']
        mto = email.Utils.parseaddr(mto_base)[1]

        ## XXXX/TODO: use `Message-id` or similar for resource (and
        ##   parse it in incoming messages)? Might have to also send
        ##   status updates for those.
        jfrom = '%s@%s' % (mfrom.replace('@', '%'), self.jid)

        tosplit = mto.split('@', 1)
        jto = None
        for mapping in self.mappings:
            #break  ## XXXXXX: hax: send everything to one place.
            if mapping[1] == tosplit[1]:
                jto = '%s@%s' % (tosplit [0], mapping[0])

        if not jto:
            ## XXX: actual problem is in, e.g., maillists mail, which is
            ##   sent to the maillist and not to the recipient. This is
            ##   more like a temporary haxfix for that.
            jto = self.jto_fallback
            if not jto:
                continue

        (subject, charset) = decode_header(msg['Subject'])[0]
        if charset:
            subject = unicode(subject, charset, 'replace')

        log = _log.debug

        log("processing email message %s", repr(msg)[:60])
        msg_plain = msg_html = None
        submessages = msg.get_payload()
        for submessage in submessages:
            # msg = msg.get_payload(0)
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
                log("msg: unprocessed ctype %r" % (ctype,))

        if config.preferredFormat == 'plaintext':
            log("msg: preferring plaintext")
            msg = msg_plain or msg_html or msg  # first whatever
        else:  # html2text or html
            log("msg: preferring html")
            msg = msg_html or msg_plain or msg
            log("msg: resulting content_type is %r" % (msg.get_content_type(),))

        charset = msg.get_charsets('utf-8')[0]
        body = msg.get_payload(None, True)
        body = unicode(body, charset, 'replace')
        # check for `msg.get_content_subtype() == 'html'` instead?
        if 'text/html' in msg.get_content_type():
            if config.preferredFormat != 'html':
                log("msg: doing html2text")
                html2text = get_html2text(config)
                body = html2text(body)
            # TODO: else compose an XMPP-HTML message? Will require a
            # complicated preprocessor like bs4 though

        # TODO?: optional extra headers (e.g. To if To != Envelope-To)
        # prepended to the body.
        m = Message(to=jto, frm=jfrom, subject=subject, body=body)
        self.jabber.send(m)
