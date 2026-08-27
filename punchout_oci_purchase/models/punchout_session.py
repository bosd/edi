# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
from datetime import date, timedelta

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PunchoutSession(models.Model):
    _inherit = "punchout.session"

    def _prepare_purchase_order_lines(self):
        """Prepare order lines from OCI shopping cart response."""
        self.ensure_one()
        if self.backend_id.protocol != "oci":
            return super()._prepare_purchase_order_lines()

        if not self.response:
            return []

        try:
            form_data = json.loads(self.response)
        except (json.JSONDecodeError, TypeError):
            _logger.error("Error parsing OCI response as JSON")
            return []

        # Parse OCI form data into product dictionaries
        product_dicts = self._parse_oci_form_data(form_data)

        lines = []
        for product_dict in product_dicts:
            product = self._get_or_create_product_oci(product_dict)
            line_vals = self._prepare_oci_order_line(product, product_dict)
            if line_vals:
                lines.append((0, 0, line_vals))

        return lines

    def _parse_oci_form_data(self, form_data):
        """Parse OCI form data (NEW_ITEM-KEY[index]) into list of dicts.

        OCI sends cart items as form fields like:
        NEW_ITEM-DESCRIPTION[1]=Product Name
        NEW_ITEM-QUANTITY[1]=10
        NEW_ITEM-PRICE[1]=99.99
        """
        prefix = "NEW_ITEM-"

        # Find all unique keys (without prefix and index)
        product_keys = set()
        for key in form_data:
            if key.startswith(prefix) and "[" in key and key.endswith("]"):
                # Extract key name between prefix and [index]
                key_name = key[len(prefix) : key.index("[")]
                product_keys.add(key_name)

        # Parse items by index
        product_dicts = []
        index = 1
        while True:
            # Check if any key exists for this index
            has_item = any(
                f"{prefix}{key}[{index}]" in form_data for key in product_keys
            )
            if not has_item:
                break

            product_dict = {}
            for key in product_keys:
                form_key = f"{prefix}{key}[{index}]"
                if form_key in form_data:
                    value = form_data[form_key]
                    # Handle lists (e.g., from multi-value fields)
                    if isinstance(value, list):
                        value = value[0] if value else ""
                    product_dict[key] = value

            # Also check for LONGTEXT with different format
            longtext_key = f"NEW_ITEM-LONGTEXT_{index}:132[]"
            if longtext_key in form_data:
                value = form_data[longtext_key]
                if isinstance(value, list):
                    value = value[0] if value else ""
                product_dict["LONGTEXT"] = value

            if product_dict:
                product_dicts.append(product_dict)
            index += 1

        return product_dicts

    def _prepare_oci_order_line(self, product, product_dict):
        """Prepare purchase order line values from OCI product dict."""
        self.ensure_one()

        # Get quantity
        quantity = float(product_dict.get("QUANTITY", 1))

        # OCI ``PRICE`` is the price for ``PRICEUNIT`` units (the price
        # basis, default 1). Divide so we book the true per-unit price:
        # a supplier sending PRICE=100 / PRICEUNIT=100 means 1.00 per
        # unit, not 100.00.
        price = float(product_dict.get("PRICE", 0))
        try:
            price_basis = float(product_dict.get("PRICEUNIT", 1) or 1)
        except (ValueError, TypeError):
            price_basis = 1.0
        unit_price = price / price_basis if price_basis else price

        # Get description
        description = product_dict.get("DESCRIPTION", product.name)

        # Get lead time for date_planned
        leadtime = float(product_dict.get("LEADTIME", 0))
        date_planned = date.today() + timedelta(days=leadtime)

        # Get UoM
        uom = self._get_uom_for_oci_item(product_dict)

        vals = {
            "product_id": product.id,
            "name": description,
            "product_qty": quantity,
            "price_unit": unit_price,
            "product_uom_id": uom.id,
            "date_planned": date_planned,
        }
        override_taxes = self._oci_line_tax_override(product, product_dict)
        if override_taxes is not None:
            vals["tax_ids"] = [(6, 0, override_taxes.ids)]
        return vals

    def _oci_line_tax_override(self, product, product_dict):
        """Return purchase taxes to force on the line when the cart's
        ``VATPERCENTAGE`` disagrees with the rate Odoo's product /
        fiscal-position chain would otherwise apply.

        Returns ``None`` to leave the standard chain in charge -- which
        is the smarter default for standard-rate lines because it already
        accounts for goods vs services, EU and reverse-charge variants
        that a bare percentage cannot express. We only step in for the
        genuine mismatch case: a reduced- or zero-rate cart item that
        auto-creates a product defaulting to the standard rate.
        """
        backend = self.backend_id
        vat_field = (backend.oci_vat_field or "").strip()
        raw = product_dict.get(vat_field) if vat_field else None
        if raw in (None, ""):
            return None
        try:
            cart_vat = float(raw)
        except (ValueError, TypeError):
            return None

        company = backend._get_company()
        fpos = (
            self.env["account.fiscal.position"]
            .with_company(company)
            ._get_fiscal_position(backend.partner_id)
            if backend.partner_id
            else self.env["account.fiscal.position"]
        )
        default_taxes = product.supplier_taxes_id._filter_taxes_by_company(company)
        if fpos:
            default_taxes = fpos.map_tax(default_taxes)
        default_rate = sum(
            default_taxes.filtered(lambda t: t.amount_type == "percent").mapped(
                "amount"
            )
        )
        if abs(cart_vat - default_rate) < 0.01:
            return None  # the chain already matches the cart

        override = self.env["account.tax"].search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount_type", "=", "percent"),
                ("amount", "=", cart_vat),
                ("price_include", "=", False),
            ],
            order="name",
            limit=1,
        )
        if not override:
            _logger.warning(
                "punchout_oci: cart VATPERCENTAGE=%s%% for %r has no matching "
                "purchase tax on company %s; keeping the product default "
                "(%s%%).",
                cart_vat,
                product_dict.get("DESCRIPTION", product.display_name),
                company.name,
                default_rate,
            )
            return None
        if fpos:
            override = fpos.map_tax(override)
        _logger.info(
            "punchout_oci: cart VATPERCENTAGE=%s%% overrides product default "
            "%s%% -> %s on line %r.",
            cart_vat,
            default_rate,
            override.mapped("name"),
            product_dict.get("DESCRIPTION", product.display_name),
        )
        return override

    def _oci_barcode_from_cart(self, product_dict):
        """Return a GTIN/EAN barcode for an auto-created product, or None.

        The source cart field is configured per backend via
        ``oci_barcode_field`` (default ``VENDORMAT``); clear it to disable
        barcode mapping (customers who keep their own barcodes). Only a
        GTIN-shaped value (8/12/13/14 digits) not already claimed by
        another product is accepted -- the barcode unique constraint would
        otherwise abort the whole cart import.
        """
        self.ensure_one()
        src = (self.backend_id.oci_barcode_field or "").strip()
        if not src:
            return None
        value = (product_dict.get(src) or "").strip()
        if not (value.isdigit() and len(value) in (8, 12, 13, 14)):
            return None
        if self.env["product.product"].search_count([("barcode", "=", value)]):
            return None
        return value

    def _get_or_create_product_oci(self, product_dict):
        """Find existing product by supplier info or create a new one."""
        self.ensure_one()
        backend = self.backend_id
        Product = self.env["product.product"]

        vendor_mat = product_dict.get("VENDORMAT", "")
        description = product_dict.get("DESCRIPTION", "Unknown Product")

        # Match by supplier product code. The two conditions on
        # ``seller_ids`` MUST go through ``any`` so they apply to the
        # SAME supplierinfo row. With two separate ``seller_ids.field``
        # leaves, Odoo's ORM matches across rows — a product with
        # vendor A's code "ABC" plus vendor B (the punchout supplier)
        # on its supplier list would falsely match a vendor B cart
        # line for "ABC", because one row satisfies the partner check
        # and a different row satisfies the code check.
        if vendor_mat and backend.partner_id:
            matches = Product.search(
                [
                    (
                        "seller_ids",
                        "any",
                        [
                            ("partner_id", "=", backend.partner_id.id),
                            ("product_code", "=", vendor_mat),
                        ],
                    ),
                ]
            )
            if len(matches) > 1:
                _logger.warning(
                    "[punchout.oci.match] backend=%s vendor_code=%s matched "
                    "%d products (%s); picking the first deterministically.",
                    backend.name,
                    vendor_mat,
                    len(matches),
                    matches.mapped("display_name"),
                )
            if matches:
                return matches[0]

        # Create new product if auto_create_products is enabled
        if backend.auto_create_products:
            uom = self._get_uom_for_oci_item(product_dict)
            # Backend-driven defaults (type, is_storable, tracking,
            # categ_id) — see
            # ``punchout.backend._get_auto_create_product_defaults``.
            # Replaces the previously hardcoded ``type="consu"`` so
            # spare-parts vendors can default to storable inventory
            # in one config knob.
            product_vals = {
                "name": description,
                "uom_id": uom.id,
                **backend._get_auto_create_product_defaults(),
            }
            # Barcode: copy the GTIN from the OCI cart field the backend
            # is configured to read (``oci_barcode_field``, default
            # VENDORMAT; clearable per backend to disable). Kept as a
            # reusable, config-driven mapping — see _oci_barcode_from_cart.
            barcode = self._oci_barcode_from_cart(product_dict)
            if barcode:
                product_vals["barcode"] = barcode

            # Add long description if different from main description
            longtext = product_dict.get("LONGTEXT", "")
            if longtext and longtext != description:
                product_vals["description_purchase"] = longtext

            # Add supplier info
            if backend.partner_id:
                price = float(product_dict.get("PRICE", 0))
                leadtime = int(float(product_dict.get("LEADTIME", 0)))
                # OCI's NEW_ITEM-CURRENCY[n] is an ISO code (TVH sends "EUR").
                # product.supplierinfo.currency_id is NOT NULL since
                # Odoo 18, so we MUST resolve a record. Fall back to
                # the company currency when the cart's code is unknown
                # (or absent) so we never trip the constraint.
                currency_code = product_dict.get("CURRENCY", "")
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
                            "product_code": vendor_mat,
                            "product_name": description,
                            "price": price,
                            "delay": leadtime,
                            "currency_id": currency.id,
                            # Pin the row to the backend's company.
                            # Without this Odoo defaults to env.company
                            # at create time — in a multi-company setup
                            # whichever company happened to be active
                            # when the cart was processed wins, even
                            # when the backend is configured to only
                            # buy from this supplier under a specific
                            # company. ``backend._get_company()``
                            # returns ``backend.company_id`` when set,
                            # falling back to env.company so single-
                            # company installs still work.
                            "company_id": backend._get_company().id,
                        },
                    )
                ]

            product = Product.sudo().create(product_vals)
            self._post_create_product_hook(product, product_dict)
            return product

        # Hard fail rather than substituting an arbitrary
        # purchase-enabled product when nothing matches.
        raise UserError(
            self.env._(
                "Punchout cart line for vendor-code %(code)s "
                "(%(desc)s) couldn't be matched to any product, and "
                "Auto Create Products is disabled on the backend "
                "%(backend)s. Either enable it, or pre-create the "
                "product and add %(supplier)s to its Vendors tab "
                "with code %(code)s before re-running the punchout.",
                code=vendor_mat or "(none)",
                desc=description,
                backend=backend.display_name,
                supplier=(
                    backend.partner_id.display_name
                    if backend.partner_id
                    else "(no supplier configured)"
                ),
            )
        )

    def _post_create_product_hook(self, product, raw_data):
        """Hook fired after a product is auto-created from a punchout
        cart. Empty in base — override in private/glue modules to
        enrich the product (image, dimensions, HS code, brand, etc.)
        from the supplier's REST API. ``raw_data`` is the protocol-
        specific cart-line dict (OCI ``NEW_ITEM-*`` form data here)
        so overrides can pull supplier-specific keys (e.g. VENDORMAT)
        without re-parsing the whole cart.

        Hook fires once per newly-created product, never on existing
        product matches. Failures inside the hook MUST be caught by
        the override — the cart-import flow should never break
        because an enrichment call timed out."""

    def _get_uom_for_oci_item(self, product_dict):
        """Get UoM for OCI item, using the full punchout.uom.mapping chain."""
        self.ensure_one()
        uom_code = product_dict.get("UNIT", "")
        if uom_code:
            uom = self.env["punchout.uom.mapping"]._get_uom_by_supplier_code(
                self.backend_id, uom_code
            )
            if uom:
                return uom
        return self.env.ref("uom.product_uom_unit")
