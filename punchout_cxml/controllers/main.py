# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from base64 import b64decode

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class PunchoutCxmlController(Controller):
    @route(
        "/punchout/cxml/receive/<int:backend_id>",
        type="http",
        auth="none",
        methods=["POST"],
        save_session=False,
        csrf=False,
        # We write (state flip + row lock) on every call, so opt out
        # of Odoo 18's speculative read-only cursor — otherwise the
        # SELECT FOR UPDATE forces a costly retry-with-rw-cursor on
        # every supplier callback (and emits a WARNING that trips
        # OCA's CI log scanner).
        readonly=False,
    )
    def receive_punchout_response(self, backend_id, *args, **kwargs):
        """Receive cXML PunchOutOrderMessage response.

        Defensive: every uncaught exception below causes Fabory's
        browser to land on a 500 page (bad UX, plus we lose the cart).
        Every exception path is caught, logged with full request
        context, and ends in a redirect to the backend's fallback URL
        so the user gets back into Odoo even when something blows up.
        """
        env = request.env
        backend = env["punchout.backend"].sudo().browse(backend_id)
        # Refuse traffic to non-open backends (draft / closed).
        try:
            backend._check_open_for_traffic()
        except Exception as e:  # noqa: BLE001
            _logger.warning(
                "[punchout.cxml.receive] backend=%s state=%s — refusing cart: %s",
                backend_id,
                getattr(backend, "state", "?"),
                e,
            )
            return request.redirect(backend._get_redirect_url())

        # Suppliers POST the PunchOutOrderMessage in different
        # encodings / param names. Try the common ones in order:
        #   1. ``cXML-base64`` form param (cXML spec example)
        #   2. ``cxml-base64`` (lowercase variant some send)
        #   3. ``cxml-urlencoded`` form param (URL-encoded XML)
        #   4. raw POST body (some suppliers POST application/xml
        #      with the cXML body straight up)
        # Whichever matches first wins. The supplier's choice is
        # logged so we can diagnose mismatches.
        form = request.httprequest.form
        cxml_string = None
        encoding_used = None
        for key in ("cXML-base64", "cxml-base64"):
            if form.get(key):
                try:
                    cxml_string = b64decode(form[key])
                    encoding_used = key
                    break
                except Exception as e:  # noqa: BLE001
                    _logger.warning(
                        "[punchout.cxml.receive] backend=%s base64 decode of "
                        "param %r failed: %s",
                        backend_id,
                        key,
                        e,
                    )
        if cxml_string is None:
            cxml_string = form.get("cxml-urlencoded")
            if cxml_string:
                encoding_used = "cxml-urlencoded"
        if cxml_string is None:
            raw = request.httprequest.get_data()
            if raw and raw.lstrip().startswith((b"<?xml", b"<cXML")):
                cxml_string = raw
                encoding_used = "raw-body"
        if cxml_string is None:
            _logger.error(
                "[punchout.cxml.receive] backend=%s no cXML payload found. "
                "Content-Type: %s. Form keys: %s. Raw body (first 500 chars): %r",
                backend_id,
                request.httprequest.content_type,
                list(form.keys()),
                request.httprequest.get_data()[:500],
            )
            return request.redirect(backend._get_redirect_url())
        _logger.info(
            "[punchout.cxml.receive] backend=%s payload received via %s (%s bytes)",
            backend_id,
            encoding_used,
            len(cxml_string),
        )
        try:
            backend._check_response_size(cxml_string)
        except Exception as e:  # noqa: BLE001
            _logger.error(
                "[punchout.cxml.receive] backend=%s payload rejected: %s",
                backend_id,
                e,
            )
            return request.redirect(backend._get_redirect_url())
        try:
            punchout_session = (
                env["punchout.session"]
                .sudo()
                ._store_punchout_session_response(backend_id, cxml_string)
            )
        except Exception:  # noqa: BLE001
            # A crash in the cart parser used to bubble up as a 500
            # to the supplier's browser. Log full detail and bounce
            # the user back to Odoo so they have a usable starting
            # point. The cXML payload is logged at WARNING (not
            # DEBUG) so it shows up in opaas's default log level —
            # otherwise the diagnostic data is lost.
            _logger.exception(
                "[punchout.cxml.receive] backend=%s _store_punchout_session_response "
                "raised — cart processing failed. Encoding: %s. cXML payload "
                "(first 2000 chars): %r",
                backend_id,
                encoding_used,
                cxml_string[:2000] if cxml_string else None,
            )
            return request.redirect(backend._get_redirect_url())
        if not punchout_session:
            redirect_url = backend._get_redirect_url()
            _logger.error(
                "[punchout.cxml.receive] backend=%s no session matched. XML "
                "(first 2000 chars): %r",
                backend_id,
                cxml_string[:2000] if cxml_string else None,
            )
        else:
            redirect_url = punchout_session._get_redirect_url()
        return request.redirect_query(redirect_url)
