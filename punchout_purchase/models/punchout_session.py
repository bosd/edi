# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class PunchoutSession(models.Model):
    _inherit = "punchout.session"

    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        readonly=True,
    )
    purchase_order_count = fields.Integer(
        compute="_compute_purchase_order_count",
    )

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = 1 if rec.purchase_order_id else 0

    def action_view_purchase_order(self):
        """Open the related purchase order."""
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_("No purchase order linked to this session."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_order_id.id,
        }

    def action_create_purchase_order(self):
        """Create a purchase order from the session response."""
        self.ensure_one()
        if self.purchase_order_id:
            raise UserError(_("A purchase order already exists for this session."))
        if self.state != "to_process":
            raise UserError(
                _("Session must be in 'To Process' state to create a purchase order.")
            )

        order = self._create_purchase_order_from_response()
        self.write(
            {
                "purchase_order_id": order.id,
                "state": "done",
            }
        )
        return self.action_view_purchase_order()

    def _create_purchase_order_from_response(self):
        """Create purchase order from response. Override in protocol modules."""
        self.ensure_one()
        backend = self.backend_id
        if not backend.partner_id:
            raise UserError(
                _("Please configure a supplier on the backend %(name)s.")
                % {"name": backend.display_name}
            )

        order_vals = self._prepare_purchase_order_vals()
        return self.env["purchase.order"].create(order_vals)

    def _prepare_purchase_order_vals(self):
        """Prepare values for purchase order creation."""
        self.ensure_one()
        backend = self.backend_id
        return {
            "partner_id": backend.partner_id.id,
            "company_id": backend._get_company().id,
            "punchout_session_id": self.id,
            "order_line": self._prepare_purchase_order_lines(),
        }

    def _prepare_purchase_order_lines(self):
        """Prepare order lines from response. Override in protocol modules."""
        # This should be overridden by protocol-specific modules
        return []

    def _get_redirect_url(self):
        """Redirect to purchase order after processing."""
        self.ensure_one()
        if self.purchase_order_id:
            order_id = self.purchase_order_id.id
            return f"/web#id={order_id}&model=purchase.order&view_type=form"
        return super()._get_redirect_url()
