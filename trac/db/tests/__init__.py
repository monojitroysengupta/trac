import unittest

from trac.db.tests import api
from trac.db.tests import postgres_test
from trac.db.tests import backup

def suite():

    suite = unittest.TestSuite()
    suite.addTest(api.suite())
    suite.addTest(postgres_test.suite())
    suite.addTest(backup.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

