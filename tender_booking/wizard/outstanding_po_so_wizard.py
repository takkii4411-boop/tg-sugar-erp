from odoo import models, fields, api
from odoo.exceptions import ValidationError , UserError
from datetime import datetime, time,timedelta
import base64
import io
import xlsxwriter 

class OutstandingPoSoWizard(models.TransientModel):
    _name = 'outstanding.po.so.wizard'
    _description = 'Outstanding PO SO Wizard'

    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")

    line_ids = fields.One2many(
        'outstanding.po.so.line',
        'wizard_id'
    )
    select_all = fields.Boolean(string="Select All")
    show_date = fields.Boolean(compute="_compute_show_date")

    @api.depends('date_from', 'date_to')
    def _compute_show_date(self):
        for rec in self:
            rec.show_date = rec.date_from != rec.date_to

    @api.onchange('select_all')
    def _onchange_select_all(self):
        for line in self.line_ids:
            line.is_selected = self.select_all

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError("To Date cannot be earlier than From Date.")

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):

        if not self.date_from or not self.date_to:
            self.line_ids = [(5, 0, 0)]
            return
        self.line_ids = [(5, 0, 0)]

        domain = [('state', 'in', ['purchase', 'done'])]

        if self.date_from:
            domain.append((
                'date_order',
                '>=',
                self.date_from.strftime('%Y-%m-%d 00:00:00')
            ))

        if self.date_to:
            domain.append((
                'date_order',
                '<=',
                self.date_to.strftime('%Y-%m-%d 23:59:59')
            ))
        orders = self.env['purchase.order'].search(domain)

        lines = []

        for o in orders:
            for line in o.order_line:

                ordered_qty = line.product_qty
                received_qty = line.qty_received
                billed_qty = line.qty_invoiced

                if ordered_qty == received_qty == billed_qty:
                    continue

                rate = line.price_unit

                broker_lines = self.env['broker.allotment.line'].search([
                    ('broker_allotment_id.tender_id', '=', o.id),
                    ('product_id', '=', line.product_id.id)
                ])

                b_so_pending = sum(broker_lines.mapped('balance_qty'))

                party_orders = self.env['sale.order'].search([
                    ('tender_id', '=', o.id),
                    ('state', 'in', ['sale', 'done'])
                ])

                p_so_pending = sum(party_orders.mapped('balance_qty'))

                party_orders = self.env['sale.order'].search([
                    ('tender_id', '=', o.id),
                    ('state', 'in', ['sale', 'done'])
                ])

                sale_lines = party_orders.mapped('order_line').filtered(
                    lambda l: l.product_id.id == line.product_id.id
                )

                do_pending = sum([
                    max((sl.qty_delivered - sl.qty_invoiced), 0)
                    for sl in sale_lines
                ])

                tender_bal = max((ordered_qty - received_qty), 0)

                total_balance = (
                    (b_so_pending or 0) +
                    (p_so_pending or 0) +
                    (do_pending or 0) +
                    (tender_bal or 0)
                )

                partner = o.partner_id

                aml_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', partner.id),
                    ('account_id.account_type', '=', 'liability_payable'),
                    ('move_id.state', '=', 'posted'),
                ])

                total = sum(aml_lines.mapped('balance'))
                vendor_due = -total

                b_so_amt = b_so_pending * rate / 100000
                do_amt = do_pending * rate / 100000
                p_so_amt = p_so_pending * rate / 100000

                balance_for_payment = b_so_amt + do_amt + p_so_amt
                total_pay = balance_for_payment + b_so_amt + do_amt + p_so_amt

                lines.append((0, 0, {
                    'date': o.booking_date.date() if o.booking_date else False,
                    'order_no': o.name,
                    'vendor': f"{o.partner_id.name}, {o.partner_id.city or ''}",
                    'item_name': line.product_id.name,
                    'ordered_qty': ordered_qty,
                    'total_balance': total_balance,
                    'rate': rate,
                    'b_so_pending': b_so_pending,
                    'p_so_pending': p_so_pending,
                    'do_pending': do_pending,
                    'tender_bal': tender_bal,
                    'balance_payment': balance_for_payment,
                    'b_so_amt': b_so_amt,
                    'do_amt': do_amt,
                    'p_so_amt': p_so_amt,
                    'total_pay': total_pay,
                    'vendor_ac_bal': vendor_due,
                    'pay_date': o.pay_date or False,
                    'lift_date': o.lift_date or False,
                }))

        self.line_ids = lines

    def action_print_report(self):
        self.ensure_one()

        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)

        if not selected_lines:
            raise ValidationError("Please select at least one record")

        return self.env.ref(
            'tender_booking.action_report_outstanding_po_so'
        ).with_context(
            date_from=self.date_from,
            date_to=self.date_to
        ).report_action(selected_lines)
        

    def action_excel(self):
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)

        if not selected_lines:
            raise UserError("Please select at least one record")


        show_date = self.date_from != self.date_to

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Outstanding PO SO')

        title_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 16})
        subtitle_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 13})
        date_format = workbook.add_format({'align': 'center', 'font_size': 11})

        header_format = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        text_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0'})
        total_format = workbook.add_format({'bold': True, 'border': 1})
        total_format_only = workbook.add_format({'bold': True, 'align': 'center', 'border': 1})

        green_format = workbook.add_format({
            'bg_color': "#90EEC2",
            'border': 1,
            'align': 'center'
        })

        green_number_format = workbook.add_format({
            'bg_color': '#90EEC2',
            'border': 1,
            'num_format': '#,##0'
        })

        date_str = ''
        if self.date_from and self.date_to:
            date_str = f"{self.date_from.strftime('%d-%b-%y')} - {self.date_to.strftime('%d-%b-%y')}"

        last_col = 18 if show_date else 17

        sheet.merge_range(0, 0, 0, last_col, 'TG Sugars LTD', title_format)
        sheet.merge_range(1, 0, 1, last_col, 'Purchase Orders With SO', subtitle_format)
        sheet.merge_range(2, 0, 2, last_col, date_str, date_format)

        col = 0

        if show_date:
            sheet.write(3, col, 'Date', header_format)
            col += 1

        headers = [
            'Order', 'Vendor', 'Item',
            'Ordered', 'Total Balance', 'Rate',
            'B SO Pending Bal', 'P SO Pending Bal', 'DO Pending Bal', 'Tender Bal',
            'Balance Payment',
            'B SO Amt', 'DO Amt', 'P SO Amt',
            'Total Pay',
            'Vendor A/c Bal', 'Pay Date', 'Lift Date'
        ]

        for h in headers:
            if h in ['Total Balance', 'Total Pay']:
                sheet.write(3, col, h, green_format)
            else:
                sheet.write(3, col, h, header_format)
            col += 1

        row = 4

        tot_ordered = tot_balance = tot_pay = 0
        tot_bso = tot_pso = tot_do = tot_tender = 0
        tot_bal_pay = tot_b_amt = tot_do_amt = tot_p_amt = 0

        for line in selected_lines:

            col = 0

            if show_date:
                sheet.write(row, col, str(line.date or ''), text_format)
                col += 1

            sheet.write(row, col, line.order_no or '', text_format); col += 1
            sheet.write(row, col, line.vendor or '', text_format); col += 1
            sheet.write(row, col, line.item_name or '', text_format); col += 1

            sheet.write(row, col, int(line.ordered_qty or 0), number_format); col += 1
            sheet.write(row, col, int(line.total_balance or 0), green_number_format); col += 1
            sheet.write(row, col, line.rate or 0, number_format); col += 1

            sheet.write(row, col, int(line.b_so_pending or 0), number_format); col += 1
            sheet.write(row, col, int(line.p_so_pending or 0), number_format); col += 1
            sheet.write(row, col, int(line.do_pending or 0), number_format); col += 1
            sheet.write(row, col, int(line.tender_bal or 0), number_format); col += 1

            sheet.write(row, col, int(line.balance_payment or 0), number_format); col += 1

            sheet.write(row, col, int(line.b_so_amt or 0), number_format); col += 1
            sheet.write(row, col, int(line.do_amt or 0), number_format); col += 1
            sheet.write(row, col, int(line.p_so_amt or 0), number_format); col += 1

            sheet.write(row, col, int(line.total_pay or 0), green_number_format); col += 1
            sheet.write(row, col, int(line.vendor_ac_bal or 0), number_format); col += 1

            sheet.write(row, col, str(line.pay_date or ''), text_format); col += 1
            sheet.write(row, col, str(line.lift_date or ''), text_format)

            # totals
            tot_ordered += line.ordered_qty or 0
            tot_balance += line.total_balance or 0

            tot_bso += line.b_so_pending or 0
            tot_pso += line.p_so_pending or 0
            tot_do += line.do_pending or 0
            tot_tender += line.tender_bal or 0

            tot_bal_pay += line.balance_payment or 0

            tot_b_amt += line.b_so_amt or 0
            tot_do_amt += line.do_amt or 0
            tot_p_amt += line.p_so_amt or 0

            tot_pay += line.total_pay or 0

            row += 1

        col = 0
        if show_date:
            col = 1

        sheet.merge_range(row, 0, row, col + 2, 'TOTAL', total_format_only)

        col = 0
        if show_date:
            col += 1

        col += 3

        sheet.write(row, col, int(tot_ordered), total_format); col += 1
        sheet.write(row, col, int(tot_balance), green_number_format); col += 1

        col += 1
        sheet.write(row, col, int(tot_bso), total_format); col += 1
        sheet.write(row, col, int(tot_pso), total_format); col += 1
        sheet.write(row, col, int(tot_do), total_format); col += 1
        sheet.write(row, col, int(tot_tender), total_format); col += 1

        sheet.write(row, col, int(tot_bal_pay), total_format); col += 1

        sheet.write(row, col, int(tot_b_amt), total_format); col += 1
        sheet.write(row, col, int(tot_do_amt), total_format); col += 1
        sheet.write(row, col, int(tot_p_amt), total_format); col += 1

        sheet.write(row, col, int(tot_pay), green_number_format)

        sheet.set_column(0, last_col, 15)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Outstanding_PO_SO.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class OutstandingPoSoLine(models.TransientModel):
    _name = 'outstanding.po.so.line'

    is_selected = fields.Boolean(string="Select")
    wizard_id = fields.Many2one('outstanding.po.so.wizard')

    date = fields.Date("Date")
    order_no = fields.Char("Order")
    vendor = fields.Char("Vendor")
    item_name = fields.Char("Item")

    ordered_qty = fields.Float("Ordered")
    total_balance = fields.Float("Total Balance")
    rate = fields.Float("Rate")

    b_so_pending = fields.Float("B SO Pending")
    p_so_pending = fields.Float("P SO Pending Bal")
    do_pending = fields.Float("DO Pending Bal")
    tender_bal = fields.Float("Tender Bal")

    balance_payment = fields.Float("Balance Payment")

    b_so_amt = fields.Float("B SO Amt")
    do_amt = fields.Float("DO Amt")
    p_so_amt = fields.Float("P SO Amt")

    total_pay = fields.Float("Total Pay")

    vendor_ac_bal = fields.Float("Vendor A/c Bal")
    pay_date = fields.Date("Pay Date")
    lift_date = fields.Date("Lift Date")
