# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from .common import TestPunchoutCommon


class TestPunchout(TestPunchoutCommon):
    def test_backend_creation(self):
        """Test that backend is created with correct values."""
        self.assertTrue(self.backend.id)
        self.assertEqual(self.backend.protocol, "cxml")
        self.assertEqual(self.backend.state, "draft")

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
