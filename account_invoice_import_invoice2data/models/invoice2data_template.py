# © 2017 Therp BV <http://therp.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import html
import json
import logging
import os
import pprint
from tempfile import mkstemp

import pkg_resources

from odoo import _, api, fields, models

try:
    from invoice2data.extract.invoice_template import InvoiceTemplate
    # from invoice2data.extract.loader import ordered_load # needs refactor
    from invoice2data.input.pdftotext import to_text
    from invoice2data.main import extract_data
    from invoice2data.extract.loader import read_templates
except ImportError:
    logging.error("Failed to import invoice2data")


'''
todo
Load files from chatter attachments
Test 1 file function
Test all chatter files function
Add a buton to import the invoice to the invoice view
add statesmanagement. draf | valid
add yaml validator
templates can only go to valid state if thet are validated.

ADD guessing framework
Write warning level messages of invoice2data to the form. (End line not found)
Template validation assertion errors?

https://github.com/OCA/server-tools/tree/14.0/jsonifier
or use method in:
https://odoo-community.org/shop/attribute-set-10356?page=2&search=json#attr=17905

'''
class Invoice2dataTemplate(models.Model):
    _name = "invoice2data.template"
    _description = "Template for invoice2data"
    _inherit = "mail.thread"

    name = fields.Char(required=True)
    template_type = fields.Selection(
        [("purchase_invoice", "Purchase Invoice")], "Type", required=False
    )
    template = fields.Text(required=True, help="Invoice2data template in JSON format")

    template_serialized = fields.Serialized()
    boolean = fields.Boolean(sparse='template_serialized')
    integer = fields.Integer(sparse='template_serialized')
    floati = fields.Float(sparse='template_serialized')
    char = fields.Char(sparse='template_serialized')
    # template_serialized_char = fields.Serialized(sparse='template_serialized')
    # char_inside = fields.Char(sparse='template_serialized_char', help="Char inside")
    selection = fields.Selection([('one', 'One'), ('two', 'Two')], sparse='template_serialized')
    partner = fields.Many2one('res.partner', sparse='template_serialized')

    preview = fields.Html(readonly=True)
    preview_text = fields.Text(readonly=True, help="This is the extracted text from the file")
    test_results = fields.Text(readonly=True)
    test_warnings = fields.Text(readonly=True)

    partner_fields_name = fields.Selection(
        [
			("vat", "VAT Number"),
			("partner_name", "Name"),
			("partner_street", "Street"),
			("partner_street2", "Street 2"),
			("partner_street3", "Street 3"),
			("partner_city", "City"),
			("partner_zip", "Zip"),
			("country_code", "country"),
			("state_code", "State"),
			("partner_email", "E-mail"),
			("partner_website", "Website"),
			("telephone", "Telephone"),
			("mobile", "Mobile"),
			("partner_ref", "Partner Reference"),
			("siren", "Siren"),
			("partner_coc", "VAT Number"),
        ],
        required=True,
        string="Field",
    )
    start = fields.Char(string="Start String")
    end = fields.Char(string="End String")
    extract_rule = fields.Selection(
        [
            ("first", "First"),
            ("last", "Last"),
            ("position_start", "Specific Position from Start"),
            ("position_end", "Specific Position from End"),
            ("min", "Min"),
            ("max", "Max"),
            ("position_min", "Specific Position from Min"),
            ("position_max", "Specific Position from Max"),
        ],
        string="Extract Rule",
        required=True,
    )
    position = fields.Integer(default=2)

    field_name = fields.Selection(
        [
            ("amount_total", "Total"),
            ("amount_untaxed", "Untaxed Amount"),
            ("amount_tax", "Tax Amount"),
            ("date", "Invoice Date"),
            ("date_due", "Due Date"),
            ("date_start", "Start Date"),
            ("date_end", "End Date"),
            ("invoice_number", "Invoice Number"),
            ("description", "Description"),

        ],
        required=True,
        string="Field",
    )
    regexp = fields.Char(string="Specific Regular Expression")
    """
    date_format = fields.Selection(
        "_date_format_sel",
        string="Specific Date Format",
        help="Leave empty if the format used is the same as the format defined "
        "in the global section.",
    )
    """
    # message_main_attachment_id = fields.Many2one(string="Main Attachment", comodel_name='ir.attachment', index=True, copy=False)
    # message_main_attachment_ids = fields.Many2many('ir.attachment', 'class_ir_attachments_rel', 'class_id', 'attachment_id', 'Attachments')

    def action_preview(self):
        """
        Preview the pdf template as text
        """
        self.ensure_one()
        if not self.message_main_attachment_id.datas:
            self.preview = '<div class="oe_error">%s</div>' % _(
                "No PDF file to preview template!"
            )
            return
        else:
            fd, file_name = mkstemp()
            try:
                os.write(fd, base64.b64decode(self.message_main_attachment_id.datas)) # self.message_main_attachment_id
                # btter to call odoo's file_write https://gitlab.merchise.org/merchise/odoo/blob/a26496b6e79153212973c55f20431df82c3d827b/odoo/addons/base/models/ir_attachment.py#L118
            finally:
                os.close(fd)

            self.preview_text = "<pre>%s</pre>" % to_text(file_name)

        if hasattr(self, "_preview_%s" % self.template_type):
            preview = getattr(self, "_preview_%s" % self.template_type)()
            if preview:
                self.preview = preview
            else:
                self.preview = '<div class="oe_error">%s</div>' % _(
                    "Something seems to be wrong with your template!"
                )
        else:
            self.preview = '<div class="oe_error">%s</div>' % _(
                "Previews not available for this kind of template!"
            )
    # @api.multi
    def action_test(self):
        """
        Run an import simulation to validate the params for this template
        """
        test_warnings = ""
        logging.warning("run import with attachment ids *%s*" % self.message_main_attachment_id)
        # for attachment in self.attachment_ids:
        #    decoded_data = base64.b64decode(attachment)
        #    logging.info("Get attachment url *%s*" % attachment.local_url)
        logging.info("Get attachment url *%s*" % self.message_main_attachment_id.local_url)
        self.ensure_one()
        if not self.message_main_attachment_id.datas:
            self.preview = '<div class="oe_error">%s</div>' % _(
                "No PDF file to preview template!"
            )
            return
        else:
            fd, file_name = mkstemp()
            try:
                os.write(fd, base64.b64decode(self.message_main_attachment_id.datas))
            finally:
                os.close(fd)

            templates = []


            templates = (read_templates(
                pkg_resources.resource_filename("invoice2data", "templates")
            ))

            # added for debug
            logging.info("read templates *%s*" % templates)

            logging.info("Get template *%s*" % self.get_template())
            # templates.append(self.get_template())
            templates += self.get_template()
            # FIXME. Error if exclude_keywords is not present
            test_results = ""
            invoice2data_res = False

            try:
                logging.info("calling extract with templates \n*%s*" % templates)
                logging.info("calling extract with filename \n*%s*" % file_name)
                invoice2data_res = extract_data(file_name, templates=templates)

            except Exception as e:
                test_warnings += (
                    _("PDF Invoice parsing failed. Error message: \n%s\n") % e
                )

            if not invoice2data_res:
                test_results += _(
                    "This PDF invoice doesn't match a known template of "
                    "the invoice2data lib.\n"
                    "invoice2data did not return a result"
                )
            else:
                """
                if invoice2data_res.get("date"):
                    invoice2data_res["date"] = invoice2data_res["date"].strftime(
                        "%Y-%m-%d"
                    )

                if invoice2data_res.get("date") and isinstance(invoice2data_res["date"], datetime.datetime):
                    invoice2data_res["date"] = fields.Date.to_string(invoice2data_res["date"])
                """
                result = json.dumps(invoice2data_res, indent=4, sort_keys=True, default=str)
                # test_results += "Result of invoice2data PDF extraction: \n"
                test_results += result

                # todo, this can be handled by the lib
                needed_keys = [
                    "amount",
                    "amount_untaxed",
                    "currency",
                    "date",
                    "desc",
                    "invoice_number",
                    "partner_name",
                ]

                for key in needed_keys:
                    if not invoice2data_res.get(key):
                        # test_results += _("\n %s is missing" % key)
                        test_warnings  += _("\n %s is missing" % key)

            self.test_warnings = test_warnings

            self.test_results = test_results

    @api.model
    def _dict2html(self, preview_dict):
        """
        Pretty print a dictionary for HTML output
        """
        return "<pre>%s</pre>" % html.escape(pprint.pformat(preview_dict))

    @api.model
    def get_templates(self, template_type):
        """
        Get the templates for a specific template type
        """
        return self.search(
            [
                ("template_type", "=", template_type),
            ]
        ).get_template()

    def get_template(self):
        """
        Return the template as an array to use by the import
        This needs refactoring ordered_load is no longer available
        """
        result = []
        # tmplate = []
        for this in self:
            try:
                tmplate = json.loads(this.template)
                tmplate["template_name"] = this.name
                # Convert keywords to list, if only one
                if not isinstance(tmplate["keywords"], list):
                    tmplate["keywords"] = [tmplate["keywords"]]

                # Set excluded_keywords as empty list, if not provided
                if "exclude_keywords" not in tmplate.keys():
                    tmplate["exclude_keywords"] = []

                # Convert excluded_keywords to list, if only one
                if not isinstance(tmplate["exclude_keywords"], list):
                    tmplate["exclude_keywords"] = [tmplate["exclude_keywords"]]

                if "priority" not in tmplate.keys():
                    tmplate["priority"] = 5

                # template.append(ordered_load(this.template))
            except Exception as e: # TypeError
                logging.warning("Failed to load template: %s ", e)
                self.test_warnings += (
                    _("Failed to load template: %s\n Error message: %s", e, this.name)
                )

                continue

            logging.info("Get template result *%s*" % InvoiceTemplate(tmplate))
            result.append(InvoiceTemplate(tmplate))
        return result
