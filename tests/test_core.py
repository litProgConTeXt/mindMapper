# -*- coding: utf-8 -*-
from io import open
from unittest import TestCase
import os
from mock import patch

import pytest

from mindMapper.utils import InvalidFileException
from mindMapper.utils import clean_url
import mindMapper.processor

def simple_url_formatter(endpoint, url):
    """
        A simple URL formatter to use when no application context
        is available.

        :param str endpoint: the endpoint to use.
        :param str url: the URL to format
    """
    print("simple_url_formatter")
    return u"/{}".format(url)

def wikilink_simple_url_formatter(text, page):
    """
        A wikilink function that uses the simple URL formatter.

        :param str text: the text to format.
    """
    print("wikilink_simple_url_formatter")
    return mindMapper.processor.wikilink(text, page, url_formatter=simple_url_formatter)

# Directly Monkey Path the Processor BEFORE loading the wiki
#
oldProcessorInit = mindMapper.processor.Processor.__init__
def simpleWikilinkProcessorInit(self, text, aPage) :
    """
        As the processor can currently not take arguments for
        preprocessors we need to temporarily subclass it to
        overwrite it with the simple URL formatter.
    """
    oldProcessorInit(self, text, aPage)
    self.postprocessors = [wikilink_simple_url_formatter]

mindMapper.processor.Processor.__init__ = simpleWikilinkProcessorInit

from mindMapper.page import Page

from utils import WikiBaseTestCase

class MockPage :
    def addLink(self, aBaseUrl, aTitle, aModifier) :
        pass

PAGE_CONTENT = u"""\
title: Test
tags: one, two, 3, jö

Hello, how are you guys?

**Is it not _magnificent_**?
"""

PAGE_CONTENT_INVALID = u"""\
Hello, how are you guys?
"""

CONTENT_HTML = u"""\
<p>Hello, how are you guys?</p>
<p><strong>Is it not <em>magnificent</em></strong>?</p>"""

WIKILINK_PAGE_CONTENT = u"""\
title: link

[[target]]
"""

WIKILINK_CONTENT_HTML = u"""\
<p><a href='/target' title='link'>target</a></p>"""

class URLCleanerTestCase(TestCase):
    """
        Contains various tests for the url cleaner.
    """

    def test_clean_simple_url(self):
        """
            Assert a simple URL remains unchanged.
        """
        simple_url = '/test'

        assert clean_url(simple_url) == simple_url

    def test_clean_deep_url(self):
        """
            Assert a deep URL remains unchanged.
        """
        deep_url = '/test/two/three/yo'

        assert clean_url(deep_url) == deep_url

    def test_handle_spaces(self):
        """
            Assert that unnecessary spaces will be removed and all
            other spaces correctly substituted.
        """
        assert (clean_url('   /hello you/wonderful/person ')
                == '/hello_you/wonderful/person')

    def test_handle_uppercase(self):
        """
            Assert that uppercase characters will be substituted.
        """
        assert clean_url("HELLo") == "hello"


class WikilinkTestCase(TestCase):
    """
        Contains various tests for the wikilink parser.
    """

    def test_simple_wikilink(self):
        """
            Assert a simple wikilink is converted correctly.
        """
        page = MockPage()
        formatted = mindMapper.processor.wikilink(u'[[target]]', page, simple_url_formatter)
        assert formatted == "<a href='/target' title='link'>target</a>"

    def test_titled_wikilink(self):
        """
            Assert a wikilink with a title will be converted correctly.
        """
        page = MockPage()
        formatted = mindMapper.processor.wikilink(u'[[target|Target]]', page, simple_url_formatter)
        assert formatted == "<a href='/target' title='link'>Target</a>"

    def test_multiple_wikilinks(self):
        """
            Assert a text with multiple wikilinks will be converted
            correctly.
        """
        page = MockPage()
        formatted = mindMapper.processor.wikilink(
            u'[[target|Target]] is better than [[alternative]]',
            page,
            simple_url_formatter
        )
        assert formatted == (
            "<a href='/target' title='link'>Target</a> is better than"
            " <a href='/alternative' title='link'>alternative</a>"
        )


