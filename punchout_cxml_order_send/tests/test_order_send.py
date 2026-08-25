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


_OK = b'<?xml version="1.0"?><cXML><Response><Status code="200" text="OK"/></Response></cXML>'
_REJECT = b'<?xml version="1.0"?><cXML><Response><Status code="500" text="Order rejected"/></Response></cXML>'


@tagged("post_install", "-at_install")
class TestOrderSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
                "cxml_order_send": True,
                "order_request_url": "https://supplier.example/cxml/order",
            }
        )
        cls.product = cls.env["product.template"].create(
            {
                "name": "Hex bolt M8x40",
                "seller_ids": [
                    (0, 0, {"partner_id": cls.supplier.id, "product_code": "MAN-123"})
                ],
            }
        ).product_variant_id
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

    def test_no_backend_raises(self):
        self.backend.cxml_order_send = False
        with self.assertRaises(UserError):
            self.po.action_send_cxml_order()

    def test_missing_endpoint_raises(self):
        self.backend.order_request_url = False
        with self.assertRaises(UserError):
            self.po.action_send_cxml_order()
