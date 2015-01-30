# coding: utf8
""" File with the required settings for the pyimapsmtpt.

Copy this file into `config.py` (or `/etc/pyimapsmtpt.conf.py`) and edit.
"""

## Not required but might be convenient
from config_defaults import *

jid = "mail.xmppserver.my"
mainServerJID = "xmppserver.my"
secret = "secret"

email_address = "my_email@gmail.com"
imap_username = email_address
imap_password = "my_email_password"
smtp_username = imap_username
smtp_password = imap_password
