from doajtest.helpers import DoajTestCase
from parameterized import parameterized, param
from doajtest.fixtures import JournalFixtureFactory, AccountFixtureFactory, ApplicationFixtureFactory

from copy import deepcopy

from portality.models import Journal, Account, Suggestion

from portality.bll import DOAJ
from portality.bll import exceptions


def create_update_cases():
    journal = Journal(**JournalFixtureFactory.make_journal_source(in_doaj=True))
    account_source = AccountFixtureFactory.make_publisher_source()

    owner_account = Account(**deepcopy(account_source))
    owner_account.set_id(journal.owner)

    non_owner_publisher = Account(**deepcopy(account_source))

    non_publisher = Account(**deepcopy(account_source))
    non_publisher.remove_role("publisher")

    admin = Account(**deepcopy(account_source))
    admin.add_role("admin")

    return [
        param("no_journal_no_account", None, None, raises=exceptions.ArgumentException),
        param("no_journal_with_account", None, owner_account, raises=exceptions.ArgumentException),
        param("journal_no_account", journal, None, raises=exceptions.ArgumentException),
        param("journal_matching_account", journal, owner_account, expected=True),
        param("journal_unmatched_account", journal, non_owner_publisher, raises=exceptions.AuthoriseException),
        param("journal_non_publisher_account", journal, non_publisher, raises=exceptions.AuthoriseException),
        param("journal_admin_account", journal, admin, expected=True)
    ]

def create_edit_cases():
    application_source = ApplicationFixtureFactory.make_application_source()
    account_source = AccountFixtureFactory.make_publisher_source()

    editable_application = Suggestion(**application_source)
    editable_application.set_application_status("update_request")

    non_editable_application = Suggestion(**application_source)
    non_editable_application.set_application_status("ready")

    owner_account = Account(**deepcopy(account_source))
    owner_account.set_id(editable_application.owner)

    non_owner_publisher = Account(**deepcopy(account_source))

    non_publisher = Account(**deepcopy(account_source))
    non_publisher.remove_role("publisher")

    admin = Account(**deepcopy(account_source))
    admin.add_role("admin")

    return [
        param("no_app_no_account", None, None, raises=exceptions.ArgumentException),
        param("no_app_with_account", None, owner_account, raises=exceptions.ArgumentException),
        param("app_no_account", editable_application, None, raises=exceptions.ArgumentException),
        param("editable_app_owning_account", editable_application, owner_account, expected=True),
        param("editable_app_nonowning_account", editable_application, non_owner_publisher, raises=exceptions.AuthoriseException),
        param("editable_app_non_publisher_account", editable_application, non_publisher, raises=exceptions.AuthoriseException),
        param("editable_app_admin_account", editable_application, admin, expected=True),
        param("non_editable_app_owning_account", non_editable_application, owner_account, raises=exceptions.AuthoriseException),
        param("non_editable_app_nonowning_account", non_editable_application, non_owner_publisher, raises=exceptions.AuthoriseException),
        param("non_editable_app_non_publisher_account", non_editable_application, non_publisher, raises=exceptions.AuthoriseException),
        param("non_editable_app_admin_account", non_editable_application, admin, expected=True)
    ]

class TestBLLAuthorisations(DoajTestCase):

    @parameterized.expand(create_update_cases)
    def test_01_create_update_request(self, name, journal, account, raises=None, expected=None):
        doaj = DOAJ()
        if raises is not None:
            with self.assertRaises(raises):
                doaj.can_create_update_request(account, journal)
        elif expected is not None:
            assert doaj.can_create_update_request(account, journal) is expected
        else:
            assert False, "Specify either raises or expected"

    @parameterized.expand(create_edit_cases)
    def test_02_edit_update_request(self, name, application, account, raises=None, expected=None):
        doaj = DOAJ()
        if raises is not None:
            with self.assertRaises(raises):
                doaj.can_edit_update_request(account, application)
        elif expected is not None:
            assert doaj.can_edit_update_request(account, application) is expected
        else:
            assert False, "Specify either raises or expected"