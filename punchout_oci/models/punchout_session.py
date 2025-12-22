# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PunchoutSession(models.Model):
    _inherit = "punchout.session"

    def _get_post_punchout_setup_url(self, session):
        """Build OCI catalog URL with authentication and HOOK_URL parameters.

        For OCI, we don't POST a setup request. Instead, we build a URL that:
        1. Points to the vendor's catalog
        2. Includes authentication parameters
        3. Includes HOOK_URL for the return endpoint
        """
        if session.backend_id.protocol != "oci":
            return super()._get_post_punchout_setup_url(session)

        backend = session.backend_id
        base_url = backend.url
        if not base_url:
            raise UserError(
                _("OCI catalog URL not configured on backend %(name)s.")
                % {"name": backend.display_name}
            )

        # Parse existing URL and query string
        parsed = urlparse(base_url)
        existing_params = parse_qs(parsed.query)

        # Build new parameters
        params = {}
        for key, value in existing_params.items():
            params[key] = value[0] if len(value) == 1 else value

        # Add custom parameters from backend
        if backend.oci_custom_parameters:
            custom_params = parse_qs(backend.oci_custom_parameters)
            for key, value in custom_params.items():
                params[key] = value[0] if len(value) == 1 else value

        # Add HOOK_URL - where the cart will be returned
        hook_url = backend._get_browser_form_post_url()
        params["HOOK_URL"] = hook_url

        # Add OCI version info if needed
        if backend.oci_version:
            params.setdefault("OCI_VERSION", backend.oci_version)

        # Rebuild URL with all parameters
        new_query = urlencode(params)
        new_url = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, "", new_query, "")
        )

        # Store the setup request info
        session.write(
            {
                "setup_request": f"OCI Catalog URL: {new_url}",
            }
        )

        return new_url

    @api.model
    def _store_punchout_session_response(self, backend_id, response_data):
        """Store OCI response and find matching session.

        OCI doesn't have a built-in session identifier like cXML's BuyerCookie.
        We match based on the user's most recent open session for this backend.
        """
        backend = self.env["punchout.backend"].sudo().browse(backend_id)
        if backend.protocol != "oci":
            return super()._store_punchout_session_response(backend_id, response_data)

        # For OCI, we need to find the most recent session for this backend
        # that is still in draft state and not expired
        session = self.sudo().search(
            [
                ("backend_id", "=", backend_id),
                ("state", "=", "draft"),
                ("expiration_date", ">", fields.Datetime.now()),
            ],
            order="create_date desc",
            limit=1,
        )

        if not session:
            _logger.error(
                "Unable to find an open OCI session for backend %s", backend_id
            )
            return False

        # Parse and store the form data
        try:
            if isinstance(response_data, str):
                form_data = json.loads(response_data)
            else:
                form_data = response_data
        except (json.JSONDecodeError, TypeError):
            form_data = {"raw": str(response_data)}

        session.write(
            {
                "response": json.dumps(form_data, indent=2),
                "response_date": fields.Datetime.now(),
            }
        )

        # Validate and update state
        validation = session._validate_response()
        if validation.get("valid"):
            session.write({"state": "to_process"})
        else:
            session.write({"state": "error", "error_message": validation.get("error")})

        return session

    def _validate_response(self):
        """Validate OCI response contains required fields."""
        self.ensure_one()
        if self.backend_id.protocol != "oci":
            return super()._validate_response()

        if not self.response:
            return {"valid": False, "error": "Empty response"}

        try:
            form_data = json.loads(self.response)
        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"Invalid JSON: {e}"}

        # Check for at least one NEW_ITEM entry
        has_items = any(key.startswith("NEW_ITEM-") for key in form_data.keys())
        if not has_items:
            return {"valid": False, "error": "No NEW_ITEM entries found in response"}

        return {"valid": True}
