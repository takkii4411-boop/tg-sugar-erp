from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class ProductPacking(models.Model):
    _name = 'cus.product.package'
    _description = 'Product Packing'

    name = fields.Char(string='Pack Name')
    per_qt_quantity = fields.Float(string='How many quintals in 1 bag?')
    quantity_contain = fields.Integer(string='Bag Size')
    is_default = fields.Boolean(string="Default", default=True)

    @api.model
    def create(self,vals_list):
        for rec in vals_list:
            if rec.get('is_default'):
                existing = self.search([('is_default', '=', True)])
                if existing:
                    raise ValidationError("Only one record can be default set")

        res = super().create(vals_list)
        if res.per_qt_quantity == 0:
            raise UserError('Please add How many quintals in 1 bag?.')
        # if res.quantity_contain == 0:
        #     raise UserError('Please add a bag size.')
        return res

    def write(self,vals):
        if vals.get('is_default', False):
            existing = self.search([('is_default', '=', True), ('id', '!=', self.id)])
            if existing:
                raise ValidationError("Only one record can be default set")

        res = super().write(vals)
        if self.per_qt_quantity == 0:
            raise UserError('Please add How many quintals in 1 bag?.')
        # if self.quantity_contain == 0:
        #     raise UserError('Please add a bag size.')
        return res
