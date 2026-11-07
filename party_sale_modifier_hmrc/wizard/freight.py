from odoo import models, fields, api
class FreightCharge(models.TransientModel):
    _name = 'freight.charge.line'
    _description = 'Freight Charge Line'

    # order_id = fields.Many2one('sale.order')
    picking_id = fields.Many2one('stock.picking', string="Delivery Order")
    rate_per_quintal = fields.Float(string="Rate Per Quintal")
    total_qty = fields.Float(string="Total Quantity", compute="_compute_total_qty")
    total_amount = fields.Float(string="Total Freight Charges", compute="_total_amount")
    freight_expense_account_id = fields.Many2one('account.account', string="Freight Expense Account", config_parameter='party_sale_modifier_hmrc.freight_expense_account_id')
    freight_payable_account_id = fields.Many2one('account.account', string="Freight Payable Account", config_parameter='party_sale_modifier_hmrc.freight_payable_account_id')
    journal_id = fields.Many2one('account.journal', string="Journal", config_parameter='party_sale_modifier_hmrc.journal_id')

    # @api.depends('order_id.order_line')
    # def _compute_total_qty(self):
    #     for rec in self:
    #         if rec.order_id.order_line:
    #             rec.total_qty = rec.order_id.order_line[0].product_uom_qty
    #         else:
    #             rec.total_qty = 0

    @api.depends('picking_id')
    def _compute_total_qty(self):
        for rec in self:
            if rec.picking_id:
                rec.total_qty = sum(
                    rec.picking_id.move_line_ids.mapped('qty_done')
                )
            else:
                rec.total_qty = 0.0

    # @api.depends('total_qty','rate_per_quintal')
    # def _total_amount(self):
    #     for rec in self:
    #         rec.total_amount = rec.total_qty * rec.rate_per_quintal   

    @api.depends('total_qty', 'rate_per_quintal')
    def _total_amount(self):
        for rec in self:
            rec.total_amount = rec.total_qty * rec.rate_per_quintal

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        param = self.env['ir.config_parameter'].sudo()
        expense_id = param.get_param('party_sale_modifier_hmrc.freight_expense_account_id')
        payable_id = param.get_param('party_sale_modifier_hmrc.freight_payable_account_id')
        journal_id = param.get_param('party_sale_modifier_hmrc.freight_journal_id')
        if expense_id:
            res['freight_expense_account_id'] = int(expense_id)
        if payable_id:
            res['freight_payable_account_id'] = int(payable_id)
        if journal_id:
            res['journal_id'] = int(journal_id)
        return res

    # def action_add_line(self):
    #     self.ensure_one()
    #     self.order_id.freight_rate = self.rate_per_quintal
    #     move = self.env['account.move'].create({
    #         'move_type': 'entry',
    #         'journal_id': self.journal_id.id,
    #         'ref': f"Freight - {self.order_id.name}",
    #         'line_ids': [
    #             (0, 0, {
    #                 'name': 'Freight Charges',
    #                 'account_id': self.freight_expense_account_id.id,
    #                 'debit': self.total_amount,
    #                 'credit': 0.0,
    #             }),
    #             (0, 0, {
    #                 'name': 'Freight Payable',
    #                 'account_id': self.freight_payable_account_id.id,
    #                 'debit': 0.0,
    #                 'credit': self.total_amount,
    #             }),
    #         ]
    #     })
    #     move.action_post()

    def action_add_line(self):
        self.ensure_one()

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'ref': f"Freight - {self.picking_id.name}",
            'picking_id': self.picking_id.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Freight Charges',
                    'account_id': self.freight_expense_account_id.id,
                    'debit': self.total_amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Freight Payable',
                    'account_id': self.freight_payable_account_id.id,
                    'debit': 0.0,
                    'credit': self.total_amount,
                }),
            ]
        })

        move.action_post()
