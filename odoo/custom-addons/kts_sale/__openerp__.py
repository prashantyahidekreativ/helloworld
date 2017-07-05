# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Kts Sales Management',
    'version': '1.0',
    'category': 'Kts Sales Management',
    'sequence': 15,
    'summary': 'Quotations, Sales Orders, Invoicing',
    'description': """
    """,
    'website': 'https://www.kreativtech.com/',
    'depends': ['sale','crm'],
    'data':['kts_sale_view.xml', 'security/ir.model.access.csv',],
    'installable': True,
    'auto_install': False,
    'application': True,
}
