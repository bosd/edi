# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from .common import TestPunchoutPurchaseCommon


class TestPunchoutPurchase(TestPunchoutPurchaseCommon):
    def test_session_purchase_order_link(self):
        """Test that session has purchase_order_id field."""
        self.assertFalse(self.session.purchase_order_id)
        self.assertEqual(self.session.purchase_order_count, 0)

    def test_backend_has_partner(self):
        """Test that backend has partner configured."""
        self.assertEqual(self.backend.partner_id, self.partner)

    def test_backend_has_auto_create_products(self):
        """Test that backend has auto_create_products flag."""
        self.assertTrue(self.backend.auto_create_products)

    def test_create_purchase_order_no_partner(self):
        """Test that creating PO without partner raises error."""
        self.backend.partner_id = False
        with self.assertRaises(UserError):
            self.session._create_purchase_order_from_response()

    def test_create_purchase_order_wrong_state(self):
        """Test that creating PO with wrong state raises error."""
        self.session.state = "draft"
        with self.assertRaises(UserError):
            self.session.action_create_purchase_order()

    def test_prepare_purchase_order_vals(self):
        """Test that PO values are prepared correctly."""
        vals = self.session._prepare_purchase_order_vals()
        self.assertEqual(vals["partner_id"], self.partner.id)
        self.assertEqual(vals["punchout_session_id"], self.session.id)

    def test_purchase_order_has_session_link(self):
        """Test that purchase.order has punchout_session_id field."""
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "punchout_session_id": self.session.id,
            }
        )
        self.assertEqual(order.punchout_session_id, self.session)
