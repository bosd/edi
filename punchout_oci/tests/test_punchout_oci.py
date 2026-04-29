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

    def test_oci_setup_url_uses_generic_auth_fields(self):
        """Generic auth_username / auth_password / auth_customer_number
        get spliced into the form-POST URL using the per-supplier
        param-name mapping. Default mapping is the OCI-conventional
        UPPERCASE names."""
        # Wipe the test-common's oci_custom_parameters so we exercise
        # the new generic-auth path in isolation.
        self.backend.oci_custom_parameters = False
        self.backend.auth_username = "alice"
        self.backend.auth_password = "s3cret"
        self.backend.auth_customer_number = "C-42"
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertIn("USERNAME=alice", url)
        self.assertIn("PASSWORD=s3cret", url)
        self.assertIn("CUSTOMER=C-42", url)

    def test_oci_setup_url_param_mapping_overrides(self):
        """Each preset can override the param names — TVH uses
        lowercase ``username``/``password`` and no customer number."""
        self.backend.oci_custom_parameters = False
        self.backend.auth_username = "alice"
        self.backend.auth_password = "s3cret"
        self.backend.auth_customer_number = False
        self.backend.oci_param_username = "username"
        self.backend.oci_param_password = "password"
        self.backend.oci_param_customer = False
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertIn("username=alice", url)
        self.assertIn("password=s3cret", url)
        # No customer number in the URL — auth_customer_number is
        # empty; the default ``CUSTOMER`` doesn't get a stray empty
        # value.
        self.assertNotIn("CUSTOMER=", url)

    def test_oci_setup_url_custom_parameters_override_generic(self):
        """``oci_custom_parameters`` is the technical escape hatch —
        when it sets a key the generic auth splice would also set,
        the explicit admin override wins."""
        self.backend.auth_username = "alice"
        self.backend.oci_custom_parameters = "USERNAME=overridden"
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertIn("USERNAME=overridden", url)
        self.assertNotIn("USERNAME=alice", url)

    def test_oci_setup_url_empty_auth_skipped(self):
        """Empty auth fields don't pollute the URL with bare keys."""
        self.backend.oci_custom_parameters = False
        self.backend.auth_username = False
        self.backend.auth_password = False
        self.backend.auth_customer_number = False
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertNotIn("USERNAME=", url)
        self.assertNotIn("PASSWORD=", url)
        self.assertNotIn("CUSTOMER=", url)

    def test_oci_setup_url_includes_session_token(self):
        """HOOK_URL should carry the session's buyer_cookie as
        ``punchout_session_token`` so the receive controller can
        unambiguously match the returning cart."""
        url = self.session_model._get_post_punchout_setup_url(self.session)
        self.assertIn("punchout_session_token", url)
        self.assertIn(self.session.buyer_cookie_id, url)

    def test_oci_store_response_with_token_picks_specific_session(self):
        """When the callback supplies a session_token, we match by
        buyer_cookie even if a more recent draft session for the same
        backend exists."""
        # Newer draft session — would win the legacy lookup.
        newer = self.session_model.create(
            {
                "backend_id": self.backend.id,
                "buyer_cookie_id": "newer-cookie",
            }
        )
        form_data = self._get_sample_oci_form_data()
        matched = self.session_model._store_punchout_session_response(
            self.backend.id,
            json.dumps(form_data),
            session_token=self.session.buyer_cookie_id,
        )
        self.assertEqual(matched, self.session)
        self.assertNotEqual(matched, newer)

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
