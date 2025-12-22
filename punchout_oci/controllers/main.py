# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class PunchoutOciController(Controller):
    @route(
        "/punchout/oci/receive/<int:backend_id>",
        type="http",
        auth="none",
        methods=["POST"],
        save_session=False,
        csrf=False,
    )
    def receive_punchout_response(self, backend_id, *args, **kwargs):
        """Receive OCI shopping cart response.

        OCI responses come as form data with NEW_ITEM- prefixed parameters.
        Example: NEW_ITEM-DESCRIPTION[1]=Product, NEW_ITEM-QUANTITY[1]=10
        """
        env = request.env
        form_data = dict(request.httprequest.form)

        # Store the form data as JSON for session processing
        response_data = json.dumps(form_data)

        punchout_session = (
            env["punchout.session"]
            .sudo()
            ._store_punchout_session_response(backend_id, response_data)
        )
        backend = env["punchout.backend"].sudo().browse(backend_id)
        if not punchout_session:
            redirect_url = backend._get_redirect_url()
            _logger.error(
                "Unable to link the OCI punchout response to a session. "
                "Form data: \n%s",
                response_data,
            )
        else:
            redirect_url = punchout_session._get_redirect_url()
        return request.redirect(redirect_url)
