#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from html5lib.constants import cdataElements, rcdataElements
from lxml import etree

from calibre.ebooks.oeb.base import SVG_NS, XHTML_NS, XLINK_NS, XPath
from calibre.ebooks.oeb.parse_utils import html5_parse
from calibre.ebooks.oeb.polish.parsing import parse_html5 as parse
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from polyglot.builtins import iteritems


def nonvoid_cdata_elements(test, parse_function):
    ''' If self closed version of non-void cdata elements like <title/> are
    present, the HTML5 parsing algorithm treats all following data as CDATA '''
    markup = '''
    <html> <head><{0}/></head> <body id="test"> </html>
    '''
    for tag in cdataElements | rcdataElements:
        for x in (tag, tag.upper(), '\n' + tag, tag + ' id="xxx" '):
            root = parse_function(markup.format(x))
            test.assertEqual(
                len(XPath('//h:body[@id="test"]')(root)), 1,
                f'Incorrect parsing for <{x}/>, parsed markup:\n' + etree.tostring(root, encoding='unicode'))


def namespaces(test, parse_function):
    ae = test.assertEqual

    def match_and_prefix(root, xpath, prefix, err=''):
        matches = XPath(xpath)(root)
        ae(len(matches), 1, err)
        ae(matches[0].prefix, prefix, err)

    markup = f''' <html xmlns="{XHTML_NS}"><head><body id="test"></html> '''
    root = parse_function(markup)
    ae(
        len(XPath('//h:body[@id="test"]')(root)), 1,
        'Incorrect parsing, parsed markup:\n' + etree.tostring(root, encoding='unicode'))
    match_and_prefix(root, '//h:body[@id="test"]', None)

    markup = f'''
    <html xmlns="{XHTML_NS}"><head><body id="test">
    <svg:svg xmlns:svg="{SVG_NS}"><svg:image xmlns:xlink="{XLINK_NS}" xlink:href="xxx"/></svg:svg>
    '''
    root = parse_function(markup)
    err = 'Incorrect parsing, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    match_and_prefix(root, '//h:body[@id="test"]', None, err)
    match_and_prefix(root, '//svg:svg', 'svg', err)
    match_and_prefix(root, '//svg:image[@xl:href]', 'svg', err)

    markup = f'''
    <html xmlns="{XHTML_NS}"><head><body id="test">
    <svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" ><image xlink:href="xxx"/></svg>
    '''
    root = parse_function(markup)
    err = 'Incorrect parsing, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    match_and_prefix(root, '//h:body[@id="test"]', None, err)
    match_and_prefix(root, '//svg:svg', None, err)
    match_and_prefix(root, '//svg:image[@xl:href]', None, err)

    markup = '<html><body><svg><image xlink:href="xxx"></svg>'
    root = parse_function(markup)
    err = 'Namespaces not created, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    match_and_prefix(root, '//svg:svg', None, err)
    match_and_prefix(root, '//svg:image[@xl:href]', None, err)
    if parse_function is parse:
        image = XPath('//svg:image')(root)[0]
        ae(image.nsmap, {'xlink':XLINK_NS, None:SVG_NS})

    root = parse_function('<html id="a"><p><html xmlns:x="y" lang="en"><p>')
    err = 'Multiple HTML tags not handled, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    match_and_prefix(root, '//h:html', None, err)
    match_and_prefix(root, '//h:html[@lang]', None, err)
    match_and_prefix(root, '//h:html[@id]', None, err)

    # if parse_function is not html5_parse:
    #     markup = '<html:html xmlns:html="{html}" id="a"><html:body><html:p></html:p></html:body></html>'.format(html=XHTML_NS)
    #     root = parse_function(markup)
    #     err = 'HTML namespace prefixed, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    #     match_and_prefix(root, '//h:html', None, err)

    markup = '<html><body><ns1:tag1 xmlns:ns1="NS"><ns2:tag2 xmlns:ns2="NS" ns1:id="test"/><ns1:tag3 xmlns:ns1="NS2" ns1:id="test"/></ns1:tag1>'
    root = parse_function(markup)
    err = 'Arbitrary namespaces not preserved, parsed markup:\n' + etree.tostring(root, encoding='unicode')

    def xpath(expr):
        return etree.XPath(expr, namespaces={'ns1':'NS', 'ns2':'NS2'})(root)
    ae(len(xpath('//ns1:tag1')), 1, err)
    ae(len(xpath('//ns1:tag2')), 1, err)
    ae(len(xpath('//ns2:tag3')), 1, err)
    ae(len(xpath('//ns1:tag2[@ns1:id="test"]')), 1, err)
    ae(len(xpath('//ns2:tag3[@ns2:id="test"]')), 1, err)
    # for tag in root.iter():
    #     if 'NS' in tag.tag:
    #         ae('ns1', tag.prefix)

    markup = '<html xml:lang="en"><body><p lang="de"><p xml:lang="es"><p lang="en" xml:lang="de">'
    root = parse_function(markup)
    err = 'xml:lang not converted to lang, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    ae(len(root.xpath('//*[@lang="en"]')), 2, err)
    ae(len(root.xpath('//*[@lang="de"]')), 1, err)
    ae(len(root.xpath('//*[@lang="es"]')), 1, err)
    # ae(len(XPath('//*[@xml:lang]')(root)), 0, err)


