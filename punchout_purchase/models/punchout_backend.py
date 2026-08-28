# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Guardrails for the image-from-URL target: cart-supplied URLs are fetched
# server-side, so cap the payload and only accept genuine image responses.
_IMAGE_MAX_BYTES = 8 * 1024 * 1024
_IMAGE_TIMEOUT = 20


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    field_mapping_ids = fields.One2many(
        comodel_name="punchout.field.mapping",
        inverse_name="backend_id",
        string="Cart field mappings",
        help=(
            "Per-supplier rules mapping cart fields to Odoo product fields "
            "(barcode, image, brand, …). Shipped in the preset; a Punchout "
            "Manager can adjust them."
        ),
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Supplier",
        help="Default supplier for purchase orders created from this backend.",
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product Category",
        help="When creating new products, use this category instead of the default.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    auto_create_products = fields.Boolean(
        default=True,
        help="Automatically create products from cart items if not found.",
    )
    default_product_type = fields.Selection(
        selection=[
            ("consu", "Goods"),
            ("service", "Service"),
        ],
        default="consu",
        required=True,
        help=(
            "Product type set on auto-created products from this "
            "backend. Most punchout suppliers ship physical parts → "
            "'Goods'. Use 'Service' for catalogs of installation / "
            "labour services."
        ),
    )
    default_is_storable = fields.Boolean(
        string="Default storable",
        help=(
            "When enabled, auto-created products are marked storable "
            "(``is_storable=True``). Requires the ``stock`` module. "
            "Set this if the parts arriving from this supplier should "
            "track inventory in your warehouse — typical for spare-"
            "parts vendors. The field is silently ignored if "
            "``is_storable`` doesn't exist on ``product.template`` "
            "(stock module not installed)."
        ),
    )
    default_tracking = fields.Selection(
        selection=[
            ("none", "By Quantity"),
            ("lot", "By Lots"),
            ("serial", "By Unique Serial Number"),
        ],
        default="none",
        required=True,
        string="Default inventory tracking",
        help=(
            "Inventory-tracking method for auto-created storable "
            "products. Only applied when ``default_is_storable`` is "
            "True and the ``stock`` module is installed."
        ),
    )

    punchout_hide_setup_hint = fields.Boolean(
        string="Hide setup hint",
        help=(
            "Suppress the 'punchout available — ask your ERP manager to "
            "activate it' hint shown to buyers on this supplier's contact "
            "and POs while the backend isn't live. Tick it for backends "
            "you deliberately keep parked (evaluated but not adopted) so "
            "the hint doesn't nag."
        ),
    )

    def _get_company(self):
        """Return the company for this backend."""
        self.ensure_one()
        return self.company_id or self.env.company

    def _punchout_notify(self, message, warning=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if warning else "success",
                "message": message,
                "sticky": False,
            },
        }

    def _request_punchout_setup(self, requester=None):
        """Raise a request for the Punchout Manager to activate this
        (dormant) backend. Schedules a To-Do activity for each manager and
        posts a chatter note; de-duplicates so repeated buyer clicks don't
        stack activities. Returns a user notification."""
        self.ensure_one()
        requester = requester or self.env.user
        managers = (
            self.env.ref("punchout_purchase.group_punchout_manager")
            .sudo()
            .user_ids.filtered("active")
        )
        if not managers:
            return self._punchout_notify(
                self.env._(
                    "No Punchout Manager is configured — please ask your "
                    "administrator to set one up."
                ),
                warning=True,
            )
        summary = self.env._("Punchout setup requested")
        note = self.env._(
            "%(user)s asked to activate punchout ordering for %(supplier)s.",
            user=requester.display_name,
            supplier=(self.partner_id.display_name or self.display_name),
        )
        already = self.activity_ids.filtered(lambda a: a.summary == summary)
        if not already:
            for manager in managers:
                self.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=manager.id,
                    summary=summary,
                    note=note,
                )
            self.sudo().message_post(body=note)
        return self._punchout_notify(
            self.env._("Your request has been sent to the Punchout Manager.")
        )

    def _get_auto_create_product_defaults(self):
        """Return a dict of default field values to apply to products
        auto-created from a punchout cart on this backend.

        Centralises ``type``, ``is_storable``, ``tracking`` and
        ``categ_id`` so the per-protocol ``_get_or_create_product_*``
        methods don't each need to consult half a dozen backend
        fields. Stock-aware fields are only emitted when their
        ``product.template`` field exists in this Odoo install
        (``stock`` module installed) — keeps the punchout stack
        usable on installs without ``stock``.
        """
        self.ensure_one()
        vals = {
            "type": self.default_product_type,
            "purchase_ok": True,
        }
        if self.product_category_id:
            vals["categ_id"] = self.product_category_id.id
        # Stock-only fields: emit only when present on the model.
        product_template_fields = self.env["product.template"]._fields
        if "is_storable" in product_template_fields:
            vals["is_storable"] = self.default_is_storable
        if self.default_is_storable and "tracking" in product_template_fields:
            vals["tracking"] = self.default_tracking
        return vals

    # ------------------------------------------------------------------
    # Cart-field mapping engine
    # ------------------------------------------------------------------
    def _apply_product_field_mappings(self, product, source):
        """Apply this backend's active cart-field mappings to ``product``.

        ``source`` is the protocol-flattened cart line — a plain
        ``{source_field: value}`` dict produced by the protocol module
        (OCI's ``NEW_ITEM-*`` keys, cXML's flattened element keys). Each
        rule resolves its raw value (direct or via its lookup table) and
        dispatches to ``_punchout_map_<target>``. Runs on both freshly
        auto-created products and re-punchout matches; each handler is
        responsible for the fill-if-empty / overwrite decision.

        Never raises: a bad rule, a dead image URL or an unknown target
        must not break the cart import — it is logged and skipped.
        """
        self.ensure_one()
        if not product or not source:
            return
        for rule in self.field_mapping_ids.filtered("active"):
            raw = source.get(rule.source_field)
            if raw in (None, "", False):
                continue
            value = rule._resolve_value(raw)
            if not value:
                continue
            handler = getattr(self, f"_punchout_map_{rule.target}", None)
            if handler is None:
                _logger.warning(
                    "[punchout.map] backend %s: no handler for target %r",
                    self.name,
                    rule.target,
                )
                continue
            try:
                handler(product, value, overwrite=rule.overwrite)
            except Exception as exc:  # noqa: BLE001 — never break the import
                _logger.warning(
                    "[punchout.map] backend %s: target %s failed on %s: %s",
                    self.name,
                    rule.target,
                    product.display_name,
                    exc,
                )

    def _punchout_map_barcode(self, product, value, overwrite=False):
        """Set the product barcode from a GTIN-shaped cart value.

        Only 8/12/13/14-digit values not already claimed by another
        product are accepted — the barcode unique constraint would
        otherwise abort the whole cart import."""
        if product.barcode and not overwrite:
            return
        code = str(value).strip()
        if not (code.isdigit() and len(code) in (8, 12, 13, 14)):
            _logger.info(
                "[punchout.map] %r is not a GTIN (8/12/13/14 digits); "
                "skipping barcode for %s.",
                code,
                product.display_name,
            )
            return
        clash = self.env["product.product"].search(
            [("barcode", "=", code), ("id", "!=", product.id)], limit=1
        )
        if clash:
            _logger.info(
                "[punchout.map] barcode %s already on %s; skipping for %s.",
                code,
                clash.display_name,
                product.display_name,
            )
            return
        product.sudo().barcode = code

    def _punchout_map_description(self, product, value, overwrite=False):
        """Set / append the supplier long text onto ``description_purchase``."""
        text = str(value).strip()
        if not text:
            return
        existing = product.description_purchase or ""
        if overwrite or not existing:
            product.sudo().description_purchase = text
        elif text not in existing:
            product.sudo().description_purchase = (existing + "\n" + text).strip()

    def _punchout_map_product_code(self, product, value, overwrite=False):
        """Set the supplier's product code on the backend-supplier's
        ``product.supplierinfo`` row for this product."""
        if not self.partner_id:
            return
        seller = product.seller_ids.filtered(
            lambda s, p=self.partner_id: s.partner_id == p
        )[:1]
        if seller and (overwrite or not seller.product_code):
            seller.sudo().product_code = str(value).strip()

    def _punchout_map_unspsc_category(self, product, value, overwrite=False):
        """Placeholder for UNSPSC (cart ``MATGROUP``) → product category.

        The value is logged; wiring UNSPSC codes to ``product.category``
        needs a code→category table and is tracked on the ROADMAP."""
        _logger.info(
            "[punchout.map] UNSPSC %s for %s — category mapping deferred "
            "(see ROADMAP).",
            value,
            product.display_name,
        )

    def _punchout_map_image(self, product, value, overwrite=False):
        """Download the supplier image URL and set it as the product image."""
        if product.image_1920 and not overwrite:
            return
        data = self._punchout_download_image(str(value).strip())
        if data:
            product.sudo().image_1920 = data

    def _punchout_download_image(self, url, max_bytes=_IMAGE_MAX_BYTES):
        """Fetch an image URL server-side and return base64 bytes, or None.

        Hardened for untrusted, supplier-supplied URLs: http(s) only, a
        request timeout, a hard size cap enforced while streaming (not just
        trusting Content-Length), and an ``image/*`` content-type check."""
        if not url.lower().startswith(("http://", "https://")):
            return None
        try:
            resp = requests.get(
                url,
                timeout=_IMAGE_TIMEOUT,
                stream=True,
                headers={"User-Agent": "OBS-Odoo-Punchout/19.0"},
            )
            resp.raise_for_status()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
            if not ctype.lower().startswith("image/"):
                _logger.info(
                    "[punchout.map] %s returned %r, not an image; skipping.",
                    url,
                    ctype,
                )
                return None
            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                _logger.info(
                    "[punchout.map] image %s declares %s bytes (> %s); skipping.",
                    url,
                    declared,
                    max_bytes,
                )
                return None
            payload = b""
            for chunk in resp.iter_content(8192):
                payload += chunk
                if len(payload) > max_bytes:
                    _logger.info(
                        "[punchout.map] image %s exceeded %s bytes; aborting.",
                        url,
                        max_bytes,
                    )
                    return None
            return base64.b64encode(payload) if payload else None
        except Exception as exc:  # noqa: BLE001 — enrichment must never fail hard
            _logger.warning("[punchout.map] image download failed for %s: %s", url, exc)
            return None
