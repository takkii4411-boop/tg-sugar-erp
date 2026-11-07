from odoo import models, fields, api
from odoo.exceptions import UserError

class PreCloseWizard(models.TransientModel):
    _name = 'pre.close.wizard'
    _description = 'Pre Close Qty Wizard'

    purchase_line_id = fields.Many2one('purchase.order.line')
    balance_qty = fields.Float(string="Balance Qty", readonly=True)
    pre_close_qty = fields.Float(string="Pre Close Qty", required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.purchase_line_id:
            raise UserError("No line found")
        if self.pre_close_qty <= 0:
            raise UserError("Pre Close Qty must be greater than 0")
        if self.balance_qty <= 0:
            raise UserError("Balance Qty must be greater than 0")
        if self.pre_close_qty > self.balance_qty:
            raise UserError("Pre close qty cannot exceed balance qty")

        line = self.purchase_line_id
        line.pre_close_qty += self.pre_close_qty
        line.balance_qty = line.balance_qty - line.pre_close_qty

        line.order_id.message_post(
            body=f"""
            Tender Pre Close Qty - Done ,  
            Product: {line.product_id.name} , 
            Qty: {self.pre_close_qty} , 
            Reason: {self.reason} . 
            """
        )