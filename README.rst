
WARNING: this is a work-in-progress.

TODO: message-id (e-mail) <-> conversation-id (in an xmpp resource) conversion

Synopsis
========

An xmpp transport (or bot, possibly to-be-done) that allows using IMAP+SSMTP
(e.g. gmail's) from an XMPP client.


Dependencies
============

Most are listed in the setup.py (use ``setup.py develop`` if you have virtuelanv).

However, some of those might require compiling, which, in turn, requires several libraries.

Known required packages in the terms of debian / ubuntu / alikes: ``python-dev``.

In Gentoo install ``dev-python/xmpppy dev-python/imapclient dev-python/gevent dev-python/html2text``.
However, xmpppy might have to be of a very specific version (see setup.py).


Usage
=====

 * Install dependencies
 * Input your passwords and stuff in ``config.py`` (see ``config_example.py``).
 * run ``python -m pyimapsmtpt.main``


TODO
====

Use a better and more fresh XMPP library.


Prior works
===========

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
