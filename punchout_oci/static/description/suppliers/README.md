# Supplier logos

PNG files in this directory back two things:

1. The supplier's `image_128` field on its preset record in
   `../../data/supplier_presets.xml` — loaded via Odoo's
   `<field name="image_128" type="base64" file="..."/>` convention so there's a single
   source of truth.
2. The Logo column in the supplier table in `../../readme/CONFIGURE.md` — referenced via
   relative path from the module's rendered README so the same file appears inline.

## Conventions

- File name: lowercase supplier slug matching the preset's XML id stem (e.g. `indi.png`
  for `preset_indi`, `phoenix_contact.png` for `preset_phoenix_contact`).
- Format: PNG with transparent background.
- Size: 128 × 128 px ceiling (Odoo's `image_128` field caps at this anyway). Smaller is
  fine; the field stretches small images to display size.
- Source: download from the supplier's own site / brand resources. Crop to the brand
  mark (no marketing taglines). This is nominative use — showing which supplier this
  preset connects to — and is the same pattern OCA uses for shipping connectors, payment
  provider modules, etc.

## Adding a logo for an existing preset

1. Drop the PNG here.
2. Edit the preset record in `../../data/supplier_presets.xml`:
   ```xml
   <field name="image_128" type="base64"
          file="punchout_oci/static/description/suppliers/<slug>.png"/>
   ```
3. Add a logo cell to the matching row in `../../readme/CONFIGURE.md`:
   ```markdown
   ![<supplier name>](static/description/suppliers/<slug>.png)
   ```
4. Bump the patch version in `__manifest__.py`.
