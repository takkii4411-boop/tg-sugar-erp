from odoo import models, fields

class TransportMaster(models.Model):
    _name = 'transport.master'
    _description = 'Transport Master'

    name = fields.Char(string="Transport Name", required=True)
