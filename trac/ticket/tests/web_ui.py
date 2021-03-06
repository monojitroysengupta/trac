# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

import unittest

from trac.core import TracError
from trac.resource import ResourceNotFound
from trac.test import EnvironmentStub, Mock, MockPerm, locale_en
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.util.datefmt import utc
from trac.web.api import RequestDone, _RequestArgs
from trac.web.chrome import Chrome
from trac.web.session import DetachedSession


class TicketModuleTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.ticket_module = TicketModule(self.env)

    def tearDown(self):
        self.env.reset_db()

    def _create_request(self, authname='anonymous', **kwargs):
        kw = {'path_info': '/', 'perm': MockPerm(), 'args': _RequestArgs(),
              'href': self.env.href, 'abs_href': self.env.abs_href,
              'tz': utc, 'locale': None, 'lc_time': locale_en,
              'session': DetachedSession(self.env, authname),
              'authname': authname, 'chrome': {'notices': [], 'warnings': []},
              'method': None, 'get_header': lambda v: None, 'is_xhr': False,
              'form_token': None}
        if 'args' in kwargs:
            kw['args'].update(kwargs.pop('args'))
        kw.update(kwargs)
        def redirect(url, permanent=False):
            raise RequestDone
        return Mock(add_redirect_listener=lambda x: [].append(x),
                    redirect=redirect, **kw)

    def _create_ticket_with_change(self, old_props, new_props,
                                   author='anonymous'):
        """Create a ticket with `old_props` and apply properties
        in `new_props`.
        """
        t = Ticket(self.env)
        t.populate(old_props)
        t.insert()
        comment = new_props.pop('comment', None)
        t.populate(new_props)
        t.save_changes(author, comment=comment)
        return t

    def _insert_ticket(self, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = Ticket(self.env)
        for k, v in kw.items():
            ticket[k] = v
        return ticket.insert()

    def test_ticket_module_as_default_handler(self):
        """The New Ticket mainnav entry is active when TicketModule is the
        `default_handler` and navigating to the base url. Test for regression
        of http://trac.edgewall.org/ticket/8791.
        """
        req = self._create_request()
        chrome = Chrome(self.env).prepare_request(req, self.ticket_module)

        name = None
        for item in chrome['nav']['mainnav']:
            if item['active'] is True:
                name = item['name']
                break
        self.assertEqual('newticket', name)

    def test_reporter_and_owner_full_name_is_displayed(self):
        """Full name of reporter and owner are used in ticket properties."""
        self.env.insert_known_users([('user1', 'User One', None),
                                     ('user2', 'User Two', None)])
        tkt_id = self._insert_ticket(reporter='user1', owner='user2')
        req = self._create_request(authname='user2', method='GET',
                                   args={'id': tkt_id, 'replyto': '1'})

        data = self.ticket_module.process_request(req)[1]

        self.assertEqual(u'<a class="trac-author" href="/trac.cgi/query?'
                         u'status=!closed&amp;reporter=user1">User One</a>',
                         unicode(data['reporter_link']))
        self.assertEqual(u'<a class="trac-author-user" href="/trac.cgi/query?'
                         u'status=!closed&amp;owner=user2">User Two</a>',
                         unicode(data['owner_link']))

    def test_quoted_reply_author_is_obfuscated(self):
        """Reply-to author is obfuscated in a quoted reply."""
        author = 'author <author@example.net>'
        tkt = self._create_ticket_with_change({}, {'comment': 'the comment'},
                                              author)
        req = self._create_request(method='GET',
                                   args={'id': tkt.id, 'replyto': '1'})

        data = self.ticket_module.process_request(req)[1]

        comment = u"Replying to [comment:1 author <author@\u2026>]:\n> " \
                  u"the comment\n"
        self.assertEqual(comment, data['comment'])
        self.assertEqual(comment, data['change_preview']['comment'])

    def test_quoted_reply_author_full_name_is_displayed(self):
        """Full name of reply-to author is used in quoted reply."""
        self.env.insert_known_users([('author', 'The Author',
                                     'author@example.net')])
        tkt = self._create_ticket_with_change({}, {'comment': 'the comment'},
                                              'author')
        req = self._create_request(method='GET',
                                   args={'id': tkt.id, 'replyto': '1'})

        data = self.ticket_module.process_request(req)[1]

        comment = u"Replying to [comment:1 The Author]:\n> " \
                  u"the comment\n"
        self.assertEqual(comment, data['comment'])
        self.assertEqual(comment, data['change_preview']['comment'])

    def test_ticket_property_diff_owner_change(self):
        """Property diff message when ticket owner is changed."""
        t = self._create_ticket_with_change({'owner': 'owner1'},
                                            {'owner': 'owner2'})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['owner']

        self.assertEqual("changed from <em>owner1</em> to <em>owner2</em>",
                         str(field['rendered']))

    def test_ticket_property_diff_owner_add(self):
        """Property diff message when ticket owner is added."""
        t = self._create_ticket_with_change({'owner': ''},
                                            {'owner': 'owner2'})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['owner']

        self.assertEqual("set to <em>owner2</em>", str(field['rendered']))

    def test_ticket_property_diff_owner_remove(self):
        """Property diff message when ticket owner is removed."""
        t = self._create_ticket_with_change({'owner': 'owner1'},
                                            {'owner': ''})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['owner']

        self.assertEqual("<em>owner1</em> deleted", str(field['rendered']))

    def test_ticket_property_diff_reporter_change(self):
        """Property diff message when ticket reporter is changed."""
        t = self._create_ticket_with_change({'reporter': 'reporter1'},
                                            {'reporter': 'reporter2'})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['reporter']

        self.assertEqual("changed from <em>reporter1</em> to "
                         "<em>reporter2</em>", str(field['rendered']))

    def test_ticket_property_diff_reporter_add(self):
        """Property diff message when ticket reporter is added."""
        t = self._create_ticket_with_change({'reporter': ''},
                                            {'reporter': 'reporter2'})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['reporter']

        self.assertEqual("set to <em>reporter2</em>", str(field['rendered']))

    def test_ticket_property_diff_reporter_remove(self):
        """Property diff message when ticket reporter is removed."""
        t = self._create_ticket_with_change({'reporter': 'reporter1'},
                                            {'reporter': ''})

        req = self._create_request(args={'id': t.id})
        data = self.ticket_module.process_request(req)[1]
        field = data['changes'][0]['fields']['reporter']

        self.assertEqual("<em>reporter1</em> deleted", str(field['rendered']))

    def _test_invalid_cnum_raises(self, action, cnum=None):
        self._insert_ticket()
        req = self._create_request(args={'action': action, 'id': '1'})
        if cnum is not None:
            req.args.update({'cnum': cnum})

        self.assertRaises(TracError, self.ticket_module.process_request, req)

    def test_comment_history_cnum_missing_raises(self):
        self._test_invalid_cnum_raises('comment-history')

    def test_comment_history_cnum_invalid_type_raises(self):
        self._test_invalid_cnum_raises('comment-history', 'a')

    def test_comment_history_cnum_empty_raises(self):
        self._test_invalid_cnum_raises('comment-history', '')

    def test_comment_history_cnum_out_of_range(self):
        """Out of range cnum returns an empty history."""
        self._insert_ticket()
        req = self._create_request(args={'action': 'comment-history',
                                         'id': '1', 'cnum': '1'})

        resp = self.ticket_module.process_request(req)
        self.assertEqual([], resp[1]['history'])

    def test_comment_diff_cnum_missing_raises(self):
        self._test_invalid_cnum_raises('comment-diff')

    def test_comment_diff_cnum_invalid_type_raises(self):
        self._test_invalid_cnum_raises('comment-diff', 'a')

    def test_comment_diff_cnum_empty_raises(self):
        self._test_invalid_cnum_raises('comment-diff', '')

    def test_comment_diff_cnum_out_of_range_raises(self):
        self._insert_ticket()
        req = self._create_request(args={'action': 'comment-diff',
                                         'id': '1', 'cnum': '1'})

        self.assertRaises(ResourceNotFound,
                          self.ticket_module.process_request, req)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TicketModuleTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
