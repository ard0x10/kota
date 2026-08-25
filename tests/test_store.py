"""The accounts, and the one rule that must never bend.

The signed-in account's refresh token belongs to Claude Code. kota reads it and
hands it back untouched; refreshing it would rotate it, and the copy Claude
Code is holding would stop working mid-session. Half of this file exists to
make that impossible to break by accident.
"""

import pathlib
import tempfile
import time
import unittest
from unittest import mock

from kota import api, creds, paths, secrets, store


def an_account(uuid="u1", label="work", expires_in_ms=3_600_000):
    return store.Account(
        uuid=uuid,
        email=label + "@example.com",
        label=label,
        access=secrets.protect("access-" + uuid),
        refresh=secrets.protect("refresh-" + uuid),
        expires_at=int(time.time() * 1000) + expires_in_ms,
    )


def signed_in_as(account, token=None):
    """Claude Code holding this account's token."""
    return creds.Live(access_token=token or secrets.unprotect(account.access),
                      refresh_token="live-refresh", expires_at=0, plan="pro")


class Isolated(unittest.TestCase):
    """Every test gets its own accounts file; none touches the real one."""

    def setUp(self):
        self.room = tempfile.TemporaryDirectory()
        here = pathlib.Path(self.room.name)
        self.patches = [
            mock.patch.object(paths, "ACCOUNTS_FILE", here / "accounts.json"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.room.cleanup()


class TheActiveAccountIsNeverRefreshed(Isolated):
    def test_a_valid_active_token_comes_from_claude_code(self):
        account = an_account()
        live = signed_in_as(account, token="whatever-claude-code-has-now")
        with mock.patch.object(api, "refresh") as refresh:
            token, changed = store._token_for(account, True, live)
        refresh.assert_not_called()
        self.assertEqual(token, "whatever-claude-code-has-now")
        self.assertFalse(changed)

    def test_an_expired_active_token_is_still_not_refreshed(self):
        account = an_account(expires_in_ms=-1_000_000)
        live = signed_in_as(account, token="fresh-from-claude-code")
        with mock.patch.object(api, "refresh") as refresh:
            token, _ = store._token_for(account, True, live)
        refresh.assert_not_called()
        self.assertEqual(token, "fresh-from-claude-code")

    def test_active_with_unreadable_credentials_is_still_not_refreshed(self):
        """The dangerous case: signed in, but the file could not be read.

        Refreshing here would rotate the token of the account somebody is in
        the middle of using. Better to report nothing than to sign them out.
        """
        account = an_account(expires_in_ms=-1_000_000)
        with mock.patch.object(api, "refresh") as refresh:
            store._token_for(account, True, None)
        refresh.assert_not_called()


class PassiveAccountsAreRefreshed(Isolated):
    def test_a_valid_passive_token_is_used_as_is(self):
        account = an_account()
        with mock.patch.object(api, "refresh") as refresh:
            token, changed = store._token_for(account, False, None)
        refresh.assert_not_called()
        self.assertEqual(token, "access-u1")
        self.assertFalse(changed)

    def test_an_expired_passive_token_is_refreshed_and_kept(self):
        account = an_account(expires_in_ms=-1_000)
        with mock.patch.object(api, "refresh",
                               return_value=("new-access", "new-refresh", 28800)):
            token, changed = store._token_for(account, False, None)
        self.assertEqual(token, "new-access")
        self.assertTrue(changed)
        self.assertEqual(secrets.unprotect(account.access), "new-access")
        self.assertEqual(secrets.unprotect(account.refresh), "new-refresh")
        self.assertGreater(account.expires_at, time.time() * 1000)

    def test_a_token_about_to_expire_is_refreshed_early(self):
        """Sixty seconds left is not enough to make a request with."""
        account = an_account(expires_in_ms=60_000)
        with mock.patch.object(api, "refresh",
                               return_value=("new", "new-r", 28800)) as refresh:
            store._token_for(account, False, None)
        refresh.assert_called_once()

    def test_an_account_with_no_refresh_token_gives_up_quietly(self):
        account = an_account(expires_in_ms=-1_000)
        account.refresh = ""
        with mock.patch.object(api, "refresh") as refresh:
            token, changed = store._token_for(account, False, None)
        refresh.assert_not_called()
        self.assertIsNone(token)
        self.assertFalse(changed)


class Collecting(Isolated):
    def test_the_signed_in_account_is_the_one_marked_active(self):
        one, two = an_account("u1", "work"), an_account("u2", "personal")
        usage = api.Usage()
        with mock.patch.object(creds, "read", return_value=signed_in_as(two)), \
             mock.patch.object(api, "usage", return_value=usage):
            reports, _ = store.collect([one, two])
        self.assertEqual([r.active for r in reports], [False, True])

    def test_one_account_failing_does_not_take_the_others_with_it(self):
        one, two = an_account("u1"), an_account("u2")

        def sometimes(token):
            if token == "access-u1":
                raise api.ApiError("signed out", 401)
            return api.Usage()

        with mock.patch.object(creds, "read", return_value=None), \
             mock.patch.object(api, "usage", side_effect=sometimes):
            reports, _ = store.collect([one, two])
        self.assertIn("capture", reports[0].error)
        self.assertEqual(reports[1].error, "")
        self.assertIsNotNone(reports[1].usage)

    def test_every_row_is_handed_over_as_it_lands(self):
        seen = []
        with mock.patch.object(creds, "read", return_value=None), \
             mock.patch.object(api, "usage", return_value=api.Usage()):
            store.collect([an_account("u1"), an_account("u2")], on_row=seen.append)
        self.assertEqual(len(seen), 2)


class Capturing(Isolated):
    def test_nobody_signed_in(self):
        with mock.patch.object(creds, "read", return_value=None):
            _, uuid, message = store.capture([])
        self.assertIsNone(uuid)
        self.assertIn("signed in", message)

    def test_a_new_account_is_added(self):
        live = creds.Live("tok", "ref", 123, "max")
        with mock.patch.object(creds, "read", return_value=live), \
             mock.patch.object(api, "identity",
                               return_value=("u9", "new@example.com", "pro")):
            accounts, uuid, _ = store.capture([])
        self.assertEqual(uuid, "u9")
        self.assertEqual(accounts[0].label, "new")
        # The credentials file knows the plan; it does not need asking for.
        self.assertEqual(accounts[0].plan, "max")
        self.assertEqual(secrets.unprotect(accounts[0].access), "tok")

    def test_the_same_account_again_is_replaced_not_doubled(self):
        existing = an_account("u9", "new")
        live = creds.Live("tok2", "ref2", 123, "pro")
        with mock.patch.object(creds, "read", return_value=live), \
             mock.patch.object(api, "identity",
                               return_value=("u9", "new@example.com", "pro")):
            accounts, _, message = store.capture([existing])
        self.assertEqual(len(accounts), 1)
        self.assertEqual(secrets.unprotect(accounts[0].access), "tok2")
        self.assertIn("updated", message)

    def test_a_token_we_already_know_costs_no_request(self):
        existing = an_account("u9")
        with mock.patch.object(creds, "read", return_value=signed_in_as(existing)), \
             mock.patch.object(api, "identity") as identity:
            _, found, _ = store.capture([existing])
        identity.assert_not_called()
        self.assertEqual(found, "u9")


class Removing(Isolated):
    def test_by_label_and_by_address(self):
        one, two = an_account("u1", "work"), an_account("u2", "personal")
        store.save([one, two])
        left, gone = store.remove([one, two], "work")
        self.assertEqual(gone.uuid, "u1")
        self.assertEqual([a.uuid for a in left], ["u2"])
        left, gone = store.remove(left, "personal@example.com")
        self.assertEqual(gone.uuid, "u2")
        self.assertEqual(left, [])

    def test_a_name_nobody_has(self):
        one = an_account("u1", "work")
        left, gone = store.remove([one], "nobody")
        self.assertIsNone(gone)
        self.assertEqual(left, [one])


class SavingAndLoading(Isolated):
    def test_a_round_trip(self):
        store.save([an_account("u1", "work"), an_account("u2", "personal")])
        back = store.load()
        self.assertEqual([a.label for a in back], ["work", "personal"])
        self.assertEqual(secrets.unprotect(back[0].access), "access-u1")

    def test_a_file_that_is_not_there(self):
        self.assertEqual(store.load(), [])

    def test_a_file_full_of_nonsense(self):
        paths.ACCOUNTS_FILE.write_text("{ this is not json", encoding="utf-8")
        self.assertEqual(store.load(), [])

    def test_a_field_that_arrived_from_a_later_version(self):
        """An unknown key must not stop the account being read."""
        paths.write_json(paths.ACCOUNTS_FILE, {"version": 99, "accounts": [
            {"uuid": "u1", "email": "a@b.c", "label": "work",
             "something_new": True}]})
        back = store.load()
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0].label, "work")


if __name__ == "__main__":
    unittest.main()
