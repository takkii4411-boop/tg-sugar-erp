from odoo import models, fields

class StockMove(models.Model):
    _inherit = 'stock.move'

    price_unit = fields.Float(
        string="Unit Price",
        related='sale_line_id.price_unit',
        store=True,
        readonly=True,
    )

    sale_qty = fields.Float(
        string="Sale Qty",
        related='sale_line_id.product_uom_qty',
        store=True,
        readonly=True,
    )
