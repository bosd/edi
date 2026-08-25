# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

import lxml.etree as ET
import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cxml_order_capable = fields.Boolean(
        compute="_compute_cxml_order_capable",
        help="True when this order's supplier has a cXML backend that accepts "
        "orders (drives the Send-as-cXML button).",
    )
    cxml_order_sent = fields.Boolean(
        string="cXML order sent", readonly=True, copy=False
    )
    cxml_order_sent_date = fields.Datetime(
        string="cXML order sent on", readonly=True, copy=False
    )
    cxml_order_response = fields.Text(
        string="cXML order response", readonly=True, copy=False
    )

    @api.depends("partner_id")
    def _compute_cxml_order_capable(self):
        for order in self:
            order.cxml_order_capable = bool(order._cxml_order_backend())

    def _cxml_order_backend(self):
        """The cXML backend that should receive this PO as an OrderRequest.

        A backend for the order's (commercial) vendor, cXML, opted in via
        ``cxml_order_send`` and active. Empty when the supplier is catalog-only
        (or not a cXML punchout supplier at all).
        """
        self.ensure_one()
        commercial = self.partner_id.commercial_partner_id
        return (
            self.env["punchout.backend"]
            .sudo()
            .search(
                [
                    ("protocol", "=", "cxml"),
                    ("cxml_order_send", "=", True),
                    ("active", "=", True),
                    ("partner_id.commercial_partner_id", "=", commercial.id),
                ],
                limit=1,
            )
        )

    # ---- cXML payload identity (mirrors the punchout.session helpers) -------
    def _cxml_order_timestamp(self):
        return fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def _cxml_order_payload_id(self):
        self.ensure_one()
        stamp = fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.id}.{stamp}@punchout.odoo"

    def _cxml_order_ship_to_partner(self):
        """Delivery address for the ShipTo block — the receiving warehouse's
        partner when available (purchase_stock), else the company partner."""
        self.ensure_one()
        if "picking_type_id" in self._fields:
            warehouse_partner = self.picking_type_id.warehouse_id.partner_id
            if warehouse_partner:
                return warehouse_partner
        return self.company_id.partner_id

    # ---- render / send ------------------------------------------------------
    def _render_cxml_order_request(self, backend):
        """Render the OrderRequest cXML for this PO. Mirrors
        ``punchout.session._render_cxml_operation``: strip whitespace bleed from
        leaf text (cXML servers compare credentials byte-for-byte) and prepend
        the cXML DTD declaration."""
        self.ensure_one()
        values = {"order": self, "backend": backend, "user": self.env.user}
        cxml = (
            self.env["ir.ui.view"]
            .sudo()
            ._render_template(
                "punchout_cxml_order_send.cxml_order_request", values=values
            )
        )
        element = ET.fromstring(cxml)
        for el in element.iter():
            if el.text and len(el) == 0:
                el.text = el.text.strip()
        ET.indent(element)
        return ET.tostring(
            element,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
            doctype=backend._get_cxml_dtd_declaration(),
        ).decode("utf-8")

    def _cxml_check_order_response(self, response):
        """Raise a clear error unless the supplier's cXML Response/Status is a
        success code (200-400)."""
        if not response.ok:
            raise UserError(
                _(
                    "The supplier rejected the order (HTTP %(code)s %(reason)s) "
                    "at %(url)s.",
                    code=response.status_code,
                    reason=response.reason,
                    url=response.url,
                )
            )
        code, text = 0, ""
        try:
            tree = ET.fromstring(response.content)
        except ET.XMLSyntaxError as err:
            raise UserError(
                _("The supplier returned a non-cXML response: %s", err)
            ) from err
        for status in tree.findall("./Response/Status"):
            code = int(status.attrib.get("code", 0))
            text = status.attrib.get("text", "")
        if not 200 <= code <= 400:
            raise UserError(
                _(
                    "The supplier rejected the order: cXML %(code)s %(text)s.",
                    code=code,
                    text=text,
                )
            )
        return True

    def action_send_cxml_order(self):
        """POST this PO to the supplier as a cXML OrderRequest."""
        for order in self:
            backend = order._cxml_order_backend()
            if not backend:
                raise UserError(
                    _(
                        "No cXML order-send backend is configured for supplier "
                        "%(supplier)s (enable 'Send orders as cXML' on the "
                        "PunchOut backend).",
                        supplier=order.partner_id.display_name,
                    )
                )
            if not backend.order_request_url:
                raise UserError(
                    _(
                        "Set the OrderRequest endpoint on the PunchOut backend "
                        "%(backend)s.",
                        backend=backend.display_name,
                    )
                )
            cxml = order._render_cxml_order_request(backend)
            try:
                response = requests.post(
                    backend.order_request_url,
                    data=cxml.encode("utf-8"),
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                    timeout=60,
                )
            except requests.RequestException as err:
                raise UserError(
                    _("Could not reach the supplier's order endpoint: %s", err)
                ) from err
            order._cxml_check_order_response(response)
            order.write(
                {
                    "cxml_order_sent": True,
                    "cxml_order_sent_date": fields.Datetime.now(),
                    "cxml_order_response": (response.text or "")[:8000],
                }
            )
            order.message_post(
                body=_(
                    "Order transmitted to %(supplier)s as a cXML OrderRequest "
                    "(accepted).",
                    supplier=backend.partner_id.display_name,
                )
            )
        return True


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _cxml_supplier_part(self, backend):
        """The supplier's part number for this line — the matching vendor
        supplierinfo code, falling back to the internal reference."""
        self.ensure_one()
        commercial = backend.partner_id.commercial_partner_id
        seller = self.product_id.seller_ids.filtered(
            lambda s, c=commercial: s.partner_id.commercial_partner_id == c
            and s.product_code
        )[:1]
        return (
            seller.product_code
            or self.product_id.default_code
            or str(self.product_id.id)
        )

    def _cxml_uom_code(self):
        """UNSPSC-style unit-of-measure code (best-effort: EA default)."""
        self.ensure_one()
        return "EA"
