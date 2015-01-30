# coding: utf8
""" Default settings for the pyimapsmtpt.

Note that this does not include the settings with no sane defaults.

See `config_example.py` for the values that must be overridden.
"""

## Where to look for the local config (which is required)
configFiles = ['config.py', '/etc/pyimapsmtpt.conf.py']
configFile = None


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


host = ""
discoName = "Mail Transport"
pid = ""

mainServer = "127.0.0.1"
port = "5347"

useComponentBinding = False
useRouteWrap = False
saslUsername = ""

debugFile = ""

dumpProtocol = False

smtpServer = "127.0.0.1"

domains = []
fallbackToJid = ''

# 'plaintext' or 'html2text' or 'html'
preferredFormat = 'plaintext'