class ProcessorTestCase(WikiBaseTestCase):
    """
        Contains various tests for the :class:`~wiki.core.Processors`
        class.
    """

    page_content = PAGE_CONTENT

    def setUp(self):
        super(ProcessorTestCase, self).setUp()
        page = MockPage()
        self.processor = mindMapper.processor.Processor(self.page_content, page)

    def test_process(self):
        """
            Assert processing works correctly.
        """
        html, original, meta = self.processor.process()

        assert html == CONTENT_HTML
        assert original == PAGE_CONTENT.split(u'\n\n', 1)[1]
        assert meta == {
            'title': u'Test',
            'tags': u'one, two, 3, jö'
        }

    def test_process_wikilinks(self):
        """
            Assert that wikilinks are processed correctly.
        """
        page = MockPage()
        #self.processor = SimpleWikilinkProcessor(WIKILINK_PAGE_CONTENT, page)
        self.processor = mindMapper.processor.Processor(WIKILINK_PAGE_CONTENT, page)
        html, _, _ = self.processor.process()
        assert html == WIKILINK_CONTENT_HTML


class PageTestCase(WikiBaseTestCase):
    """
        Contains various tests for the :class:`~wiki.core.Page`
        class.
    """

    page_content = PAGE_CONTENT

    def setUp(self):
        super(PageTestCase, self).setUp()

        self.page_path = self.create_file('test.md', self.page_content)
        self.page = Page(self.page_path, 'test')

    def test_page_loading(self):
        """
            Assert that content is loaded correctly from disk.
        """
        assert self.page.content == PAGE_CONTENT

    def test_page_meta(self):
        """
            Assert meta data is interpreted correctly.
        """
        assert self.page.title == u'Test'
        assert self.page.tags == u'one, two, 3, jö'

    def test_page_saving(self):
        """
            Assert that saving a page back to disk persists it
            correctly.
        """
        self.page.save()
        with open(self.page_path, 'r', encoding='utf-8') as fhd:
            saved = fhd.read()
        assert saved == self.page_content


class InvalidPageTestCase(WikiBaseTestCase):
    """
        Contains various tests for the :class:`~wiki.core.Page`
        class, but with an invalid file.
    """

    page_content = PAGE_CONTENT_INVALID

    def setUp(self):
        super(InvalidPageTestCase, self).setUp()

        self.page_path = self.create_file('test.md', self.page_content)

    def test_page_loading_fails(self):
        """
            Assert that content is loaded correctly from disk.
        """
        with pytest.raises(InvalidFileException):
            Page(self.page_path, 'test')


class WikiTestCase(WikiBaseTestCase):
    """
        Contains various tests for the :class:`~wiki.core.Wiki`
        class.
    """

    def test_simple_file_detection(self):
        """
            Assert a test markdown file is correctly detected.
        """
        self.create_file('test.md')
        assert self.wiki.exists('test') is True

    def test_wrong_extension_detection(self):
        """
            Assert a non markdown file is ingored.
        """
        self.create_file('test.txt')
        assert self.wiki.exists('test') is False

    def test_config_is_unreadable(self):
        """
            Assert that the content file cannot be loaded as a page.
        """
        # the config file is automatically created, so we can just run
        # tests without having to worry about anything
        assert self.wiki.exists('config') is False
        assert self.wiki.exists('config.py') is False

    def test_delete(self):
        """
            Assert deleting a URL will delete the file.
        """
        self.create_file('test.md')
        self.wiki.delete("test")
        assert not os.path.exists(os.path.join(self.rootdir, 'test.md'))

    def test_index(self):
        """
            Assert index correctly lists all the files.
        """
        self.create_file('test.md', PAGE_CONTENT)
        self.create_file('one/two/three.md', WIKILINK_PAGE_CONTENT)
        self.create_file('invalid.md', PAGE_CONTENT_INVALID)
        self.wiki.rebuildPagesCache()
        pages = self.wiki.index()
        assert len(pages) == 2

        # as the index return should be sorted by the title
        # the first page should always be the link one and the other
        # one the second
        deeptestpage = pages[0]
        assert deeptestpage.url == 'one/two/three'

        testpage = pages[1]
        assert testpage.url == 'test'
        #assert False

    def test_move(self):
        """
            Assert that pages are moved correctly, including URL sanitization.
        """
        self.create_file('test.md')
        assert self.wiki.move('test', 'newtest') == 'newtest'
        assert self.wiki.exists('newtest')
        assert not self.wiki.exists('test')

        self.create_file('test_2.md')
        assert self.wiki.move('test_2', 'Test 3') == "test_3"
        assert self.wiki.exists('test_3')
        assert not self.wiki.exists('test_2')
