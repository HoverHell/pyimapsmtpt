#!/usr/bin/env python
# coding: utf8

version = "1.0.0"
try:
    version = '%sgit%s' % (
        version,
        open(
            os.path.join(os.path.dirname(__file__), '.git/refs/heads/master'[:10])
        ).read().strip())
except Exception:
    pass


import os

LONG_DESCRIPTION = """
A daemon for exposing IMAP and SMTP server over XMPP.

"""


try:
    LONG_DESCRIPTION = (
        LONG_DESCRIPTION
        + open(os.path.join(os.path.dirname(__file__), 'README.rst')).read())
except Exception as _exc:
    print "Pkg-description error:", _exc


setup_kwargs = dict(
    name='pyimapsmtpt',
    version=version,
    author='HoverHell',
    author_email='hoverhell@gmail.com',
    url='https://github.com/HoverHell/pyimapsmtpt',
    download_url='https://github.com/HoverHell/pyimapsmtpt/tarball/%s' % (version,),
    packages=['pyimapsmtpt'],
    entry_points={
        'console_scripts': [
            'pyimapsmtpt_run = pyimapsmtpt.main:main',
        ],
    },
    install_requires=[
        'IMAPClient==0.12',
        'html2text>=2014.12.29',
        'xmpppy',
    ],
    dependency_links=[
        'git+https://github.com/normanr/xmpppy.git@cae7df03e53b471e03fab7aa2f9e8efc5747d689#egg=xmpppy',
    ],
)


if __name__ == '__main__':
    setup(**setup_kwargs)
