# -*- coding: utf-8 -*-
{
    'name': 'Web Widget Pill Icon (Conditional Icons & Colors)',
    'summary': 'Transform any field into a stylish pill/badge with dynamic FontAwesome icons and CSS classes based on value mapping.',
    'version': '15.0.1.0.0',
    'category': 'Web',
    'author': 'Chris',
    'website': 'https://github.com/chrisking94/odoo_addons/tree/main/web_widget_pill_icon',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'web_widget_pill_icon/static/src/css/pill_icon_widget.css',
            'web_widget_pill_icon/static/src/js/pill_icon_widget.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
