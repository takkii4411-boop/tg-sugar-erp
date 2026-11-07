from odoo import models, fields,api,_
from odoo.exceptions import UserError,ValidationError
from datetime import date
import logging
import calendar
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _create_backorder(self):
        backorders = super()._create_backorder()

        backorders.write({
            'vehicle_number': False,
            'driver_id': False,
            'driver_phone': False,
            'transport_name': False,
        })

        return backorders

    invoice_created = fields.Boolean(default=False)

    tender_no = fields.Many2one(
        'purchase.order',
        string="Tender No",
        related="sale_id.broker_allotment_id.tender_id",
        store=False
    )

    broker_no = fields.Many2one(
        'broker.allotment',
        string="Broker No",
        related="sale_id.broker_allotment_id",
        store=False
    )

    vendor_bill_id = fields.Many2one(
        'account.move',
        string="Vendor Bill",
        compute="_compute_bill_invoice"
    )

    customer_invoice_id = fields.Many2one(
        'account.move',
        string="Customer Invoice",
        compute="_compute_bill_invoice"
    )

    po_rate = fields.Float(
        string="PO Rate",
        compute="_compute_po_rate",
        store=True
    )

    vendor_amount = fields.Float(
        string="Vendor Amount",
        compute="_compute_vendor_amount",
        store=True
    )

    freight_charge_line_ids = fields.One2many(
        'freight.charge.line',
        'picking_id',
        string="Freight Charges"
    )
    freight_count = fields.Integer(compute="_compute_freight")

    freight_total = fields.Float(compute="_compute_freight")

    def _compute_freight(self):
        for rec in self:
            moves = self.env['account.move'].search([
                ('picking_id', 'in', rec.id),
                ('state', '=', 'posted'),
                ('ref', 'ilike', 'Freight')
            ])
            rec.freight_count = len(moves)
            rec.freight_total = sum(moves.mapped('amount_total'))

    def action_view_freight_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Freight Journal Entries',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [
                ('picking_id', '=', self.id),
                ('move_type', '=', 'entry')
            ],
            'context': {'create': False},
        }

    @api.depends('sale_id.tender_id.order_line.price_unit')
    def _compute_po_rate(self):
        for rec in self:
            po_rate = 0
            if rec.sale_id and rec.sale_id.tender_id:
                tender = rec.sale_id.tender_id
                if tender.order_line:
                    po_rate = tender.order_line[0].price_unit
            rec.po_rate = po_rate


    @api.depends('sale_id.tender_id.order_line.price_subtotal')
    def _compute_vendor_amount(self):

        for rec in self:
            amount = 0
            if rec.sale_id and rec.sale_id.tender_id:
                tender = rec.sale_id.tender_id

                if tender.order_line:
                    amount = tender.order_line[0].price_subtotal

            rec.vendor_amount = amount

    voucher_date = fields.Date(string="Voucher Date", default=fields.Datetime.now)

    def action_add_freight(self):
        self.ensure_one()

        existing = self.env['account.move'].search([
            ('ref', '=', f"Freight - {self.name}"),
            ('move_type', '=', 'entry')
        ], limit=1)

        if existing:
            raise UserError("Freight Charge already added for this Delivery Order.")
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'freight.charge.line',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id}
        }

    def _compute_bill_invoice(self):
        for picking in self:
            vendor_bill = self.env['account.move'].search([
                ('move_type','=','in_invoice'),
                ('picking_id','=', picking.id),
                ('state','!=','cancel')
            ], limit=1)

            customer_invoice = self.env['account.move'].search([
                ('move_type','=','out_invoice'),
                ('picking_id','=', picking.id),
                ('state','!=','cancel')
            ], limit=1)

            picking.vendor_bill_id = vendor_bill
            picking.customer_invoice_id = customer_invoice


            total_done = sum(picking.move_line_ids.mapped('qty_done'))

            billed_qty = sum(
                picking.env['account.move.line'].search([
                    ('move_id.move_type','=','in_invoice'),
                    ('move_id.picking_id','=',picking.id),
                    ('move_id.state','!=','cancel')
                ]).mapped('quantity')
            )

            picking.vendor_bill_created = billed_qty >= total_done

            

            # picking.vendor_bill_created = bool(vendor_bill)
            # picking.invoice_created = bool(customer_invoice)
            MoveLine = self.env['account.move.line']

            for picking in self:

                total_done = sum(picking.move_line_ids.mapped('qty_done'))

                billed_qty = sum(
                    MoveLine.search([
                        ('move_id.move_type','=','out_invoice'),
                        ('move_id.picking_id','=',picking.id),
                        ('move_id.state','!=','cancel')
                    ]).mapped('quantity')
                )

                picking.invoice_created = billed_qty >= total_done

    customer_id = fields.Many2one(
        'res.partner',
        string="Customer",
        compute="_compute_customer",
        store=True
    )
    @api.depends('sale_id.partner_id')
    def _compute_customer(self):
        for rec in self:
            rec.customer_id = rec.sale_id.partner_id



    is_immediate_payment = fields.Boolean(
        string="Is Immediate Payment",
        compute="_compute_is_immediate_payment",
        store=False
    )

    @api.depends('sale_id', 'sale_id.payment_term_id')
    def _compute_is_immediate_payment(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.payment_term_id:
                picking.is_immediate_payment = picking.sale_id.payment_term_id.name == 'Immediate Payment'
            else:
                picking.is_immediate_payment = False



    def action_create_customer_invoice(self):
        for picking in self:

            # if picking.sale_id and picking.sale_id.payment_term_id and \
            #     picking.sale_id.payment_term_id.name == 'Immediate Payment':
            #         raise UserError(
            #             "For Immediate Payment terms, invoice must be created from Party Order, not from Delivery Order."
            #         )


            existing_invoice = self.env['account.move'].search([
                ('move_type','=','out_invoice'),
                ('picking_ids','in', picking.id),
                ('state','!=','cancel')
            ],limit=1)

            if existing_invoice:
                raise UserError(
                    f"Invoice already created for Delivery Order {picking.name}"
                )
            if picking.state != 'done':
                raise UserError("Invoice is created only from DONE delivery!")

            if picking.invoice_created:
                raise UserError("Invoice already created")

            invoice_lines = []

            for line in picking.move_line_ids:
                if line.qty_done <= 0:
                    continue
                if not line.move_id.sale_line_id:
                    continue
                sale_line = line.move_id.sale_line_id

                delivered_qty = line.qty_done

                MoveLine = self.env['account.move.line']

                already_billed_qty = sum(
                    MoveLine.search([
                        ('move_id.move_type','=','out_invoice'),
                        ('move_id.picking_id','=', picking.id),
                        ('move_id.state','!=','cancel'),
                        ('product_id','=', line.product_id.id)
                    ]).mapped('quantity')
                )

                remaining_qty = delivered_qty - already_billed_qty

                if remaining_qty <= 0:
                    continue

                invoice_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'quantity': remaining_qty,
                    'price_unit': sale_line.price_unit,
                    'sale_line_ids': [(6, 0, [sale_line.id])] if sale_line else [],
                    'account_id': line.product_id.categ_id.property_account_income_categ_id.id,
                }))

            if not invoice_lines:
                raise UserError("No delivered quantity to invoice")

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': picking.customer_id.id,
                'customer_id': picking.partner_id.id,
                'invoice_origin': picking.sale_id.name,
                'invoice_user_id': picking.sale_id.user_id.id,
                'invoice_line_ids': invoice_lines,
                'picking_id': picking.id,
            })
            invoice.vehicle_number = picking.vehicle_number
            invoice.driver_name = picking.driver_id.name if picking.driver_id else False
            invoice.driver_number = picking.driver_phone
            invoice.transport_name = picking.transport_name.name
            invoice.action_post()
            picking.invoice_created = True
            picking._compute_invoice_status()  
            

    vendor_bill_created = fields.Boolean(string="Vendor Bill Created", default=False)

    def action_create_vendor_bill(self):
        self.ensure_one()
        MoveLine = self.env['account.move.line']

        # if self.vendor_bill_created:
        #     raise UserError(_("Vendor Bill already created!"))

        MoveLine = self.env['account.move.line']

        total_delivered = sum(self.move_line_ids.mapped('qty_done'))

        total_billed = sum(
            MoveLine.search([
                ('move_id.move_type','=','in_invoice'),
                ('move_id.state','=','posted'),   # only posted
                ('move_id.picking_id','=', self.id),
            ]).mapped('quantity')
        )

        if total_billed >= total_delivered:
            raise UserError(_("Full quantity already billed for this Delivery Order!"))
        if not self.partner_id:
            raise UserError(_("Vendor is missing."))

        if not (
            self.sale_id
            and self.sale_id.broker_allotment_id
            and self.sale_id.broker_allotment_id.tender_id
        ):
            raise UserError(_("Tender not found. Vendor Bill cannot be created."))

        tender_po = self.sale_id.broker_allotment_id.tender_id

        invoice_lines = []

        for move in self.move_ids:
            qty_done = sum(move.move_line_ids.mapped('qty_done'))
            if qty_done <= 0:
                continue

            product = move.product_id
            expense_account = product.categ_id.property_account_expense_categ_id

            if not expense_account:
                raise UserError(
                    _("Expense account not set for product category %s")
                    % product.categ_id.display_name
                )

            po_line = tender_po.order_line.filtered(
                lambda l: l.product_id == product
            )

            if not po_line:
                raise UserError(
                    _("Product %s not found in Tender Purchase Order.")
                    % product.display_name
                )
            
            po_line = po_line[0]
            
            delivered_qty = sum(move.move_line_ids.mapped('qty_done'))
            already_billed_qty = sum(
                MoveLine.search([
                    ('move_id.move_type','=','in_invoice'),
                    ('move_id.picking_id','=',self.id),
                    ('move_id.state','!=','cancel'),
                    ('product_id','=',product.id)
                ]).mapped('quantity')
            )

            remaining_qty = delivered_qty - already_billed_qty

            if remaining_qty <= 0:
                continue

            invoice_lines.append((0, 0, {
                'product_id': product.id,
                'name': product.display_name,
                'quantity': remaining_qty,
                'price_unit': po_line[0].price_unit,
                'account_id': expense_account.id,
                'purchase_line_id': po_line[0].id,
            }))

        if not invoice_lines:
            raise UserError(_("No delivered quantity to bill."))

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.sale_id.broker_allotment_id.tender_id.partner_id.id,
            'invoice_origin': self.sale_id.name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': invoice_lines,
            'picking_id': self.id,
            'vehicle_number': self.vehicle_number,
            'driver_name': self.driver_id.name if self.driver_id else False,
            'driver_number': self.driver_phone,
            'transport_name': self.transport_name.name,
            'auto_tds_apply': False,  
        })
        bill.action_post()
        self.vendor_bill_created = True

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
        }

    vehicle_number = fields.Char(string="Vehicle Number")
    driver_phone = fields.Char(string="Driver Phone")
    driver_id = fields.Many2one('res.partner', string="Driver Name")
    transport_id = fields.Many2one('res.partner', string="Transport Name")
    transport_name = fields.Many2one('transport.master', string="Transport")

    def button_validate(self):
        for picking in self:
            if picking.picking_type_code == 'outgoing':
                if not picking.vehicle_number:
                    raise UserError("Vehicle Number is Required!")
                if not picking.transport_name:
                    raise UserError("Transport Name is Required!")
        # return super().button_validate()
    
 
        res = super().button_validate()

        for picking in self:
            if picking.state == 'done' and picking.sale_id:
                picking._send_delivery_whatsapp_message()

        return res

    def _send_delivery_whatsapp_message(self):
        whatsapp_items = []
        for move in self.move_line_ids:
            if move.qty_done > 0:
                whatsapp_items.append(
                    f"{move.product_id.display_name}, Qty {move.qty_done} quintal"
                )

        if not whatsapp_items:
            return

        items_text = " | ".join(whatsapp_items)

        driver_name = self.driver_id.name if self.driver_id else 'N/A'
        driver_phone = self.driver_phone or 'N/A'
        vehicle_no = self.vehicle_number or 'N/A'


        broker_party_message = (
            "The following qty has been delivered:\n"
            f"With items: {items_text}\n\n"
            f"Driver Name   : {driver_name}\n"
            f"Driver Phone  : {driver_phone}\n"
            f"Vehicle No    : {vehicle_no}"
        )

        # broker_name = (
        #     self.sale_id.broker_allotment_id.partner_id.name
        #     if self.sale_id.broker_allotment_id and self.sale_id.broker_allotment_id.partner_id
        #     else 'N/A'
        # )
        # party_name = self.partner_id.name if self.partner_id else 'N/A'

        # company_message = (
        #     f"The following qty has been delivered to "
        #     f"Broker: {broker_name} / Party: {party_name}\n"
        #     f"With items: {items_text}"
        # )

        # company_partner = self.company_id.partner_id
        broker_partner = self.sale_id.broker_allotment_id.partner_id
        party_partner = self.partner_id

        # if company_partner:
        #     contact_number = company_partner.phone
        #     if contact_number:
        #         _logger.warning("DELIVERY WHATSAPP MESSAGE READY (COMPANY)")
        #         _logger.warning("Send To (Company): %s", company_partner.name)
        #         _logger.warning("Contact Number: %s", contact_number)
        #         _logger.warning("Message: %s", company_message)
        #         _logger.warning("--------------------------------------------------")

        if broker_partner:
            contact_number = broker_partner.phone
            if contact_number:
                _logger.warning("WHATSAPP TEMPLATE READY : DELIVERY ORDER")
                _logger.warning("Send To (Broker): %s", broker_partner.name)
                _logger.warning("Contact Number: %s", contact_number)
                _logger.warning("Message: %s", broker_party_message)
                _logger.warning("--------------------------------------------------")

        if party_partner:
            contact_number = party_partner.phone
            if contact_number:
                _logger.warning("WHATSAPP TEMPLATE READY : DELIVERY ORDER")
                _logger.warning("Send To (Party): %s", party_partner.name)
                _logger.warning("Contact Number: %s", contact_number)
                _logger.warning("Message: %s", broker_party_message)
                _logger.warning("--------------------------------------------------")

    invoice_count = fields.Integer(
        string="Customer Invoice",
        compute='_compute_invoice_count'
    )

    def _compute_invoice_count(self):
        Move = self.env['account.move']
        for picking in self:
            if picking.state != 'done':
                picking.invoice_count = 0
                continue

            picking.invoice_count = Move.search_count([
                ('move_type', '=', 'out_invoice'),
                ('state', '!=', 'cancel'),
                '|',
                ('picking_id', '=', picking.id),
                ('picking_ids', 'in', picking.id),
            ])

    def action_create_merged_customer_invoice(self):
        pickings = self

        if any(p.state != 'done' for p in pickings):
            raise UserError("All Delivery Orders must be in Done state.")

        partner = pickings[0].partner_id
        if any(p.partner_id != partner for p in pickings):
            raise UserError("Please select Delivery Orders of same customer.")

        if any(p.invoice_created for p in pickings):
            raise UserError("Invoice already created for this Delivery Order.")
        first_picking = pickings[0]
        for picking in pickings:
            existing_invoice = self.env['account.move'].search([
                ('move_type','=','out_invoice'),
                ('picking_ids','in', picking.id),
                ('state','!=','cancel')
            ],limit=1)

            if existing_invoice:
                raise UserError(
                    f"Invoice already created for Delivery Order {picking.name}"
                )
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': first_picking.customer_id.id,
            'customer_id': first_picking.partner_id.id,
            'invoice_origin': ', '.join(pickings.mapped('name')),
            'picking_ids': [(6,0,pickings.ids)],
            'vehicle_number': first_picking.vehicle_number,
            'driver_name': first_picking.driver_id.name if first_picking.driver_id else False,
            'driver_number': first_picking.driver_phone,
            'transport_name': first_picking.transport_name.name,

        }) 

        line_map = {}

        for picking in pickings:
            for line in picking.move_line_ids:
                if line.qty_done <= 0:
                    continue

                sale_line = line.move_id.sale_line_id
                product = line.product_id
                price = line.move_id.sale_line_id.price_unit if line.move_id.sale_line_id else product.lst_price

                key = (product.id, price)

                if key in line_map:
                    line_map[key]['quantity'] += line.qty_done
                else:
                    line_map[key] = {
                        'product_id': product.id,
                        'name': product.display_name,
                        'quantity': line.qty_done,
                        'price_unit': price,
                        'sale_line_ids': [(6, 0, [sale_line.id])],
                        'account_id': product.categ_id.property_account_income_categ_id.id,
                    }
        invoice.write({
            'invoice_line_ids': [(0, 0, vals) for vals in line_map.values()]
        })

        invoice.action_post()
        pickings.write({
            'invoice_created': True,
            'invoice_status': 'done' 
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def action_create_merged_vendor_bill(self):
        pickings = self

        if any(p.state != 'done' for p in pickings):
            raise UserError("All Delivery Orders must be in Done state.")
        partner = pickings[0].sale_id.broker_allotment_id.tender_id.partner_id
        if any(p.sale_id.broker_allotment_id.tender_id.partner_id != partner for p in pickings):
            raise UserError("Please select Delivery Orders of same Vendor.")
        if any(p.vendor_bill_created for p in pickings):
            raise UserError("Vendor Bill already created.")

        MoveLine = self.env['account.move.line']
        first_picking = pickings[0]

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_origin': ', '.join(pickings.mapped('name')),
            'picking_ids': [(6, 0, pickings.ids)],
            'picking_id': pickings[0].id,
            'invoice_date': fields.Date.context_today(self),
            'vehicle_number': first_picking.vehicle_number,
            'driver_name': first_picking.driver_id.name if first_picking.driver_id else False,
            'driver_number': first_picking.driver_phone,
            'transport_name': first_picking.transport_name.name,
            'auto_tds_apply': False,
        })

        line_map = {}

        for picking in pickings:
            tender_po = picking.sale_id.broker_allotment_id.tender_id

            for move in picking.move_ids:
                product = move.product_id

                delivered_qty = sum(move.move_line_ids.mapped('qty_done'))
                if delivered_qty <= 0:
                    continue

                already_billed_qty = sum(
                    MoveLine.search([
                        ('move_id.move_type','=','in_invoice'),
                        ('move_id.picking_id','=', picking.id),
                        ('move_id.state','!=','cancel'),
                        ('product_id','=', product.id)
                    ]).mapped('quantity')
                )

                remaining_qty = delivered_qty - already_billed_qty

                if remaining_qty <= 0:
                    continue

                po_line = tender_po.order_line.filtered(lambda l: l.product_id == product)
                if not po_line:
                    raise UserError(f"{product.display_name} not found in Tender PO")

                price = po_line[0].price_unit
                key = (product.id, price)
                expense_account = product.categ_id.property_account_expense_categ_id
                if not expense_account:
                    raise UserError(f"Expense account missing for {product.display_name}")

                if key in line_map:
                    line_map[key].quantity += remaining_qty
                else:
                    line_map[key] = self.env['account.move.line'].create({
                        'move_id': bill.id,
                        'product_id': product.id,
                        'quantity': remaining_qty,
                        'price_unit': price,
                        'name': product.display_name,
                        'account_id': expense_account.id,
                        'purchase_line_id': po_line[0].id,
                    })

        if not line_map:
            raise UserError("No quantity to bill.")

        bill.action_post()

        pickings.write({
            'vendor_bill_created': True,
            'vendor_bill_status': 'done'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
        }

    # def action_view_customer_invoices(self):
    #     self.ensure_one()

    #     invoice = self.env['account.move'].search([
    #         ('move_type', '=', 'out_invoice'),
    #         ('state', '!=', 'cancel'),
    #         ('picking_id', '=', self.id),
    #     ], limit=1)

    #     if not invoice:
    #         raise UserError("No customer invoice found for this Delivery Order.")

    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Customer Invoice',
    #         'res_model': 'account.move',
    #         'view_mode': 'form',
    #         'res_id': invoice.id,
    #         'target': 'current',
    #     }

    def action_view_customer_invoices(self):
        self.ensure_one()

        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
            '|',
            ('picking_id', '=', self.id),
            ('picking_ids', 'in', self.id),
        ])

        if not invoices:
            raise UserError("No customer invoice found for this Delivery Order.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
        }
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sale Order",
        related='move_ids.sale_line_id.order_id',
        store=True
    )


    total_qty = fields.Float(
        string="Quantity",
        compute="_compute_qty_rate",
        store=True
    )

    unit_rate = fields.Float(
        string="Rate",
        compute="_compute_qty_rate",
        store=True
    )  

    @api.depends('move_ids.product_uom_qty', 'move_ids.sale_line_id.price_unit')
    def _compute_qty_rate(self):
        for picking in self:
            qty = 0.0
            rate = 0.0
            if picking.move_ids:
                move = picking.move_ids[0]
                qty = move.product_uom_qty
                rate = move.sale_line_id.price_unit if move.sale_line_id else 0.0

            picking.total_qty = qty
            picking.unit_rate = rate

    invoice_status = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string="Invoice Status", compute="_compute_invoice_status", store=True)


    vendor_bill_status = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string="Vendor Bill Status", compute="_compute_vendor_bill_status", store=True)
    
    product_id = fields.Many2one('product.product', string="Product", compute="_compute_product")

    @api.depends('move_ids.product_id')
    def _compute_product(self):
        for rec in self:
            rec.product_id = rec.move_ids[:1].product_id


    # @api.depends('name')
    # def _compute_vendor_bill_status(self):

    #     Move = self.env['account.move']

    #     for rec in self:

    #         bill = Move.search([
    #             ('move_type', '=', 'in_invoice'),
    #             ('picking_id', '=', rec.id),
    #             ('state', '!=', 'cancel')
    #         ], limit=1)

    #         rec.vendor_bill_status = 'done' if bill else 'draft'

    @api.depends('move_ids')
    def _compute_invoice_status(self):
        for rec in self:
            invoice = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '!=', 'cancel'),
                '|',
                ('picking_id', '=', rec.id),
                ('picking_ids', 'in', rec.id)
            ], limit=1)

            rec.invoice_status = 'done' if invoice else 'draft'


    @api.depends('move_ids', 'vendor_bill_created')
    def _compute_vendor_bill_status(self):
        for rec in self:
            bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('state', '!=', 'cancel'),
                '|',
                ('picking_id', '=', rec.id),
                ('picking_ids', 'in', rec.id)
            ], limit=1)
            rec.vendor_bill_status = 'done' if bill else 'draft'

    def action_cancel(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.broker_allotment_id:
                broker = picking.sale_id.broker_allotment_id
                for move in picking.move_ids:
                    so_line = move.sale_line_id
                    if not so_line:
                        continue
                    broker_line = broker.order_line.filtered(lambda l: l.product_id == move.product_id)
                    if broker_line:
                        broker_line.balance_qty += move.product_uom_qty
                        broker_line.party_qty -= move.product_uom_qty
        return super().action_cancel()

    def get_partner_aging(self):
        self.ensure_one()

        partner = self.partner_id
        today = date.today()

        buckets = {
            '0_30': 0,
            '31_60': 0,
            '61_90': 0,
            '90_plus': 0,
        }

        lines = self.env['account.move.line'].search([
            ('partner_id', '=', partner.id),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('move_id.state', '=', 'posted'),
            ('reconciled', '=', False),
        ])

        for line in lines:
            due_date = line.date_maturity or line.date
            days = (today - due_date).days

            amount = line.amount_residual

            if days <= 30:
                buckets['0_30'] += amount
            elif days <= 60:
                buckets['31_60'] += amount
            elif days <= 90:
                buckets['61_90'] += amount
            else:
                buckets['90_plus'] += amount

        return buckets


    def get_vendor_balance(self):
        self.ensure_one()

        partner = self.sale_id.broker_allotment_id.tender_id.partner_id

        lines = self.env['account.move.line'].search([
            ('partner_id', '=', partner.id),
            ('account_id.account_type', '=', 'liability_payable'),
            ('move_id.state', '=', 'posted'),
        ])

        total = sum(line.balance for line in lines)

        return -total

class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def action_create_returns(self):
        action = super().action_create_returns()
        if action.get('res_id'):
            picking = self.env['stock.picking'].browse(action['res_id'])
            original_picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
            if original_picking and original_picking.location_id:
                dest = original_picking.location_id.id
                picking.write({'location_dest_id': dest})
                picking.move_ids.write({'location_dest_id': dest})
                picking.move_line_ids.write({'location_dest_id': dest})
        return action
