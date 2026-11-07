# -*- coding: utf-8 -*-
################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
################################################################################
import logging
from odoo import models,fields,api
_logger = logging.getLogger(__name__)

class TallyTag(models.Model):
    _name = 'tally.tag'
    _description = "Tally Tags"

    name = fields.Char(string="Tag",required=True)

class TallyFieldMapping(models.Model):
    _name = 'tally.field.mapping'
    _description = "Tally Mapping"

    name = fields.Char(string="Name",required=True)
    active = fields.Boolean(string="Active",default=True)
    tally_mapping_line_ids = fields.One2many('tally.mapping.line',inverse_name='mapping_field_id',string="Fileds To Mapped")

class TallyMappingLine(models.Model):
    _name = 'tally.mapping.line'
    _description = "Tally Mapping Line"

    mapping_field_id = fields.Many2one('tally.field.mapping', string="Mapping",help="Select the Tally tags that you want to map with Odoo field")
    tally_field_id = fields.Many2one('tally.tag', string="Tally Tag",help="Select the Tally tags that you want to map with Odoo field")
    model_field_id = fields.Many2one('ir.model.fields',domain="[('model', '=', 'account.move')]")
    fixed_text = fields.Char(string="Text",help="Fixed data that you want to send")
    default = fields.Char(string="Default",help="The data enter here will be send when there is no data in the field")
    fixed = fields.Boolean(string="Fixed",default=False,help="Select wether you want to send the fixed data or the field data")
