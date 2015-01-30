
== Synopsis ==

An xmpp transport (or bot, possibly to-be-done) that allows using IMAP+SSMTP
(e.g. gmail's) from an XMPP client.


== Dependencies ==

Most are listed in requirements.txt

However, some of those might require compiling, which, in turn, requires several libraries.

Known required packages in the terms of debian / ubuntu / alikes:

python-dev


== TODO ==

Use a better and more fresh XMPP library.


== Prior works ==

This codebase itself continues the pymailt codebase.

Pymailt:

  * http://xmpppy.sourceforge.net/mail/
  * http://sourceforge.net/projects/xmpppy/
  * https://github.com/normanr/mail-transport.git
  * https://github.com/HoverHell/mail-transport.git

The primary difference is that pyimapsmtpt does not require an owned mail
server; it still might require an owned xmpp server, but that one does not
have to be globally-reachable.


Other known relevant projects:

  * https://github.com/legastero/weld
