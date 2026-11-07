from odoo import models, fields,api

class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    include_credit_charge = fields.Boolean(
        string="Include Credit Charge in Unit Price"
    )

    credit_days = fields.Integer(
        string="Credit Days",
        help="Number of credit days for delay charge calculation"
    )