# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_broker_partner = fields.Boolean(string="Is Broker")
    is_party_partner = fields.Boolean("Is Party")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._context.get('default_is_broker_partner') and not vals.get('is_broker_partner'):
                vals['is_broker_partner'] = True


            if vals.get('customer_rank', 0) > 0:
                vals['is_party_partner'] = True
                vals['is_broker_partner'] = False

        return super().create(vals_list)
