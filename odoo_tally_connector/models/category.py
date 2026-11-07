# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>:wink:
# See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import fields, models, api, _

class ProductTemplate(models.Model):

    _inherit = "product.template"

    @api.model
    def get_default_ledger_by(self):
        return self.env['ir.config_parameter'].sudo().get_param('odoo_tally_connector.ledger_by') or 'category'

    @api.onchange('categ_id')
    def _onchange_categ_id(self):
        if self.categ_id and self.categ_id.export_tally_ledger:
            self.export_tally_ledger = self.categ_id.export_tally_ledger
        if self.categ_id and self.categ_id.local_tally_ledger:
            self.export_tally_ledger = self.categ_id.local_tally_ledger

    export_tally_ledger = fields.Char(string="Export Tally Ledger")
    local_tally_ledger = fields.Char(string="Local Tally Ledger")
    ledger_by = fields.Char(selection=[('category','Category'),('product','Product')], string="Tally Ledger By", help="If the tally ledger is not set in journal then this has been used by default tax ledger.", default=get_default_ledger_by)

class ProductCategory(models.Model):

    _inherit = "product.category"

    export_tally_ledger = fields.Char(string="Export Tally Ledger")
    local_tally_ledger = fields.Char(string="Local Tally Ledger")

class AccountJournal(models.Model):

    _inherit = "account.journal"

    tally_ledger_local = fields.Char(string="Local Tally Ledger")
    tally_ledger_export = fields.Char(string="Export Tally Ledger")

class AccountTax(models.Model):

    _inherit = "account.tax"

    tally_ledger_name = fields.Char(string="Tally Ledgername")
