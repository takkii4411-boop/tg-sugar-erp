from odoo import models, fields, api
from odoo.exceptions import ValidationError

class OverdueCharge(models.Model):
    _name = 'overdue.charge'
    _description = 'Invoice Overdue Charge'
    # _order = 'from_day'

    name = fields.Char(string="Name")
    # from_day = fields.Integer(string="From Day")
    # to_day = fields.Integer(string="To Day")
    day = fields.Integer(string="Credit Days")
    charge_per_quintal = fields.Float(string="Delay Charge Per Quintal")
    # partner_id = fields.Many2one(
    #     'res.partner',
    #     string="Party"
    # )

    line_ids = fields.One2many(
        'overdue.charge.line',
        'charge_id',
        string="Delay Lines"
    )

    @api.constrains('day')
    def _check_day(self):
        for rec in self:
            if rec.day < 0:
                raise ValidationError("Day cannot be negative")

    @api.constrains('day')
    def _check_duplicate_day(self):
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id),
                ('day', '=', rec.day)
            ]):
                raise ValidationError("Charge already exists for this day.")

            # if rec.partner_id:
            #     domain.append(('partner_id', '=', rec.partner_id.id))
            # else:
            #     domain.append(('partner_id', '=', False))

            # if self.search_count(domain):
            #     raise ValidationError(
            #         "Overdue charge already exists for this customer and day range."
            #     )

    # @api.constrains('from_day', 'to_day')
    # def _check_day_range(self):
    #     for rec in self:
    #         if rec.from_day <= 0 or rec.to_day <= 0:
    #             raise ValidationError("Day must be greater than 0")

    #         if rec.from_day > rec.to_day:
    #             raise ValidationError("From Day cannot be greater than To Day")

    # @api.constrains('from_day', 'to_day', 'partner_id')
    # def _check_overlapping_ranges(self):
    #     for rec in self:
    #         domain = [
    #             ('id', '!=', rec.id),
    #             ('from_day', '<=', rec.to_day),
    #             ('to_day', '>=', rec.from_day),
    #         ]

    #         if rec.partner_id:
    #             domain.append(('partner_id', '=', rec.partner_id.id))
    #         else:
    #             domain.append(('partner_id', '=', False))

    #         if self.search_count(domain):
    #             raise ValidationError(
    #                 "Overdue charge already exists for this customer and day range."
    #             )


class OverdueChargeLine(models.Model):
    _name = 'overdue.charge.line'
    _description = 'Daywise Credit Charge Line'

    charge_id = fields.Many2one('overdue.charge')

    # delay_day = fields.Integer(string="Delay Day")
    delay_charge = fields.Float(string="Delay Charge Per Quintal")
    delay_day = fields.Selection([(str(i), str(i)) for i in range(0, 100)], string="Delay Days")

    charge_1 = fields.Float(string="Charge 1", compute="_compute_all_charges")
    charge_2 = fields.Float(string="Charge 2", compute="_compute_all_charges")
    charge_3 = fields.Float(string="Charge 3", compute="_compute_all_charges")

    @api.depends('delay_day')
    def _compute_all_charges(self):
        all_charges = self.env['overdue.charge'].search([], order="id")

        for rec in self:
            rec.charge_1 = 0
            rec.charge_2 = 0
            rec.charge_3 = 0

            day = rec.delay_day  
            if len(all_charges) > 0:
                line1 = all_charges[0].line_ids.filtered(
                    lambda l: l.delay_day == day
                )
                rec.charge_1 = line1[:1].delay_charge if line1 else 0

            if len(all_charges) > 1:
                line2 = all_charges[1].line_ids.filtered(
                    lambda l: l.delay_day == day
                )
                rec.charge_2 = line2[:1].delay_charge if line2 else 0

            
            if len(all_charges) > 2:
                line3 = all_charges[2].line_ids.filtered(
                    lambda l: l.delay_day == day
                )
                rec.charge_3 = line3[:1].delay_charge if line3 else 0
    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.delay_day}-{rec.delay_charge}"
            result.append((rec.id, name))
        return result