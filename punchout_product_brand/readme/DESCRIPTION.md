Bridge module that adds a **brand** target to the punchout cart
field-mapping framework (`punchout_purchase`). When a supplier's cart
returns a brand — as a name or as a code — a mapping rule can write it
onto the auto-created product's `product_brand_id`.

It exists as a separate add-on because the brand field comes from the
optional OCA `product_brand` module: keeping the target here means the
core punchout stack never depends on `product_brand`. Install this
bridge only where `product_brand` is present; it then auto-installs.
