# coding: utf8
""" Default settings for the pyimapsmtpt.

Note that this does not include the settings with no sane defaults.

See `config_example.py` for the values that must be overridden.
"""

## Where to look for the local config (which is required)
config_files = ['config.py', '/etc/pyimapsmtpt.conf.py']
config_file = None


use_env = True  ## Allow overriding some settings from os.environ


#######
## Things you might want to override anyway
#######

## TODO?: in the transport mode, make those inputable-at-registration?

## The short client identifier that will be used to mark messages as 'seen by
## this client'.
## Beware, if your inbox is large this might work weirdly.
## TODO: at some 'initialisation' point, mark all inbox messages with this or
## somehow save the value for 'always filter for messages from the <current
## timestamp>'
imap_client_id = 'pyit1'

## NOTE: gmail incapabilities:
## https://support.google.com/mail/answer/78761?hl=en
imap_server = "imap.gmail.com:993"
imap_ssl = True
smtp_server = "smtp.gmail.com:587"
smtp_starttls = True
## TODO?: support the other smtp stuff

## XMPP stuff (*almost* useful defaults)

# The IP address or DNS name of the main Jabber server
xmpp_main_server = "127.0.0.1"
# The TCP port to connect to the Jabber server on (this is the default for Jabberd2)
xmpp_component_port = "5347"

# SASL username used to bind to Jabber server.
# if enabled, `xmpp_secret` is used for sasl password
xmpp_sasl_username = ""

# Use external component binding.
# This dodges the need to manually configure all jids that talk to this transport.
# Jabberd2 requires saslUsername and useRouteWrap for this to work.
# Wildfire as of 2.6.0 requires just this.
xmpp_use_component_binding = False

# Wrap stanzas in <route> stanza.
# Jabberd2 requires this for useComponentBinding.
xmpp_use_route_wrap = False


#######
## Things that have no default and must be overridden
#######

## See config_example.py


#######
## General library stuff
#######

# Preferred format for email->xmpp messages
# 'plaintext' or 'html2text' or 'html'
preferred_format = 'plaintext'


# Non-straightforward configuration for prepending some of the headers to the
# XMPP message body
prepend_headers = set(('subject', 'to'))  # also: '_always_to', 'from'


# Even less straightforward, for optionally parsing out some email headers
# from the received XMPP messages.
# Set this to empty to disable this feature.
# WARN: the default is somewhat wide-allowing.
# For examples, see `tests/test_xmppbody_headers.py`
# Rules:
#  * For headers to be tried, all text lines before the first blank line
#    should be header-like 'name: value'; otherwise everything is an email
#    body.
#  * First of the headers should always be first of the preparse_headers,
#    otherwise an error is returned
#  * All headers should be listed in preparse_headers (making it an
#    allowed-headers list); otherwise an error is returned
preparse_headers = ('subject', 'to', 'envelope-to')


# If html2text is preferred, this configuration will be used for it
html2text_strip = True
html2text_bodywidth = 100  # h2t's own default is 78
html2text_links_each_paragraph = 1  # h2t's own default is 0
## Whatever else thou want to set on it.
## see `html2text.config` source (the names generally need to be lowercased)
html2text_etcetera = {}


## These two options, if not None, are used to override some values in the
## `logging` option when configuring the logging (for easier overriding)
log_level = 1
log_file = ""

logging = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s: %(levelname)-13s: %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'main_file': {
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
    },
    'root': {
        'handlers': ['console'],
        'level': 1,
    },
}


#######
## The main daemon stuff
#######

## NOTE: `sed -r 's/([a-z])([A-Z])/\1_\l\2/g'` relative to pymailt.

# The name of the transport in the service discovery list.
xmpp_disco_name = "Personal Mail Transport"

# The location of the PID file
# Empty => no pidfile to be written
pidfile = ""

# Show the raw data being sent and received from the xmpp and mail servers
dump_protocol = False

# Restart self (using execv) on exit (e.g. IOError). Probably should not be
# used (use upstart/runit/bashscript/... instead).
auto_self_restart = False
