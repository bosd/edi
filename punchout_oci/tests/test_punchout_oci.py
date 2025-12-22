# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.tools import mute_logger

from .common import TestPunchoutOciCommon


class TestPunchoutOci(TestPunchoutOciCommon):
    def test_oci_protocol_available(self):
        """Test that OCI protocol is available in selection."""
        protocols = dict(self.backend_model._selection_protocol())
        self.assertIn("oci", protocols)
        self.assertEqual(protocols["oci"], "OCI")

    def test_oci_backend_creation(self):
        """Test that OCI backend is created with correct values."""
        self.assertTrue(self.backend.id)
        self.assertEqual(self.backend.protocol, "oci")
        self.assertEqual(self.backend.oci_version, "5.0")

    def test_oci_setup_url_generation(self):
        """Test that OCI catalog URL is generated correctly."""
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertIn("HOOK_URL=", url)
        self.assertIn("username=test", url)

    def test_oci_store_response(self):
        """Test storing OCI form data response."""
        form_data = self._get_sample_oci_form_data()
        response_json = json.dumps(form_data)

        session = self.session_model._store_punchout_session_response(
            self.backend.id, response_json
        )

        self.assertTrue(session)
        self.assertEqual(session.state, "to_process")
        self.assertTrue(session.response)

    @mute_logger("odoo.addons.punchout_oci.models.punchout_session")
    def test_oci_empty_response(self):
        """Test that empty response is handled gracefully."""
        session = self.session_model._store_punchout_session_response(
            self.backend.id, "{}"
        )
        self.assertTrue(session)
        self.assertEqual(session.state, "error")

    def test_oci_validate_response(self):
        """Test OCI response validation."""
        form_data = self._get_sample_oci_form_data()
        self.session.response = json.dumps(form_data)
        result = self.session._validate_response()
        self.assertTrue(result.get("valid"))

    def test_oci_validate_response_no_items(self):
        """Test OCI response validation with no items."""
        self.session.response = json.dumps({"other_field": "value"})
        result = self.session._validate_response()
        self.assertFalse(result.get("valid"))
