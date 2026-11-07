# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMoveOldRecords(models.Model):
    _inherit = 'account.move'


    x_particulars = fields.Char(
        string='Particulars',
        help='Particulars from Sales Register'
    )
    x_buyer = fields.Char(
        string='Buyer',
        help='Buyer name from Sales Register'
    )
    x_buyer_address = fields.Char(
        string='Buyer Address',
        help='Buyer address from Sales Register'
    )
    x_consignee = fields.Char(
        string='Consignee',
        help='Consignee name from Sales Register'
    )
    x_consignee_address = fields.Char(
        string='Consignee Address',
        help='Consignee address from Sales Register'
    )
    x_voucher_type = fields.Char(
        string='Voucher Type',
        help='Voucher type from Sales Register'
    )
    x_voucher_ref_no = fields.Char(
        string='Voucher Ref. No.',
        help='Voucher reference number from Sales Register'
    )
    x_sales_tax_no = fields.Char(
        string='Sales Tax No.',
        help='Sales tax number from Sales Register'
    )
    x_service_tax_no = fields.Char(
        string='Service Tax No.',
        help='Service tax number from Sales Register'
    )
    x_pan_no = fields.Char(
        string='PAN No.',
        help='PAN number from Sales Register'
    )
    x_cst_no = fields.Char(
        string='CST No.',
        help='CST number from Sales Register'
    )
    x_narration = fields.Char(
        string='Narration',
        help='Narration from Sales Register'
    )
    x_order_no_date = fields.Char(
        string='Order No. & Date',
        help='Order number and date from Sales Register'
    )
    x_terms_of_payment = fields.Char(
        string='Terms of Payment',
        help='Terms of payment from Sales Register'
    )
    x_other_references = fields.Char(
        string='Other References',
        help='Other references from Sales Register'
    )
    x_terms_of_delivery = fields.Char(
        string='Terms of Delivery',
        help='Terms of delivery from Sales Register'
    )
    x_delivery_note_no_date = fields.Char(
        string='Delivery Note No. & Date',
        help='Delivery note number and date from Sales Register'
    )
    x_despatch_doc_no = fields.Char(
        string='Despatch Doc. No',
        help='Despatch document number from Sales Register'
    )
    x_despatch_through = fields.Char(
        string='Despatch Through',
        help='Despatch through from Sales Register'
    )
    x_destination = fields.Char(
        string='Destination',
        help='Destination from Sales Register'
    )
    x_place_of_receipt = fields.Char(
        string='Place of Receipt by Shipper',
        help='Place of receipt by shipper from Sales Register'
    )
    x_vessel_flight_no = fields.Char(
        string='Vessel/Flight No.',
        help='Vessel or flight number from Sales Register'
    )
    x_port_of_loading = fields.Char(
        string='Port of Loading',
        help='Port of loading from Sales Register'
    )
    x_port_of_discharge = fields.Char(
        string='Port of Discharge',
        help='Port of discharge from Sales Register'
    )
    x_country_to = fields.Char(
        string='Country To',
        help='Country to from Sales Register'
    )
    x_shipping_no = fields.Char(
        string='Shipping No.',
        help='Shipping number from Sales Register'
    )
    x_shipping_date = fields.Char(
        string='Shipping Date',
        help='Shipping date from Sales Register (stored as text)'
    )
    x_port_code = fields.Char(
        string='Port Code',
        help='Port code from Sales Register'
    )
    x_alt_units = fields.Char(
        string='Alt. Units',
        help='Alternate units from Sales Register'
    )


    x_quantity = fields.Float(
        string='Quantity',
        digits=(16, 3),
        help='Quantity from Sales Register'
    )
    x_rate = fields.Float(
        string='Rate',
        digits=(16, 2),
        help='Rate from Sales Register'
    )
    x_value = fields.Float(
        string='Value',
        digits=(16, 2),
        help='Value from Sales Register'
    )
    x_round_off = fields.Float(
        string='Round Off',
        digits=(16, 2),
        help='Round off amount from Sales Register'
    )
    


    x_bill_particulars = fields.Char(
        string='Particulars',
        help='Particulars from Purchase Register'
    )
    x_bill_supplier = fields.Char(
        string='Supplier',
        help='Supplier name from Purchase Register'
    )
    x_bill_supplier_address = fields.Char(
        string='Supplier Address',
        help='Supplier address from Purchase Register'
    )
    x_bill_consignee = fields.Char(
        string='Consignee',
        help='Consignee name from Purchase Register'
    )
    x_bill_consignee_address = fields.Char(
        string='Consignee Address',
        help='Consignee address from Purchase Register'
    )
    x_bill_voucher_type = fields.Char(
        string='Voucher Type',
        help='Voucher type from Purchase Register'
    )
    x_bill_voucher_no = fields.Char(
        string='Voucher No.',
        help='Voucher number from Purchase Register'
    )
    x_bill_sales_tax_no = fields.Char(
        string='Sales Tax No.',
        help='Sales tax number from Purchase Register'
    )
    x_bill_service_tax_no = fields.Char(
        string='Service Tax No.',
        help='Service tax number from Purchase Register'
    )
    x_bill_pan_no = fields.Char(
        string='PAN No.',
        help='PAN number from Purchase Register'
    )
    x_bill_cst_no = fields.Char(
        string='CST No.',
        help='CST number from Purchase Register'
    )
    x_bill_narration = fields.Char(
        string='Narration',
        help='Narration from Purchase Register'
    )
    x_bill_order_no_date = fields.Char(
        string='Order No. & Date',
        help='Order number and date from Purchase Register'
    )
    x_bill_terms_of_payment = fields.Char(
        string='Terms of Payment',
        help='Terms of payment from Purchase Register'
    )
    x_bill_other_references = fields.Char(
        string='Other References',
        help='Other references from Purchase Register'
    )
    x_bill_terms_of_delivery = fields.Char(
        string='Terms of Delivery',
        help='Terms of delivery from Purchase Register'
    )
    x_bill_receipt_note_no_date = fields.Char(
        string='Receipt Note No. & Date',
        help='Receipt note number and date from Purchase Register'
    )
    x_bill_receipt_doc_lr_no = fields.Char(
        string='Receipt Doc./LR. No.',
        help='Receipt document / LR number from Purchase Register'
    )
    x_bill_despatch_through = fields.Char(
        string='Despatch Through',
        help='Despatch through from Purchase Register'
    )
    x_bill_destination = fields.Char(
        string='Destination',
        help='Destination from Purchase Register'
    )
    x_bill_place_of_receipt = fields.Char(
        string='Place of Receipt by Shipper',
        help='Place of receipt by shipper from Purchase Register'
    )
    x_bill_vessel_flight_no = fields.Char(
        string='Vessel/Flight No.',
        help='Vessel or flight number from Purchase Register'
    )
    x_bill_port_of_loading = fields.Char(
        string='Port of Loading',
        help='Port of loading from Purchase Register'
    )
    x_bill_port_of_discharge = fields.Char(
        string='Port of Discharge',
        help='Port of discharge from Purchase Register'
    )
    x_bill_country_to = fields.Char(
        string='Country To',
        help='Country to from Purchase Register'
    )
    x_bill_bill_of_entry_no = fields.Char(
        string='Bill of Entry No.',
        help='Bill of entry number from Purchase Register'
    )
    x_bill_bill_of_entry_date = fields.Char(
        string='Bill of Entry Date',
        help='Bill of entry date from Purchase Register (stored as text)'
    )
    x_bill_port_code = fields.Char(
        string='Port Code',
        help='Port code from Purchase Register'
    )
    x_bill_alt_units = fields.Char(
        string='Alt. Units',
        help='Alternate units from Purchase Register'
    )


    x_bill_quantity = fields.Float(
        string='Quantity',
        digits=(16, 3),
        help='Quantity from Purchase Register'
    )
    x_bill_rate = fields.Float(
        string='Rate',
        digits=(16, 2),
        help='Rate from Purchase Register'
    )
    x_bill_value = fields.Float(
        string='Value',
        digits=(16, 2),
        help='Value from Purchase Register'
    )
    x_bill_addl_cost = fields.Float(
        string='Addl. Cost',
        digits=(16, 2),
        help='Additional cost from Purchase Register'
    )
    x_bill_tds_purchase_goods = fields.Float(
        string='TDS on Purchase of Goods',
        digits=(16, 2),
        help='TDS on purchase of goods from Purchase Register'
    )
    x_bill_round_off = fields.Float(
        string='Round Off',
        digits=(16, 2),
        help='Round off amount from Purchase Register'
    )
    x_bill_softwar_amc = fields.Float(
        string='Softwar Amc Charges',
        digits=(16, 2),
        help='Software AMC charges from Purchase Register'
    )
    x_bill_telephone_bill = fields.Float(
        string='Telephone Bill',
        digits=(16, 2),
        help='Telephone bill from Purchase Register'
    )
    x_bill_employee_benefit = fields.Float(
        string='Employee Benifit Expenses',
        digits=(16, 2),
        help='Employee benefit expenses from Purchase Register'
    )
    x_bill_commission_brokerage = fields.Float(
        string='Commission and Brokerage 18%',
        digits=(16, 2),
        help='Commission and brokerage 18% from Purchase Register'
    )
    x_bill_food_licence = fields.Float(
        string='Food Licence Renewal Fee (Gst)',
        digits=(16, 2),
        help='Food licence renewal fee from Purchase Register'
    )
    x_bill_bank_charge = fields.Float(
        string='Bank Charge',
        digits=(16, 2),
        help='Bank charge from Purchase Register'
    )
    x_bill_sugar_purchase_rate_diff = fields.Float(
        string='Sugar Purchase Rate Diff',
        digits=(16, 2),
        help='Sugar purchase rate difference from Purchase Register'
    )
    x_bill_legal_consultancy = fields.Float(
        string='Legal Consultancy',
        digits=(16, 2),
        help='Legal consultancy from Purchase Register'
    )
    x_bill_tally_net = fields.Float(
        string='Tally.NET Subscription Services New MU',
        digits=(16, 2),
        help='Tally.NET subscription from Purchase Register'
    )
    x_bill_repair_maintance = fields.Float(
        string='Repair & Maintance',
        digits=(16, 2),
        help='Repair and maintenance from Purchase Register'
    )
    x_bill_mobile = fields.Float(
        string='Mobile',
        digits=(16, 2),
        help='Mobile charges from Purchase Register'
    )
    x_bill_software_odoo = fields.Float(
        string='Software (Odoo)',
        digits=(16, 2),
        help='Software Odoo charges from Purchase Register'
    )
    x_bill_igst_18 = fields.Float(
        string='IGST 18%',
        digits=(16, 2),
        help='IGST 18% from Purchase Register'
    )