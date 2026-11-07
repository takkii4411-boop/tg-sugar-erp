# -*- coding: utf-8 -*-
{
    'name': 'Broker Process',
    'summary': 'Broker allotment menus for partners and sale orders',
    'website': 'www.hmrcgroups.com',
    'author': 'HMRC Industry Private Limited',
    'sequence': 1,
    'support': 'contact@hmrcgroups.com',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'description': """
        Adds boolean fields in Res Partner & Sale Order.
        Creates two separate menus with domain filters.
    """,
    'depends': ['base', 'contacts', 'sale', 'purchase', 'product', 'uom', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron.xml',
        'data/mail_template.xml',
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
        'views/broker_allotment_view.xml',
        'wizard/broker_balance_views.xml',
        'wizard/price_update_wizard.xml',
        'views/partner_action.xml',
        'views/menu_items.xml',
        'report/report.xml',
        'report/template.xml',
    ],
    'images': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
