# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

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
            self.env._(
                "Your request has been sent to the Punchout Manager."
            )
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
