## First-class product Classification field

cXML `ItemDetail/Classification` carries one or more standard product
codes (UNSPSC, eCl@ss, NAICS, supplier-internal taxonomies) tagged by
the `domain` attribute. Today this module appends them as a labelled
footer to `product.description_purchase`:

```
[Classification]
UNSPSC: 31162400
eCl@ss: 23-23-19-01
```

That gives the buyer the information at point-of-purchase (visible on
the PO line description) without inventing a schema, but it isn't
queryable, doesn't survive product re-imports cleanly, and can't be
mapped to internal product categories.

The proper fix is a generic `product.classification` model (m2m or
o2m on `product.template`) with a `domain` selection (UNSPSC, eCl@ss,
custom) and a free-text `code`. This belongs upstream — either in OCA
`product` or as a dedicated `product_classification` module — because
the same data flows in via EDI imports, supplier feeds, and PIM
syncs, not just punchout. When that module exists, this glue should
write to the structured field and stop touching `description_purchase`.

## PriceBasisQuantity handling

cXML `ItemDetail/PriceBasisQuantity` lets the supplier quote a price
per N units instead of per single unit (e.g. "EUR 12.00 per 100
pieces"). Today this module ignores the element and treats every
`UnitPrice/Money` as price-per-1, which is correct for every supplier
we've round-tripped so far (Fabory's cart sends each line as 1:1).

A robust implementation needs to:

1. Read `PriceBasisQuantity/@quantity` (the conversion factor) and
   `PriceBasisQuantity/UnitOfMeasure` (which may differ from the order
   UoM — e.g. quoted per 100 pieces but ordered as a single carton).
2. Either divide `UnitPrice/Money` by the conversion factor before
   storing on the PO line (simplest, matches Odoo's per-unit price
   semantics), or set `product.uom_po_id` and `product.seller_ids.min_qty`
   so Odoo's own price-per-package logic kicks in (cleaner, but touches
   more product-side configuration and risks collisions when multiple
   suppliers quote the same product with different basis quantities).
3. Round to the product currency's decimal precision after conversion
   to avoid sub-cent drift.

Defer until a real supplier sends a non-1 PriceBasisQuantity. When
they do, prefer option 1 unless the supplier also pushes minimum-order
quantities, in which case option 2 starts paying off.
