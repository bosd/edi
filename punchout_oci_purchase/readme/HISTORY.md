## 19.0.1.4.0 (2026)

- [IMP] Barcode and VAT mapping are now config-driven per backend
  (``oci_barcode_field`` / ``oci_vat_field`` on the backend, set in the
  preset). The barcode source cart field is configurable and clearable
  (disable per customer), via the reusable ``_oci_barcode_from_cart``
  helper; the VAT guard reads its source field from the backend too.
  No hardcoded ``VENDORMAT`` / ``VATPERCENTAGE``.

## 19.0.1.3.0 (2026)

- [IMP] Honour the OCI ``PRICEUNIT`` price basis: the line's unit price
  is ``PRICE / PRICEUNIT`` (was ``PRICE`` verbatim), so a supplier
  quoting a price per pack no longer books that price per unit.
- [IMP] VAT guard: when a cart line's ``VATPERCENTAGE`` differs from the
  rate Odoo's product / fiscal-position chain would apply, force a
  matching-rate purchase tax (e.g. a reduced-rate item that auto-creates
  a product defaulting to the standard rate). Standard-rate lines keep
  the smarter default chain.
- [IMP] Set the auto-created product's barcode from a GTIN/EAN
  ``VENDORMAT`` (guarded on uniqueness).

## 19.0.1.2.0 (2026)

- [FIX] Pin auto-created `product.supplierinfo.company_id` to the
  backend's company. Without this, the row defaulted to
  `self.env.company` at create time — in a multi-company setup the
  active company at cart-process time would win, even when the
  backend was configured to only buy from this supplier under a
  specific company. Surfaces as ghost seller rows visible only in
  some company contexts.

## 18.0.1.0.0 (2026)

- [ADD] First version: OCI cart → purchase order glue.
- [IMP] UoM lookup routed through
  `punchout.uom.mapping._get_uom_by_supplier_code` (full 6-tier
  resolution).
- [FIX] Drop `detailed_type` from auto-created products
  (Odoo 18 removed the field).
- [FIX] Use `supplier_code` (not the non-existent `external_code`) when
  scanning backend UoM mappings.
- [FIX] Auto-created products now carry the supplier-provided UoM, so
  the resulting order line doesn't trip the same-category constraint.
- [IMP] Warn (logger) when a vendor code matches multiple products
  for the same partner. Picks the first deterministically rather
  than silently. Surfaces stale supplierinfo data without breaking
  the punchout flow.
- [ADD] `_post_create_product_hook(product, raw_data)` — empty
  extension point fired once per newly-created product. Lets private
  / glue modules enrich the product (image, dimensions, HS code,
  brand) from the supplier's REST API without monkey-patching.
  ``raw_data`` is the OCI cart-line dict.
