# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class PunchoutIdsController(Controller):
    @route(
        "/punchout/ids/receive/<int:backend_id>",
        type="http",
        auth="none",
        methods=["POST"],
        save_session=False,
        csrf=False,
    )
    def receive_punchout_response(self, backend_id, *args, **kwargs):
        """Receive IDS shopping cart response.

        IDS responses come with a 'warenkorb' parameter containing XML.
        """
        env = request.env
        # IDS uses 'warenkorb' parameter for the shopping cart XML
        warenkorb = request.httprequest.form.get("warenkorb", "")

        punchout_session = (
            env["punchout.session"]
            .sudo()
            ._store_punchout_session_response(backend_id, warenkorb)
        )
        backend = env["punchout.backend"].sudo().browse(backend_id)
        if not punchout_session:
            redirect_url = backend._get_redirect_url()
            _logger.error(
                "Unable to link the IDS punchout response to a session. " "Data: \n%s",
                warenkorb[:500] if warenkorb else "(empty)",
            )
        else:
            redirect_url = punchout_session._get_redirect_url()
        return request.redirect(redirect_url)
