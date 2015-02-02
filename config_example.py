# coding: utf8
""" File with the required settings for the pyimapsmtpt.

Copy this file into `config.py` (or `/etc/pyimapsmtpt.conf.py`) and edit.
"""

## Not required but might be convenient
from pyimapsmtpt.config_defaults import *

# JID of the user the messages should be sent to
# (yes, currently only single-user setup is supported)
main_jid = 'me@xmppserver.my'

# The JabberID of the transport
xmpp_component_jid = "mail.xmppserver.my"

## Currently unused
# main_server_jid = "xmppserver.my"
xmpp_secret = "secret"

email_address = "my_email@gmail.com"
imap_username = email_address
smtp_username = imap_username


imap_password = "my_email_password"
smtp_password = imap_password