def space_characters(test, parse_function):
    markup = '<html><p>\u000cX</p>'
    root = parse_function(markup)
    err = 'form feed character not converted, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    test.assertNotIn('\u000c', root.xpath('//*[local-name()="p"]')[0].text, err)
    markup = '<html><p>a\u000b\u000c</p>'
    root = parse_function(markup)  # Should strip non XML safe control code \u000b
    test.assertNotIn('\u000b', root.xpath('//*[local-name()="p"]')[0].text, err)
    test.assertNotIn('\u000c', root.xpath('//*[local-name()="p"]')[0].text, err)


def case_insensitive_element_names(test, parse_function):
    markup = '<HTML><P> </p>'
    root = parse_function(markup)
    err = 'case sensitive parsing, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    test.assertEqual(len(XPath('//h:p')(root)), 1, err)


def entities(test, parse_function):
    markup = '<html><p>&nbsp;&apos;</p>'
    root = parse_function(markup)
    err = 'Entities not handled, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    test.assertEqual("\xa0'", root.xpath('//*[local-name()="p"]')[0].text, err)


def multiple_html_and_body(test, parse_function):
    markup = '<html id="1"><body id="2"><p><html lang="en"><body lang="de"></p>'
    root = parse_function(markup)
    err = 'multiple html and body not handled, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    test.assertEqual(len(XPath('//h:html')(root)), 1, err)
    test.assertEqual(len(XPath('//h:body')(root)), 1, err)
    test.assertEqual(len(XPath('//h:html[@id and @lang]')(root)), 1, err)
    test.assertEqual(len(XPath('//h:body[@id and @lang]')(root)), 1, err)


def attribute_replacement(test, parse_function):
    markup = f'<html><body><svg viewbox="0"></svg><svg xmlns="{SVG_NS}" viewbox="1">'
    root = parse_function(markup)
    err = 'SVG attributes not normalized, parsed markup:\n' + etree.tostring(root, encoding='unicode')
    test.assertEqual(len(XPath('//svg:svg[@viewBox]')(root)), 2, err)


def comments(test, parse_function):
    markup = '<html><!-- -- ---><body/></html>'
    root = parse_function(markup)
    test.assertEqual(len(XPath('//h:body')(root)), 1, 'Failed to parse with comment containing dashes')
    test.assertEqual(len(tuple(root.iterdescendants(etree.Comment))), 1)


basic_checks = (nonvoid_cdata_elements, namespaces, space_characters,
                case_insensitive_element_names, entities, comments,
                multiple_html_and_body, attribute_replacement)


class ParsingTests(BaseTest):

    def test_lxml_tostring(self):
        ' Test for bug in some versions of lxml that causes incorrect serialization of sub-trees'
        from html5_parser import parse
        root = parse('<p>a<p>b<p>c')
        p = root.xpath('//p')[0]
        self.assertEqual(etree.tostring(p, encoding=str), '<p>a</p>')

    def test_conversion_parser(self):
        ' Test parsing with the HTML5 parser used for conversion '
        for test in basic_checks:
            test(self, html5_parse)

    def test_polish_parser(self):
        ' Test parsing with the HTML5 parser used for polishing '
        for test in basic_checks:
            test(self, parse)

        root = parse('<html><p><svg><image /><b></svg>&nbsp;\n<b>xxx', discard_namespaces=True)
        self.assertTrue(root.xpath('//b'), 'Namespaces not discarded')
        self.assertFalse(root.xpath('//svg/b'), 'The <b> was not moved out of <svg>')

        for ds in (False, True):
            src = '\n<html>\n<p>\n<svg><image />\n<b></svg>&nbsp'
            root = parse(src, discard_namespaces=ds)
            for tag, lnum in iteritems({'html':2, 'head':3, 'body':3, 'p':3, 'svg':4, 'image':4, 'b':5}):
                elem = root.xpath(f'//*[local-name()="{tag}"]')[0]
                self.assertEqual(lnum, elem.sourceline, f'Line number incorrect for {tag}, source: {src}:')

        for ds in (False, True):
            src = '\n<html>\n<p b=1 a=2 c=3 d=4 e=5 f=6 g=7 h=8><svg b=1 a=2 c=3 d=4 e=5 f=6 g=7 h=8>\n'
            root = parse(src, discard_namespaces=ds)
            for tag in ('p', 'svg'):
                for i, (k, v) in enumerate(root.xpath(f'//*[local-name()="{tag}"]')[0].items()):
                    self.assertEqual(i+1, int(v))

        root = parse('<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en-US" xmlns:xml="http://www.w3.org/XML/1998/namespace"><body/></html>')
        self.assertNotIn('xmlnsU0003Axml', root.attrib, 'xml namespace declaration not removed')

        root = parse('<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en-US" xmlns:extra="extra"><body/></html>')
        self.assertIn('extra', root.nsmap, 'Extra namespace declaration on <html> tag not preserved')


def timing():
    import sys

    from html5lib import parse as vanilla

    from calibre.ebooks.chardet import xml_to_unicode
    from calibre.utils.monotonic import monotonic
    filename = sys.argv[-1]
    with open(filename, 'rb') as f:
        raw = f.read()
    raw = xml_to_unicode(raw)[0]

    for name, f in (('calibre', partial(parse, line_numbers=False)), ('html5lib', vanilla), ('calibre-old', html5_parse)):
        timings = []
        for i in range(10):
            st = monotonic()
            f(raw)
            timings.append(monotonic() - st)
        avg = sum(timings)/len(timings)
        print(f'Average time for {name}: {avg:.2g}')
