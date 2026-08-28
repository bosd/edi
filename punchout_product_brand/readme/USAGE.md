On a punchout backend, add a *Cart field mapping* with target **Brand**:

- **Supplier returns a brand name** (e.g. cart field `Extrinsic:Brand` =
  "Sick"): use *value transform* **Direct**. The name is matched to an
  existing `product.brand` case-insensitively, or created if new.
- **Supplier returns a brand code** (e.g. `4471`): use *value transform*
  **Lookup table** and add a row `4471 → Sick`. The translated name is
  then matched / created as above.

By default the brand is only set when the product has none yet, so
manual corrections survive a re-punchout. Tick *Overwrite* to always
apply the supplier's brand.
