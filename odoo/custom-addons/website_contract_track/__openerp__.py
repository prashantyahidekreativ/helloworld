# -*- coding: utf-8 -*-

{
    'name': 'Website Contract Service',
    'category': 'Website',
    'author':'KreativTech',
    'sequence': 160,
    'website': 'http://www.kreativtech.com',
    'summary': 'Website, Contract, Service Tracker ',
    'version': '1.0',
    'description': """
         Website Contract Service Tracker
============

        """,
    'depends': ['kts_contract_management','website'],
    'data': [
        'data/data.xml',
        'views/templates.xml'
    ],
    'installable': True,
    'application': True,
}