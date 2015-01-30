# coding: utf8
""" Default settings for the pyimapsmtpt.

Note that this does not include the settings with no sane defaults.

See `config_example.py` for the values that must be overridden.
"""

## Where to look for the local config (which is required)
config_files = ['config.py', '/etc/pyimapsmtpt.conf.py']
config_file = None


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


## NOTE: `sed -r 's/([a-z])([A-Z])/\1_\l\2/g'` relative to pymailt.

host = ""
disco_name = "Mail Transport"
pid = ""

main_server = "127.0.0.1"
port = "5347"

use_component_binding = False
use_route_wrap = False
sasl_username = ""

debug_file = ""

dump_protocol = False

domains = []
fallback_to_jid = ''

# 'plaintext' or 'html2text' or 'html'
preferred_format = 'plaintext'
