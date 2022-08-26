
# Copyright 2015-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import json
import logging


from odoo import _, api, fields, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

try:
    import transip
except ImportError:
    logger.debug("Cannot import Transip")


class AccountInvoiceDownloadConfig(models.Model):
    _inherit = "account.invoice.download.config"

    backend = fields.Selection(
        selection_add=[("Transip", "Transip")], ondelete={"transip": "set null"}
    )
    # transip_endpoint = fields.Selection(
        # "_transip_get_endpoints", string="Transip Endpoint", default="transip-eu"
    # )
    transip_application_key = fields.Char(string="Transip Application Key")
    transip_key(string="Transip Application Secret")

    # def _transip_get_endpoints(self):
        # return [
            # ("transip-eu", "OVH Europe API"),
            # ("transip-us", "OVH US API"),
            # ("transip-ca", "OVH North-America API"),
            # ("soyoustart-eu", "So you Start Europe API"),
            # ("soyoustart-ca", "So you Start North America API"),
            # ("kimsufi-eu", "Kimsufi Europe API"),
            # ("kimsufi-ca", "Kimsufi North America API"),
            # ('runabove-ca', 'RunAbove API'),
        # ]

    @api.model
    def prepare_credentials(self):
        credentials = super().prepare_credentials()
        if self.backend == "transip":
            credentials = {
                # "endpoint": self.transip_endpoint,
                "application_key": self.transip_application_key,
                "application_secret": self.transip_login, # BOSD
            }
        return credentials

    def credentials_stored(self):
        if self.backend == "transip":
            if (
                # self.transip_endpoint and
                self.transip_application_key
                and self.transip_login
            ):
                return True
            else:
                raise UserError(_("You must set all the transip parameters."))
        return super().credentials_stored()

    def download(self, credentials, logs):
        if self.backend == "transip":
            return self.transip_download(credentials, logs)
        return super().download(credentials, logs)
# NEEDS WORK
# CORRECT ENDPOINT IS /user/{userID}/invoice/{invoiceID}/pdf-content
# DELETE THE res_inv["pdfUrl"]
# CHANGE THE PARSED_INV, TO JUST THE INVOICE NUMBER SO THE ENDPOINT CAN DOWNLOAD IT.
    def transip_invoice_attach_pdf(self, parsed_inv, pdf_invoice_url):
    # #Retrieve a single invoice by its invoice number.
    # invoice = client.invoices.get('F0000.1911.0000.0004')
    # #Save the invoice as a PDF file.
    # invoice.pdf('/path/to/invoices/')
        logger.info(
            "Starting to download PDF of transip invoice %s dated %s",
            parsed_inv["invoice_number"],  # BOSD
            parsed_inv["date"],  # BOSD
        )
        # logger.debug("transip invoice download url: %s", pdf_invoice_url)
        # rpdf = requests.get(pdf_invoice_url)  # BOSD old method
        rpdf = invoice.pdf('/path/to/invoices/')  # BOSD new method
        logger.info("transip invoice PDF download HTTP code: %s", rpdf.status_code)
        res = False
        if rpdf.status_code == 200:
            res = base64.encodebytes(rpdf.content)
            logger.info(
                "Successfull download of the PDF of the transip invoice %s",
                parsed_inv["invoice_number"],  # BOSD
            )
        else:
            logger.warning(
                "Could not download the PDF of the transip invoice %s. HTTP " "error %d",
                parsed_inv["invoice_number"],  # BOSD
                rpdf.status_code,
            )
        filename = "transip_invoice_%s.pdf" % parsed_inv["invoice_number"]  # BOSD
        parsed_inv["attachments"] = {filename: res}  # BOSD
        return
