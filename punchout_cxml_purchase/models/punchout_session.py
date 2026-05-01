# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import date, timedelta

import lxml.etree as ET

from odoo import models

_logger = logging.getLogger(__name__)


class PunchoutSession(models.Model):
    _inherit = "punchout.session"

    def _prepare_purchase_order_lines(self):
        """Prepare order lines from cXML PunchOutOrderMessage response."""
        self.ensure_one()
        if self.backend_id.protocol != "cxml":
            return super()._prepare_purchase_order_lines()

        if not self.response:
            return []

        lines = []
        try:
            tree = ET.fromstring(self.response.encode())
            for item in tree.findall(".//ItemIn"):
                line_vals = self._parse_cxml_item(item)
                if line_vals:
                    lines.append((0, 0, line_vals))
        except ET.XMLSyntaxError as e:
            _logger.error("Error parsing cXML response: %s", e)
            return []

        return lines

    def _parse_cxml_item(self, item_element):
        """Parse a cXML ItemIn element and return purchase order line values."""
        self.ensure_one()

        # Get quantity
        quantity = float(item_element.get("quantity", 1))

        # Get ItemDetail
        item_detail = item_element.find("ItemDetail")
        if item_detail is None:
            return {}

        # Get description
        description_elem = item_detail.find("Description")
        description = (
            description_elem.text if description_elem is not None else "Unknown"
        )

        # Get unit price
        unit_price_elem = item_detail.find("UnitPrice/Money")
        unit_price = 0.0
        if unit_price_elem is not None and unit_price_elem.text:
            try:
                unit_price = float(unit_price_elem.text)
            except (ValueError, TypeError):
                _logger.debug("Invalid cXML UnitPrice format: %s", unit_price_elem.text)

        # Get supplier part ID
        item_id = item_element.find("ItemID")
        supplier_part_id = ""
        if item_id is not None:
            supplier_part_elem = item_id.find("SupplierPartID")
            if supplier_part_elem is not None:
                supplier_part_id = supplier_part_elem.text or ""

        # Get or create product
        product = self._get_or_create_product_cxml(
            supplier_part_id, description, unit_price, item_detail
        )

        # Get UoM
        uom = self._get_uom_for_cxml_item(item_detail)

        # Parse LeadTime (in days). cXML 1.2 spec ``ItemDetail/LeadTime``
        # is the supplier-promised number of days from order to delivery.
        # Apply to ``date_planned`` so the PO carries the correct expected
        # arrival date — was previously hardcoded to today, ignoring
        # whatever the supplier promised.
        lead_days = 0
        lead_elem = item_detail.find("LeadTime")
        if lead_elem is not None and lead_elem.text:
            try:
                lead_days = int(lead_elem.text.strip())
            except (ValueError, TypeError):
                _logger.debug("Invalid cXML LeadTime format: %s", lead_elem.text)
        date_planned = date.today() + timedelta(days=lead_days)

        return {
            "product_id": product.id,
            "name": description,
            "product_qty": quantity,
            "price_unit": unit_price,
            "product_uom_id": uom.id,
            "date_planned": date_planned,
        }

    def _get_or_create_product_cxml(
        self, supplier_part_id, description, unit_price, item_detail
    ):
        """Find existing product by supplier info or create a new one."""
        self.ensure_one()
        backend = self.backend_id
        Product = self.env["product.product"]

        # Try to find by supplier product code. Don't ``limit=1`` so
        # we can warn about ambiguous matches (same partner_id +
        # supplier-part attached to multiple products — pathological
        # data, but it happens when a backend was reconfigured and
        # old supplierinfo lines were never cleaned up).
        if supplier_part_id and backend.partner_id:
            matches = Product.search(
                [
                    ("seller_ids.partner_id", "=", backend.partner_id.id),
                    ("seller_ids.product_code", "=", supplier_part_id),
                ]
            )
            if len(matches) > 1:
                _logger.warning(
                    "[punchout.cxml.match] backend=%s supplier_part=%s matched "
                    "%d products (%s); picking the first deterministically.",
                    backend.name,
                    supplier_part_id,
                    len(matches),
                    matches.mapped("display_name"),
                )
            if matches:
                return matches[0]

        # No supplier-code match. Try matching by name (existing
        # product, but not yet linked to this supplier). If found,
        # ADD this supplier to the product's seller_ids so future
        # punchout sessions match by code AND so the user sees this
        # vendor on the product form. Without this step,
        # auto-created products are fine but products that already
        # exist in the catalog (e.g. matched by name through
        # punchout_purchase glue) end up without a vendor link.
        if backend.partner_id and description:
            existing = Product.search([("name", "=", description)], limit=1)
            if existing:
                self._ensure_supplier_link(
                    existing,
                    backend,
                    supplier_part_id,
                    description,
                    unit_price,
                    item_detail,
                )
                return existing

        # Create new product if auto_create_products is enabled
        if backend.auto_create_products:
            uom = self._get_uom_for_cxml_item(item_detail)
            # Backend-driven defaults — see
            # ``punchout.backend._get_auto_create_product_defaults``.
            product_vals = {
                "name": description,
                "uom_id": uom.id,
                **backend._get_auto_create_product_defaults(),
            }

            # Add supplier info
            if backend.partner_id:
                # cXML's UnitPrice/Money carries the ISO currency in
                # the @currency attribute. product.supplierinfo.currency_id
                # is NOT NULL since Odoo 18, so we MUST resolve a record.
                # Fall back to the company currency when the cart's code
                # is unknown / absent so we never trip the constraint.
                money_elem = item_detail.find("UnitPrice/Money")
                currency_code = (
                    money_elem.get("currency", "") if money_elem is not None else ""
                )
                currency = (
                    self.env["res.currency"].search(
                        [("name", "=", currency_code)], limit=1
                    )
                    if currency_code
                    else self.env["res.currency"]
                )
                if not currency:
                    currency = backend._get_company().currency_id
                product_vals["seller_ids"] = [
                    (
                        0,
                        0,
                        {
                            "partner_id": backend.partner_id.id,
                            "product_code": supplier_part_id,
                            "product_name": description,
                            "price": unit_price,
                            "currency_id": currency.id,
                        },
                    )
                ]

            product = Product.sudo().create(product_vals)
            self._post_create_product_hook(
                product,
                {
                    "supplier_part_id": supplier_part_id,
                    "description": description,
                    "unit_price": unit_price,
                    "item_detail": item_detail,
                },
            )
            return product

        # Fallback: return a generic product or raise error
        return Product.search([("purchase_ok", "=", True)], limit=1)

    def _build_protocol_header_messages(self, order, new_lines):
        """Surface cXML PunchOutOrderMessageHeader data — Total,
        Shipping, Tax, and Extrinsic costs (e.g. Order Costs) — as
        chatter warnings so the buyer can reconcile against Odoo's
        native PO totals before confirming.

        Odoo's PO model has no first-class fields for supplier-
        reported shipping / order costs, and Odoo computes its own
        tax (which may differ from what the supplier quoted). The
        safest behaviour is to expose the supplier's numbers verbatim
        so the buyer notices when something diverges. A future
        commit can add backend fields like ``freight_product_id`` to
        materialise the supplier's shipping/order-cost values as
        actual PO lines automatically.
        """
        self.ensure_one()
        msgs = super()._build_protocol_header_messages(order, new_lines)
        if self.backend_id.protocol != "cxml" or not self.response:
            return msgs
        try:
            tree = ET.fromstring(self.response.encode())
        except ET.XMLSyntaxError:
            return msgs
        header = tree.find(".//PunchOutOrderMessageHeader")
        if header is None:
            return msgs

        def _money(elem_path):
            elem = header.find(f"{elem_path}/Money")
            if elem is None or not elem.text:
                return None, None
            try:
                return float(elem.text.strip()), elem.get("currency", "")
            except (ValueError, TypeError):
                return None, None

        bullets = []
        # Supplier-reported total — compare to Odoo's computed total.
        cart_total, total_ccy = _money("Total")
        po_total = order.amount_total
        if cart_total is not None and abs(cart_total - po_total) > 0.01:
            bullets.append(
                self.env._(
                    "Supplier total <strong>%(cart)s %(ccy)s</strong> differs "
                    "from Odoo's computed PO total <strong>%(po)s</strong> — "
                    "verify the lines, taxes, and any shipping / order costs "
                    "before confirming.",
                    cart=f"{cart_total:.2f}",
                    ccy=total_ccy,
                    po=f"{po_total:.2f}",
                )
            )
        # Supplier-reported tax — compare to Odoo's computed tax.
        cart_tax, _ccy = _money("Tax")
        po_tax = order.amount_tax
        if cart_tax is not None and abs(cart_tax - po_tax) > 0.01:
            bullets.append(
                self.env._(
                    "Supplier tax <strong>%(cart)s</strong> differs from "
                    "Odoo's computed tax <strong>%(po)s</strong>. Odoo's "
                    "tax derives from each product's configured tax_id; if "
                    "the supplier's number is correct, adjust the product "
                    "taxes or the line tax overrides.",
                    cart=f"{cart_tax:.2f}",
                    po=f"{po_tax:.2f}",
                )
            )
        # Supplier-reported shipping — Odoo's PO model has no native
        # field for this; surface it so the buyer can add it as a
        # separate line manually.
        cart_ship, _ccy = _money("Shipping")
        if cart_ship is not None and cart_ship > 0:
            bullets.append(
                self.env._(
                    "Supplier reported <strong>%(amt)s</strong> in shipping. "
                    "Odoo doesn't auto-create a freight line — add one "
                    "manually before confirming, or configure a freight "
                    "product on the backend (planned).",
                    amt=f"{cart_ship:.2f}",
                )
            )
        # Extrinsic charges — typically Order Costs, sometimes more.
        for extrinsic in header.findall("Extrinsic"):
            money = extrinsic.find("Money")
            if money is None or not money.text:
                continue
            try:
                value = float(money.text.strip())
            except (ValueError, TypeError):
                continue
            if value <= 0:
                continue
            bullets.append(
                self.env._(
                    "Supplier reported <strong>%(name)s</strong>: "
                    "<strong>%(amt)s</strong>. Add as a separate PO line "
                    "if you need to capture it.",
                    name=extrinsic.get("name", "Extrinsic charge"),
                    amt=f"{value:.2f}",
                )
            )
        return bullets

    def _ensure_supplier_link(
        self,
        product,
        backend,
        supplier_part_id,
        description,
        unit_price,
        item_detail,
    ):
        """Make sure ``backend.partner_id`` is on the product's
        ``seller_ids`` so the vendor link survives the punchout
        round-trip. Creates a new ``product.supplierinfo`` row when
        one doesn't exist for (product, partner) yet. No-op when the
        partner is already a seller — we don't overwrite price or
        delay on existing rows because the user may have edited
        them deliberately.
        """
        self.ensure_one()
        if not backend.partner_id:
            return
        existing = product.seller_ids.filtered(
            lambda s, p=backend.partner_id: s.partner_id == p
        )
        if existing:
            return
        money_elem = item_detail.find("UnitPrice/Money")
        currency_code = money_elem.get("currency", "") if money_elem is not None else ""
        currency = (
            self.env["res.currency"].search([("name", "=", currency_code)], limit=1)
            if currency_code
            else self.env["res.currency"]
        )
        if not currency:
            currency = backend._get_company().currency_id
        product.sudo().write(
            {
                "seller_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": backend.partner_id.id,
                            "product_code": supplier_part_id,
                            "product_name": description,
                            "price": unit_price,
                            "currency_id": currency.id,
                        },
                    )
                ]
            }
        )

    def _post_create_product_hook(self, product, raw_data):
        """Hook fired after a product is auto-created from a punchout
        cart. Empty in base — override in private/glue modules to
        enrich the product (image, dimensions, HS code, brand, etc.)
        from the supplier's REST API. ``raw_data`` is the protocol-
        specific cart-line dict; for cXML it carries
        ``supplier_part_id``, ``description``, ``unit_price`` and the
        raw ``item_detail`` lxml element so overrides can pull
        protocol-specific fields without re-parsing.

        Hook fires once per newly-created product, never on existing
        product matches. Failures inside the hook MUST be caught by
        the override — the cart-import flow should never break
        because an enrichment call timed out."""

    def _get_uom_for_cxml_item(self, item_detail):
        """Get UoM for cXML item, using the full punchout.uom.mapping chain."""
        self.ensure_one()
        uom_elem = item_detail.find("UnitOfMeasure")
        uom_code = uom_elem.text if uom_elem is not None else None
        if uom_code:
            uom = self.env["punchout.uom.mapping"]._get_uom_by_supplier_code(
                self.backend_id, uom_code
            )
            if uom:
                return uom
        return self.env.ref("uom.product_uom_unit")
