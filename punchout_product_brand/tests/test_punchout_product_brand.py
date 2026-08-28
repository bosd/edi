# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from uuid import uuid4

from odoo.tests.common import TransactionCase


class TestPunchoutProductBrand(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["punchout.backend"].create(
            {
                "name": str(uuid4()),
                "description": str(uuid4()),
                "protocol": "oci",
                "url": "https://example.com/punchout",
                "browser_form_post_url": "/punchout/oci/receive/",
                "auto_create_products": True,
            }
        )
        cls.Mapping = cls.env["punchout.field.mapping"]
        cls.product = cls.env["product.product"].create({"name": "Brand target"})

    def test_brand_target_registered(self):
        targets = dict(self.Mapping._selection_target())
        self.assertIn("brand", targets)

    def test_brand_find_or_create_by_name(self):
        self.Mapping.create(
            {
                "backend_id": self.backend.id,
                "source_field": "BRAND",
                "target": "brand",
            }
        )
        self.backend._apply_product_field_mappings(self.product, {"BRAND": "Sick"})
        self.assertTrue(self.product.product_brand_id)
        self.assertEqual(self.product.product_brand_id.name, "Sick")

    def test_brand_matches_existing_case_insensitive(self):
        existing = self.env["product.brand"].create({"name": "Bosch"})
        self.Mapping.create(
            {
                "backend_id": self.backend.id,
                "source_field": "BRAND",
                "target": "brand",
            }
        )
        self.backend._apply_product_field_mappings(self.product, {"BRAND": "bosch"})
        self.assertEqual(self.product.product_brand_id, existing)

    def test_brand_code_via_lookup_table(self):
        rule = self.Mapping.create(
            {
                "backend_id": self.backend.id,
                "source_field": "BRANDCODE",
                "target": "brand",
                "value_transform": "lookup_table",
            }
        )
        self.env["punchout.value.mapping"].create(
            {"mapping_id": rule.id, "raw": "4471", "value": "Sick"}
        )
        self.backend._apply_product_field_mappings(self.product, {"BRANDCODE": "4471"})
        self.assertEqual(self.product.product_brand_id.name, "Sick")

    def test_brand_fill_if_empty_preserves_existing(self):
        original = self.env["product.brand"].create({"name": "Original"})
        self.product.product_brand_id = original
        self.Mapping.create(
            {
                "backend_id": self.backend.id,
                "source_field": "BRAND",
                "target": "brand",
            }
        )
        self.backend._apply_product_field_mappings(self.product, {"BRAND": "Sick"})
        self.assertEqual(self.product.product_brand_id, original)
