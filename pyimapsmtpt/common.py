# coding: utf8

import re
import logging


_log = logging.getLogger(__name__)


class EventProcessed(Exception):
    """ A special exception to end the current event processing """


def to_bytes(val):
    if isinstance(val, unicode):
        return val.encode('utf-8')
    return val


def get_html2text(config):
    try:
        import html2text
    except Exception, exc:
        _log.warning("html2text import failure: %r", exc)
        return lambda s: s  # dummy replacement

    obj = html2text.HTML2Text(bodywidth=config.html2text_bodywidth)
    obj.links_each_paragraph = config.html2text_links_each_paragraph
    for k, v in config.html2text_etcetera.items():
        setattr(obj, k, v)

    ## postprocess
    def func(val, *ar, **kwa):
        res = obj.handle(val, *ar, **kwa)
        if config.html2text_strip():
            res = res.strip()
        return res

    func.html2text_mod = html2text
    func.html2text = obj
    return func


def configure_logging(config):
    import logging.config as logconf
    if config.log_level is not None:
        config.logging['root']['level'] = config.log_level
    if config.log_file is not None:
        config.logging['handlers']['main_file']['filename'] = config.log_file
        config.logging['root']['handlers'] = ['main_file']
    logconf.dictConfig(config.logging)


def config_email_utf8():
    """ Apparently, for created email, this makes the email module avoid using
    base64 for encoding utf-8 email body parts. It also sets `output_charset`
    to None.  The exact reasons are still unclear.  """
    import email.charset
    email.charset.add_charset(
        'utf-8',
        ## Default: 3
        header_enc=email.charset.SHORTEST,
        ## Default: 2
        body_enc=None,
        ## Default: 'utf-8'
        output_charset=None)


#######
## Library-independence for JIDs
#######

def jid_to_data(jid):
    """ ...

    :param jid: xmpp.protocol.JID instance or jid_data or string
    """
    if isinstance(jid, dict):
        assert 'node' in jid
        assert 'domain' in jid
        assert 'resource' in jid
        return jid

    if isinstance(jid, basestring):
        return jid_string_to_data(jid)

    ## Probably an xmpp.protocol.JID or equivalent
    return dict(node=jid.node, domain=jid.domain, resource=jid.resource)


def jid_data_to_string(jid_data, resource=True):
    res = [
        '%s@' % (jid_data['node'],) if jid_data['node'] else '',
        jid_data['domain'],
        '/%s' % (jid_data['resource'],) if resource else ''
    ]
    return ''.join(res)


_re_optional = lambda s: r'(?:%s)?' % (s,)
_jid_re = ''.join([
    r'^',
    _re_optional(r'(?P<node>[^@]+)@'),
    r'(?P<domain>[^/@]+)',
    _re_optional(r'/(?P<resource>.*)'),
    '$'])
# http://stackoverflow.com/a/1406200 - not perfectly strict but workable
_jid_re_strict = r'''^(?:([^@/<>'\"]+)@)?([^@/<>'\"]+)(?:/([^<>'\"]*))?$'''


def jid_string_to_data(jid_str, strict=True):
    if strict:
        m = re.match(_jid_re_strict, jid_str)
    else:
        m = re.match(_jid_re, jid_str)
    if not m:
        raise ValueError("Malformed JID", jid_str)
    node, domain, resource = m.groups()
    _pp = lambda v: v or ''
    return dict(node=_pp(node), domain=_pp(domain), resource=_pp(resource))
