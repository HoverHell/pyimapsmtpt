#!/usr/bin/env python
# coding: utf8

import pytest

from pyimapsmtpt.convertlayer import extract_headers_from_body


pph = ('subject',)  ## default [p]re[p]arse_[h]eaders


ex1 = ("""
Subject: actual subject
Meta-header: some meta header

The body
""", ('subject', 'meta-header'))  ## => header-message


def test_ex1():
    res = extract_headers_from_body(*ex1)
    assert res


ex2 = (ex1[0], pph)  ## => error, extraneous header


def test_ex2():
    with pytest.raises(ValueError):
        extract_headers_from_body(*ex2)


ex3 = ("""
This is a message with no
subject: it matches, but it should not
be processed as a header-message

... and should not return an error.
""", pph)  ## => plain message


def test_ex3():
    assert extract_headers_from_body(*ex3) is None


ex4 = ("""
subejct: error subject

The body
""", pph)  ## => error, invalid header


def test_ex4():
    with pytest.raises(ValueError):
        extract_headers_from_body(*ex4)


ex5 = ("""
i: you
you: i

this is not a header-message though
""", pph)  ## => error, as an exceptional case



def test_ex5():
    with pytest.raises(ValueError):
        extract_headers_from_body(*ex5)
