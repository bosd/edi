# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    punchout_session_id = fields.Many2one(
        comodel_name="punchout.session",
        string="Punchout Session",
        readonly=True,
        copy=False,
    )

    def action_view_punchout_session(self):
        """Open the related punchout session."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "punchout.session",
            "view_mode": "form",
            "res_id": self.punchout_session_id.id,
        }
