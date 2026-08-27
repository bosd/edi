## 19.0.1.1.0 (2026)

- [ADD] Emit ``SupplierPartAuxiliaryID`` per order line in the cXML
  OrderRequest when the line carries a
  ``punchout_supplier_aux_id`` (captured from the punchout cart by
  ``punchout_cxml_purchase``). Suppliers such as Topgeschenken require
  this to match the order line back to the original cart item.

## 19.0.1.0.0 (2026)

- Initial release: send a confirmed purchase order to the supplier as a
  cXML ``OrderRequest``.
