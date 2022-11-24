# Copyright 2015-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Invoice Import Invoice2data",
    "version": "14.0.1.0.1",
    "category": "Accounting/Accounting",
    "license": "AGPL-3",
    "summary": "Import supplier invoices using the invoice2data lib",
    "author": "Akretion,Odoo Community Association (OCA)",
    "maintainers": ["alexis-via"],
    "website": "https://github.com/OCA/edi",
    "depends": ["account_invoice_import", "mail"],
    # "excludes": ["account_invoice_import_simple_pdf"],
    "external_dependencies": {
        "python": [
            "invoice2data",
            # https://github.com/OCA/edi/issues/544
            "dateparser==1.1.1",
        ],
        "deb": ["poppler-utils"],
    },
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "views/invoice2data_template.xml",
        "wizard/account_invoice_import_view.xml",
    ],
    "demo": ["demo/demo_data.xml"],
    "installable": True,
}
