# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Retire ``oci_barcode_field`` in favour of the cart field-mapping
framework (``punchout.field.mapping``).

Preset backends get their ``VENDORMAT -> barcode`` rule from the shipped
``punchout_oci_purchase`` data file, so this only converts *non-preset*
OCI backends (created by hand / RPC) that had a barcode source configured,
then drops the column. Runs before the ORM removes the field.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    # The mapping framework (punchout_purchase) must be present.
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'punchout_field_mapping'"
    )
    if not cr.fetchone():
        return
    # Idempotent: bail if the column is already gone.
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'punchout_backend' "
        "AND column_name = 'oci_barcode_field'"
    )
    if not cr.fetchone():
        return
    # Preset backends receive their barcode rule from the data file —
    # skip them here so we don't create a duplicate rule.
    cr.execute(
        "SELECT res_id FROM ir_model_data "
        "WHERE module = 'punchout_oci' AND model = 'punchout.backend' "
        "AND name LIKE 'preset_%'"
    )
    preset_ids = tuple(r[0] for r in cr.fetchall()) or (0,)
    cr.execute(
        """
        SELECT b.id, b.oci_barcode_field
        FROM punchout_backend b
        WHERE b.protocol = 'oci'
          AND COALESCE(b.oci_barcode_field, '') <> ''
          AND b.id NOT IN %s
          AND NOT EXISTS (
              SELECT 1 FROM punchout_field_mapping m
              WHERE m.backend_id = b.id AND m.target = 'barcode'
          )
        """,
        (preset_ids,),
    )
    rows = cr.fetchall()
    for backend_id, source in rows:
        cr.execute(
            """
            INSERT INTO punchout_field_mapping
                (backend_id, sequence, source_field, target,
                 value_transform, overwrite, active,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, 10, %s, 'barcode', 'direct', false, true,
                    1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC')
            """,
            (backend_id, source),
        )
    _logger.info(
        "[punchout_oci] retired oci_barcode_field: migrated %d non-preset "
        "backend(s) to a barcode mapping rule.",
        len(rows),
    )
    cr.execute("ALTER TABLE punchout_backend DROP COLUMN oci_barcode_field")
