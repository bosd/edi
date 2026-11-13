# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# pylint: disable=protected-access,missing-class-docstring,missing-function-docstring
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


class _Resp:
    def __init__(self, content, ok=True, status_code=200, reason="OK"):
        self.content = content
        self.text = content.decode() if isinstance(content, bytes) else content
        self.ok = ok
        self.status_code = status_code
        self.reason = reason
        self.url = "https://supplier.example/cxml/order"


_OK = (
    b'<?xml version="1.0"?><cXML><Response>'
    b'<Status code="200" text="OK"/></Response></cXML>'
)
_REJECT = (
    b'<?xml version="1.0"?><cXML><Response>'
    b'<Status code="500" text="Order rejected"/></Response></cXML>'
)


@tagged("post_install", "-at_install")
class TestOrderSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cxml_channel = cls.env.ref("punchout_cxml_order_send.transmission_cxml")
        cls.manual_channel = cls.env.ref("punchout.transmission_manual")
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Manutan", "is_company": True}
        )
        cls.backend = cls.env["punchout.backend"].create(
            {
                "name": "Manutan test",
                "description": "Manutan",
                "protocol": "cxml",
                "url": "https://m.example/setup",
                "browser_form_post_url": "/punchout/cxml/receive/",
                "from_domain": "DUNS",
                "from_identity": "ODOONLMANU",
                "to_domain": "DUNS",
                "to_identity": "417526183",
                "shared_secret": "s3cr3t",
                "partner_id": cls.supplier.id,
                "supported_transmission_ids": [
                    (6, 0, (cls.manual_channel | cls.cxml_channel).ids)
                ],
                "order_transmission_id": cls.cxml_channel.id,
                "order_request_url": "https://supplier.example/cxml/order",
            }
        )
        cls.product = (
            cls.env["product.template"]
            .create(
                {
                    "name": "Hex bolt M8x40",
                    "seller_ids": [
                        (
                            0,
                            0,
                            {"partner_id": cls.supplier.id, "product_code": "MAN-123"},
                        )
                    ],
                }
            )
            .product_variant_id
        )
        cls.po = cls.env["purchase.order"].create(
            {
                "partner_id": cls.supplier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_qty": 5,
                            "price_unit": 3.75,
                            "name": "Hex bolt M8x40",
                        },
                    )
                ],
            }
        )

    def test_capable_flag(self):
        self.assertTrue(self.po.cxml_order_capable)

    def test_render_contains_orderrequest_and_partnumber(self):
        cxml = self.po._render_cxml_order_request(self.backend)
        self.assertIn("<OrderRequest>", cxml)
        self.assertIn("MAN-123", cxml)  # supplier part number
        self.assertIn("ODOONLMANU", cxml)  # buyer identity
        self.assertIn("417526183", cxml)  # supplier identity
        self.assertIn("<ItemOut", cxml)

    def test_supplier_aux_id_emitted_when_present(self):
        """Suppliers like Topgeschenken need the cart-item UUID echoed
        back as SupplierPartAuxiliaryID; emit it only when the line
        carries one."""
        cxml = self.po._render_cxml_order_request(self.backend)
        self.assertNotIn("SupplierPartAuxiliaryID", cxml)

        self.po.order_line.punchout_supplier_aux_id = "AUX-UUID-42"
        cxml = self.po._render_cxml_order_request(self.backend)
        self.assertIn("<SupplierPartAuxiliaryID>AUX-UUID-42", cxml)

    def test_send_success_sets_state(self):
        with patch("requests.post", return_value=_Resp(_OK)):
            self.po.action_send_cxml_order()
        self.assertTrue(self.po.cxml_order_sent)
        self.assertTrue(self.po.cxml_order_sent_date)

    def test_send_rejected_raises(self):
        with patch("requests.post", return_value=_Resp(_REJECT)):
            with self.assertRaises(UserError):
                self.po.action_send_cxml_order()
        self.assertFalse(self.po.cxml_order_sent)

    def test_send_flag_follows_order_transmission(self):
        """The cXML send flag is derived from the Order transmission choice."""
        self.assertTrue(self.backend.cxml_order_send)
        self.backend.order_transmission_id = self.manual_channel
        self.assertFalse(self.backend.cxml_order_send)
        self.assertFalse(self.po.cxml_order_capable)
        self.backend.order_transmission_id = self.cxml_channel
        self.assertTrue(self.backend.cxml_order_send)

    def test_no_backend_raises(self):
        self.backend.order_transmission_id = self.manual_channel
        with self.assertRaises(UserError):
            self.po.action_send_cxml_order()

    def test_missing_endpoint_raises(self):
        self.backend.order_request_url = False
        with self.assertRaises(UserError):
            self.po.action_send_cxml_order()

    def test_fabory_preset_has_no_cxml_channel(self):
        """Fabory takes e-PDF orders only: cXML is not a supported channel."""
        fabory = self.env.ref("punchout_cxml.preset_fabory").with_context(
            active_test=False
        )
        self.assertNotIn(self.cxml_channel, fabory.supported_transmission_ids)
        manutan = self.env.ref("punchout_cxml.preset_manutan").with_context(
            active_test=False
        )
        self.assertIn(self.cxml_channel, manutan.supported_transmission_ids)
