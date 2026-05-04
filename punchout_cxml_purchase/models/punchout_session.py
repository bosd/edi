# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import date, timedelta

import lxml.etree as ET

from odoo import models
from odoo.exceptions import UserError

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

        # Match by supplier product code. The two conditions on
        # ``seller_ids`` MUST go through ``any`` so they apply to the
        # SAME supplierinfo row. With two separate ``seller_ids.field``
        # leaves, Odoo's ORM matches across rows — a product with
        # vendor A's code "ABC" plus vendor B (the punchout supplier)
        # on its supplier list would falsely match a vendor B cart
        # line for "ABC", because one row satisfies the partner check
        # and a different row satisfies the code check.
        if supplier_part_id and backend.partner_id:
            matches = Product.search(
                [
                    (
                        "seller_ids",
                        "any",
                        [
                            ("partner_id", "=", backend.partner_id.id),
                            ("product_code", "=", supplier_part_id),
                        ],
                    ),
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
                self._apply_cxml_classification_to_description(matches[0], item_detail)
                return matches[0]

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
                            # Pin to backend's company — see
                            # punchout_oci_purchase.punchout_session
                            # for the full rationale.
                            "company_id": backend._get_company().id,
                        },
                    )
                ]

            product = Product.sudo().create(product_vals)
            self._apply_cxml_classification_to_description(product, item_detail)
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

        # Hard fail rather than substituting an arbitrary
        # purchase-enabled product when nothing matches.
        raise UserError(
            self.env._(
                "Punchout cart line for supplier-part %(part)s "
                "(%(desc)s) couldn't be matched to any product, and "
                "Auto Create Products is disabled on the backend "
                "%(backend)s. Either enable it, or pre-create the "
                "product and add %(supplier)s to its Vendors tab "
                "with code %(part)s before re-running the punchout.",
                part=supplier_part_id or "(none)",
                desc=description,
                backend=backend.display_name,
                supplier=(
                    backend.partner_id.display_name
                    if backend.partner_id
                    else "(no supplier configured)"
                ),
            )
        )

    def _apply_cxml_classification_to_description(self, product, item_detail):
        """Append cXML ``Classification`` codes (UNSPSC, eCl@ss, etc.)
        to the product's ``description_purchase`` as a labelled
        footer. cXML allows multiple ``Classification`` elements,
        each with a ``domain`` attribute identifying the standard.
        Stored verbatim until a generic product-classification
        module ships (see ROADMAP).

        Idempotent: skipped if the marker is already present.
        """
        self.ensure_one()
        classifications = item_detail.findall("Classification")
        if not classifications:
            return
        marker = "[Classification]"
        existing = product.description_purchase or ""
        if marker in existing:
            return
        lines = []
        for cls in classifications:
            domain = cls.get("domain") or "Unknown"
            code = (cls.text or "").strip()
            if code:
                lines.append(f"{domain}: {code}")
        if not lines:
            return
        footer = "\n\n" + marker + "\n" + "\n".join(lines)
        product.sudo().description_purchase = (existing + footer).strip()

    def _build_protocol_header_messages(self, order, new_lines):
        """Surface Total / Tax mismatches between the supplier's cart
        header and Odoo's computed PO totals as chatter warnings so
        the buyer can reconcile before confirming. Shipping and
        Extrinsic charges aren't surfaced here — they're materialised
        as real PO lines by ``_prepare_protocol_extra_lines``.
        """
        self.ensure_one()
        msgs = super()._build_protocol_header_messages(order, new_lines)
        header = self._cxml_header()
        if header is None:
            return msgs
        cart_total, total_ccy = self._cxml_header_money(header, "Total")
        po_total = order.amount_total
        if cart_total is not None and abs(cart_total - po_total) > 0.01:
            msgs.append(
                self.env._(
                    "Supplier total <strong>%(cart)s %(ccy)s</strong> differs "
                    "from Odoo's computed PO total <strong>%(po)s</strong> — "
                    "verify the lines and taxes before confirming.",
                    cart=f"{cart_total:.2f}",
                    ccy=total_ccy,
                    po=f"{po_total:.2f}",
                )
            )
        cart_tax, _ccy = self._cxml_header_money(header, "Tax")
        po_tax = order.amount_tax
        if cart_tax is not None and abs(cart_tax - po_tax) > 0.01:
            msgs.append(
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
        return msgs

    def _prepare_protocol_extra_lines(self):
        """Materialise cXML cart-header surcharges as PO lines.

        ``<Shipping>`` (one) and each ``<Extrinsic name="...">`` with
        a ``<Money>`` payload become a PO line backed by an auto-
        spawned ``Punchout: <name>`` service product (looked up by
        name first, so a curated pre-existing product is reused).
        Tax-free by default — supplier values are taken at face value.
        """
        self.ensure_one()
        lines = super()._prepare_protocol_extra_lines()
        if self.backend_id.protocol != "cxml":
            return lines
        header = self._cxml_header()
        if header is None:
            return lines
        charges = []
        ship_amt, ship_ccy = self._cxml_header_money(header, "Shipping")
        if ship_amt is not None and ship_amt > 0:
            charges.append(("Shipping", ship_amt, ship_ccy))
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
            charges.append(
                (
                    extrinsic.get("name") or "Extrinsic charge",
                    value,
                    money.get("currency", ""),
                )
            )
        backend = self.backend_id
        company = backend._get_company()
        # ``purchase.order.line.tax_ids`` is plain m2m, not a compute. The
        # onchange that would populate it (``_prepare_add_missing_fields``
        # → ``onchange_product_id``) only fires when ``order_id`` is in
        # the create vals — which it isn't when we hand a ``(0, 0, vals)``
        # tuple to ``purchase.order.create``. So resolve tax_ids ourselves
        # from the product's purchase taxes (filtered by company) and
        # mapped through the partner's fiscal position, the same chain
        # ``_compute_tax_id`` would use.
        fpos = (
            self.env["account.fiscal.position"]
            .with_company(company)
            ._get_fiscal_position(backend.partner_id)
            if backend.partner_id
            else self.env["account.fiscal.position"]
        )
        for name, amount, _currency in charges:
            product = self._get_or_create_punchout_charge_product(name)
            taxes = product.supplier_taxes_id._filter_taxes_by_company(company)
            # Fall back to the company default purchase tax when the
            # product has no ``supplier_taxes_id`` — handles products
            # that pre-existed from earlier rounds (auto-spawned
            # tax-free) or where the user manually set ``taxes_id``
            # instead of ``supplier_taxes_id``.
            if not taxes and company.account_purchase_tax_id:
                taxes = company.account_purchase_tax_id
            mapped_taxes = fpos.map_tax(taxes) if fpos else taxes
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": self.env._("Supplier-quoted %(name)s", name=name),
                        "product_qty": 1.0,
                        "price_unit": amount,
                        "product_uom_id": product.uom_id.id,
                        "date_planned": date.today(),
                        "tax_ids": [(6, 0, mapped_taxes.ids)],
                    },
                )
            )
        return lines

    def _cxml_header(self):
        """Return the parsed ``PunchOutOrderMessageHeader`` lxml
        element, or ``None`` when the response is missing/invalid or
        the protocol isn't cXML."""
        self.ensure_one()
        if self.backend_id.protocol != "cxml" or not self.response:
            return None
        try:
            tree = ET.fromstring(self.response.encode())
        except ET.XMLSyntaxError:
            return None
        return tree.find(".//PunchOutOrderMessageHeader")

    @staticmethod
    def _cxml_header_money(header, tag):
        """Pull ``(amount, currency)`` from ``<{tag}><Money currency="X">N
        </Money></{tag}>``. Returns ``(None, None)`` when the element
        is missing or the amount isn't parseable."""
        elem = header.find(f"{tag}/Money")
        if elem is None or not elem.text:
            return None, None
        try:
            return float(elem.text.strip()), elem.get("currency", "")
        except (ValueError, TypeError):
            return None, None

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
