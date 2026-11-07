# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>:wink:
# See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import models, api, fields, _

class TallyConfiguration(models.Model):
    _name = 'tally.configuration'
    _description = "Tally Configurations"

    name = fields.Char(string="Configuration Name", required=True)
    tally_journal_ledger = fields.Char(string="Default Tally Journal Ledger", help="If the tally legder is not set in journal then this has been used by default journal ledger.")
    tally_category_ledger = fields.Char(string="Default Tally Product Ledger", help="If the tally legder is not set in Product or Category then this has been used by default ledger.")
    tally_tax_ledger = fields.Char(string="Default Tally Tax Ledger", help="If the tally ledger is not set in journal then this has been used by default tax ledger.")
    ledger_by = fields.Selection(selection=[('category','Goup By Category'),('product','Group By Product')], string="Tally Ledger Group By", help="If the tally ledger is not set in journal then this has been used by default tax ledger.", default="category")
    bill_allocation  = fields.Boolean(string="Want to Use Bill Alloaction in XML")
    active = fields.Boolean(default=True, help="Set active to false to hide the configuration without removing it.")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    field_mapping_id = fields.Many2one('tally.field.mapping', string="Tags Mapping")
    gstovrdnnature_local = fields.Char(string="Local", help="Local GSTOVRDNNATURE.", default="Sales Taxable", required="1")
    gstovrdnnature_interstate = fields.Char(string="Interstate", help="Interstate GSTOVRDNNATURE.", default="Interstate Sales Taxable", required="1")
    gstovrdnnature_overseas = fields.Char(string="Overseas", help="Overseas GSTOVRDNNATURE.", default="Exports LUT/Bond", required="1")