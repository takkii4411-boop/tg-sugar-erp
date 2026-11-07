# -*- coding: utf-8 -*-
{
    'name': 'Portal Broker',
    'summary': 'Broker allotment menus for partners and sale orders',
    'website': 'www.hmrcgroups.com',
    'author': 'HMRC Industry Private Limited',
    'sequence': 1,
    'support': 'contact@hmrcgroups.com',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'description': """
Portal Broker Access
=====================
Provides portal user access to broker allotment features.

This module enables portal users to view their own broker allotment data.

Features:
- Auto-create portal users when is_broker_partner is set to True
- Portal users can only see their own broker.allotment records
- List view with filtering and sorting
- Detailed view with line items
- PDF report access
""",
    'depends': ['base', 'portal', 'sale_order_modifier_hmrc', 'party_sale_modifier_hmrc'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/res_partner_views.xml',
        'views/portal_broker_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