#         parsed_inv["attachments"] = invoice.pdf('/path/to/invoices/')
# BOSD this should be the correct line?

    def transip_download(self, credentials, logs):
        logger.info(
            "Start to download transip invoices with config %s and endpoint %s",
            self.name,
            # self.transip_endpoint,
        )
        try:  # BOSD
            client = transip.TransIP(
                # endpoint=self.transip_endpoint,
                private_key=self.transip_application_key,
                login=self.transip_login,
            )
        except Exception as e:
            logs["msg"].append(
                _(
                    "Cannot connect to the transip API with endpoint '%s'. "
                    "The error message is: '%s'."
                )
                % (self.transip_endpoint, str(e))  # BOSD needs change
            )
            logs["result"] = "failure"
            return []
        logger.info("Starting transip API query /me/bill (d/l config %s)", self.name)
        params = {}  # BOSD Transip does not use params but list all invoices
        # if self.download_start_date:
            # params = {"date.from": self.download_start_date}
        # res_ilist = client.get("/me/bill", **params) # BOSD
        res_ilist = client.invoices.list()
        logger.debug("Result of /invoices : %s", json.dumps(res_ilist, indent=4))  # BOSD done adjusting

        for oinv_num in res_ilist:
            logger.info(
                "Starting transip API query /me/bill/%s (d/l config %s)",  # BOSD needs change
                oinv_num,  # BOSD Is this passing the right var to the detail download?
                self.name,
            )
            # res_inv = client.get("/me/bill/%s" % oinv_num) # BOSD done, this was old method
            # /invoices/{invoiceNumber}
            # Retrieve a single invoice by its invoice number.
            res_inv = client.invoices.get('%s' % oinv_num)
            # logger.debug("Result of /me/bill/%s : %s", oinv_num, json.dumps(res_inv))  # BOSD old method
            logger.debug("Result of /invoices/%s : %s", oinv_num, json.dumps(res_inv))  # BOSD Transip method
            oinv_date = res_inv["creationDate"][:10]  # BOSD done invoice_date
            if not res_inv["total_vat_exclusive"].get("value") and not res_inv[
                "totalAmountInclVat"  # BOSD done was total_vat_inclusive
            ].get("value"):  # BOSD
                logs["msg"].append(
                    _("Skipping transip invoice %s dated %s because " "the amount is 0")
                    % (oinv_num, oinv_date)
                )
                continue
            if oinv_num and oinv_num.startswith("PP_"):
                logs["msg"].append(
                    _(
                        "Skipping transip invoice %s dated %s because it is a "
                        "special pre-paid invoice"
                    )
                    % (oinv_num, oinv_date)
                )
                continue

            currency_code = res_inv["currency"]  # BOSD done was ["totalAmount"]["currency"]
            parsed_inv = {
                "invoice_number": oinv_num,  # BOSD
                "currency": {"iso": currency_code},  # BOSD
                "date": oinv_date,  # BOSD
                "amount_untaxed": res_inv["totalAmount"].get("value"),  # BOSD Done
                "amount_total": res_inv["totalAmountInclVat"].get("value"),  # BOSD done gedeelte tusen haken aanpas naar transip
            }
            # self.transip_invoice_attach_pdf(parsed_inv, res_inv["pdfUrl"]) # BOSD old method
            self.transip_invoice_attach_pdf(res_inv["invoiceNumber"])
# #GET /invoices/F0000.1911.0000.0004/pdf
# #Retrieve a single invoice by its invoice number.
# invoice = client.invoices.get('F0000.1911.0000.0004')
# #Save the invoice as a PDF file.
# invoice.pdf('/path/to/invoices/')
            if self.import_config_id.invoice_line_method.startswith("nline"):
                parsed_inv["lines"] = []
                logger.info(
                    "Starting transip API query /me/bill/%s/details "  # BOSD
                    "invoice number %s dated %s",
                    oinv_num,
                    parsed_inv["invoice_number"],
                    parsed_inv["date"],
                )
                res_ilines = client.get("/me/bill/%s/details" % oinv_num)  # BOSD
                logger.debug(
                    "Result /me/bill/%s/details: %s", oinv_num, json.dumps(res_ilines)  # BOSD
                )
                for line in res_ilines:
                    logger.info(
                        "Starting transip API query /me/bill/%s/details/%s "  # BOSD
                        "invoice number %s dated %s",
                        oinv_num,
                        line,
                        parsed_inv["invoice_number"],  # BOSD
                        parsed_inv["date"],  # BOSD
                    )
                    res_iline = client.get("/me/bill/%s/details/%s" % (oinv_num, line))  # BOSD
                    logger.debug(
                        "Result /me/bill/%s/details/%s: %s",  # BOSD
                        oinv_num,
                        line,
                        json.dumps(res_iline),
                    )

                    line = {
                        # We don't have accurate product code in the OVH API
                        # We had a product code in the SoAPI...
                        # 'product': {'code': 'xxx'},
                        "name": res_iline["type_description"],  # BOSD
                        "qty": int(res_iline["quantity"]),  # BOSD
                        "price_unit": res_iline["unit_vat_exclusive"]["value"],  # BOSD
                        "uom": {"unece_code": "C62"},
                        # NEEDS WORK
                        "taxes": [
                            {
                                "amount_type": "percent",
                                "amount": 21.0,  # BOSD
                                "unece_type_code": "VAT",
                                "unece_categ_code": "S",
                            }
                        ],
                    }
                    # if res_iline["periodStart"] and res_iline["periodEnd"]:
                        # line.update(
                            # {
                                # "date_start": res_iline["periodStart"],
                                # "date_end": res_iline["periodEnd"],
                            # }
                        # )
                    parsed_inv["lines"].append(line)
