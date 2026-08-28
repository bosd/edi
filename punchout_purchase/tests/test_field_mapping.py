# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from unittest.mock import MagicMock, patch

from .common import TestPunchoutPurchaseCommon

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestPunchoutFieldMapping(TestPunchoutPurchaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mapping = cls.env["punchout.field.mapping"]
        cls.product = cls.env["product.product"].create({"name": "Mapping target"})

    def _rule(self, **vals):
        vals.setdefault("backend_id", self.backend.id)
        return self.Mapping.create(vals)

    # -- barcode ---------------------------------------------------------
    def test_barcode_valid_gtin_set(self):
        self._rule(source_field="EAN", target="barcode")
        self.backend._apply_product_field_mappings(
            self.product, {"EAN": "4047084372537"}
        )
        self.assertEqual(self.product.barcode, "4047084372537")

    def test_barcode_non_gtin_skipped(self):
        self._rule(source_field="EAN", target="barcode")
        # VENDORMAT-style code, 7 digits — not a GTIN length.
        self.backend._apply_product_field_mappings(self.product, {"EAN": "1660085"})
        self.assertFalse(self.product.barcode)

    def test_barcode_fill_if_empty_preserves_existing(self):
        self.product.barcode = "1111111111116"
        self._rule(source_field="EAN", target="barcode")
        self.backend._apply_product_field_mappings(
            self.product, {"EAN": "4047084372537"}
        )
        self.assertEqual(self.product.barcode, "1111111111116")

    def test_barcode_overwrite(self):
        self.product.barcode = "1111111111116"
        self._rule(source_field="EAN", target="barcode", overwrite=True)
        self.backend._apply_product_field_mappings(
            self.product, {"EAN": "4047084372537"}
        )
        self.assertEqual(self.product.barcode, "4047084372537")

    def test_barcode_duplicate_skipped(self):
        self.env["product.product"].create(
            {"name": "Owns EAN", "barcode": "4047084372537"}
        )
        self._rule(source_field="EAN", target="barcode")
        self.backend._apply_product_field_mappings(
            self.product, {"EAN": "4047084372537"}
        )
        self.assertFalse(self.product.barcode)

    # -- description -----------------------------------------------------
    def test_description_set_when_empty(self):
        self._rule(source_field="LONGTEXT", target="description")
        self.backend._apply_product_field_mappings(
            self.product, {"LONGTEXT": "Long spec text"}
        )
        self.assertEqual(self.product.description_purchase, "Long spec text")

    def test_description_appends_without_overwrite(self):
        self.product.description_purchase = "First"
        self._rule(source_field="LONGTEXT", target="description")
        self.backend._apply_product_field_mappings(self.product, {"LONGTEXT": "Second"})
        self.assertIn("First", self.product.description_purchase)
        self.assertIn("Second", self.product.description_purchase)

    # -- product_code ----------------------------------------------------
    def test_product_code_set_on_supplierinfo(self):
        self.product.write({"seller_ids": [(0, 0, {"partner_id": self.partner.id})]})
        self._rule(source_field="VENDORMAT", target="product_code")
        self.backend._apply_product_field_mappings(self.product, {"VENDORMAT": "AE-99"})
        seller = self.product.seller_ids.filtered(
            lambda s: s.partner_id == self.partner
        )
        self.assertEqual(seller.product_code, "AE-99")

    # -- value transform -------------------------------------------------
    def test_lookup_table_translates_value(self):
        rule = self._rule(
            source_field="CODE",
            target="description",
            value_transform="lookup_table",
        )
        self.env["punchout.value.mapping"].create(
            {"mapping_id": rule.id, "raw": "4471", "value": "Sick"}
        )
        self.backend._apply_product_field_mappings(self.product, {"CODE": "4471"})
        self.assertEqual(self.product.description_purchase, "Sick")

    def test_lookup_table_unmapped_skipped(self):
        rule = self._rule(
            source_field="CODE",
            target="description",
            value_transform="lookup_table",
        )
        self.env["punchout.value.mapping"].create(
            {"mapping_id": rule.id, "raw": "4471", "value": "Sick"}
        )
        self.backend._apply_product_field_mappings(self.product, {"CODE": "9999"})
        self.assertFalse(self.product.description_purchase)

    def test_inactive_rule_skipped(self):
        self._rule(source_field="EAN", target="barcode", active=False)
        self.backend._apply_product_field_mappings(
            self.product, {"EAN": "4047084372537"}
        )
        self.assertFalse(self.product.barcode)

    # -- image download (mocked) ----------------------------------------
    def _fake_response(self, content=_PNG, ctype="image/png"):
        resp = MagicMock()
        resp.headers = {"Content-Type": ctype, "Content-Length": str(len(content))}
        resp.raise_for_status.return_value = None
        resp.iter_content.return_value = [content]
        return resp

    def test_image_downloaded_and_set(self):
        self._rule(source_field="ATTACHMENT", target="image")
        with patch(
            "odoo.addons.punchout_purchase.models.punchout_backend.requests.get",
            return_value=self._fake_response(),
        ):
            self.backend._apply_product_field_mappings(
                self.product, {"ATTACHMENT": "https://img.example.com/x.png"}
            )
        self.assertEqual(self.product.image_1920, base64.b64encode(_PNG))

    def test_image_non_image_content_type_skipped(self):
        self._rule(source_field="ATTACHMENT", target="image")
        with patch(
            "odoo.addons.punchout_purchase.models.punchout_backend.requests.get",
            return_value=self._fake_response(content=b"<html>", ctype="text/html"),
        ):
            self.backend._apply_product_field_mappings(
                self.product, {"ATTACHMENT": "https://img.example.com/x.png"}
            )
        self.assertFalse(self.product.image_1920)

    def test_image_non_http_url_skipped(self):
        self._rule(source_field="ATTACHMENT", target="image")
        with patch(
            "odoo.addons.punchout_purchase.models.punchout_backend.requests.get"
        ) as mock_get:
            self.backend._apply_product_field_mappings(
                self.product, {"ATTACHMENT": "ftp://img.example.com/x.png"}
            )
            mock_get.assert_not_called()
        self.assertFalse(self.product.image_1920)
