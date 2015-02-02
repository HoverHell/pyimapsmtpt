# coding: utf8

import logging


_log = logging.getLogger(__name__)


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
    import logging.config
    if config.log_level is not None:
        config.logging['root']['level'] = config.log_level
    if config.log_file is not None:
        config.logging['handlers']['main_file']['filename'] = config.log_file
        config.logging['root']['handlers'] = ['main_file']
    logging.config.dictConfig(config.logging)


def config_email_utf8():
    """ Apparently, for created email, this makes the email module avoid using
    base64 for encoding utf-8 email body parts. It also sets `output_charset`
    to None.  The exact reasons are still unclear.  """
    import email
    email.Charset.add_charset(
        'utf-8',
        ## Default: 3
        header_enc=email.Charset.SHORTEST,
        ## Default: 2
        body_enc=None,
        ## Default: 'utf-8'
        output_charset=None)
