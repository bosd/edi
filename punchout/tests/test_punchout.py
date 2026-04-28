# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .common import TestPunchoutCommon


class TestPunchout(TestPunchoutCommon):
    def test_backend_creation(self):
        """Test that backend is created with correct values."""
        self.assertTrue(self.backend.id)
        self.assertEqual(self.backend.protocol, "cxml")
        # ``state`` defaults to ``draft`` on the field — verify with
        # a fresh backend (the test-common one is forced to ``open``
        # so downstream tests work).
        fresh = self.backend_model.create(
            {
                "name": "draft-default-check",
                "description": "default-state check",
                "protocol": "cxml",
                "url": "https://example.com/punchout",
                "browser_form_post_url": "/punchout/receive/",
            }
        )
        self.assertEqual(fresh.state, "draft")

    def test_session_creation(self):
        """Test that session is created with correct values."""
        self.assertTrue(self.session.id)
        self.assertEqual(self.session.backend_id, self.backend)
        self.assertEqual(self.session.state, "draft")

    def test_session_duration_validation(self):
        """Test that session duration must be positive."""
        with self.assertRaises(ValidationError):
            self.backend.write({"session_duration": 0})

    def test_expiration_date_computed(self):
        """Test that expiration date is computed based on session duration."""
        self.assertTrue(self.session.expiration_date)
        self.assertTrue(self.session.expiration_date > self.session.create_date)

    def test_check_response_size_under_limit(self):
        """Payload under cap returns silently."""
        self.backend.max_response_size = 1024
        self.backend._check_response_size("x" * 100)

    def test_check_response_size_over_limit(self):
        """Oversized payload raises UserError."""
        self.backend.max_response_size = 100
        with self.assertRaises(UserError):
            self.backend._check_response_size("x" * 101)

    def test_check_response_size_disabled(self):
        """``max_response_size = 0`` disables the check (any size passes)."""
        self.backend.max_response_size = 0
        self.backend._check_response_size("x" * 10_000_000)

    def test_check_open_for_traffic_blocks_draft(self):
        """A draft backend refuses traffic — never been live."""
        self.backend.state = "draft"
        with self.assertRaises(UserError):
            self.backend._check_open_for_traffic()

    def test_check_open_for_traffic_blocks_closed(self):
        """A closed backend refuses traffic — explicitly decommissioned."""
        self.backend.state = "closed"
        with self.assertRaises(UserError):
            self.backend._check_open_for_traffic()

    def test_check_open_for_traffic_allows_open(self):
        """The only state that may receive traffic."""
        self.backend.state = "open"
        # Must not raise.
        self.backend._check_open_for_traffic()

    def test_gc_deletes_sessions_older_than_retention(self):
        """Sessions older than backend.session_retention_days get unlinked."""
        self.backend.session_retention_days = 30
        old_session = self.session_model.create({"backend_id": self.backend.id})
        # Age the row by writing create_date directly (skipping ORM defaults).
        self.env.cr.execute(
            "UPDATE punchout_session SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=60), old_session.id),
        )
        old_session.invalidate_recordset()
        deleted = self.session_model._gc_punchout_sessions()
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(old_session.exists())

    def test_gc_keeps_recent_sessions(self):
        """Sessions inside the retention window are not touched."""
        self.backend.session_retention_days = 30
        recent = self.session_model.create({"backend_id": self.backend.id})
        self.session_model._gc_punchout_sessions()
        self.assertTrue(recent.exists())

    def test_gc_skips_zero_retention(self):
        """``session_retention_days = 0`` opts out of GC entirely."""
        self.backend.session_retention_days = 0
        old_session = self.session_model.create({"backend_id": self.backend.id})
        self.env.cr.execute(
            "UPDATE punchout_session SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=10000), old_session.id),
        )
        self.session_model._gc_punchout_sessions()
        self.assertTrue(old_session.exists())
