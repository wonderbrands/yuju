# -*- coding: utf-8 -*-
{
    'name': "Yuju",

    'summary': """
        Integration with Yuju's platform""",

    'description': """
        Module integration with Yuju's software platform.
        - Create orders into your odoo software from marketplaces like Mercado Libre, Amazon, etc..
        - Create products from Yuju platform into odoo
        - Update your stock from odoo to your Yuju account.
    """,

    'author': "Gerardo A Lopez Vega @glopzvega",
    'email': "gerardo.lopez@yuju.io",
    'website': "https://yuju.io/",
    'category': 'Sales',
    'version': '2.2.6',
    'license': 'Other proprietary',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'sale_management',
        'stock',
        'component_event'
    ],
    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/config.xml',
        'views/mappings.xml',
        'views/webhooks.xml',
        'views/sale_order.xml',
        'views/product.xml',
        'views/menu_items.xml',
        # 'views/views.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
    "cloc_exclude": [
        # "lib/common.py", # exclude a single file
        # "data/*.xml",    # exclude all XML files in a specific folder
        "controllers/**/*",  # exclude all files in a folder hierarchy recursively
        "log/**/*",  # exclude all files in a folder hierarchy recursively
        "models/**/*",  # exclude all files in a folder hierarchy recursively
        "notifier/**/*",  # exclude all files in a folder hierarchy recursively
        "requirements/**/*",  # exclude all files in a folder hierarchy recursively
        "responses/**/*",  # exclude all files in a folder hierarchy recursively
        "security/**/*",  # exclude all files in a folder hierarchy recursively
        "views/**/*",  # exclude all files in a folder hierarchy recursively
    ]
}

# Version 2.0.0
# Actualiza proceso para envio de webhooks y guarda registro de envio

# Version 2.0.1
# Agrega prefijo Id factura en webhook

# Version 2.0.2
# Agrega metodo para cancelar pago asociado a factura si se cancela la orden

# Version 2.0.3
# Actualiza permisos generales para webhook record

# Version 2.0.4
# Agrega campo yuju carrier

# Version 2.0.5
# Agrega validacion de base de datos en la configuracion para webhooks de stock

# Version 2.0.6
# Fix folio strip

# Version 2.0.7
# Agrega company_id de registro en obtencion de configuracion

# Version 2.0.8
# Agrega validacion en envio de Webhook precios duplicados

# Version 2.0.9
# Agrega validacion tipo de registro antes de enviar webhook, 
# fix bool object in record error getting company for config

# Version 2.1.6
# Agrega parametros de company_id y campos adicionales en la orden.

# Version 2.1.7
# Agrega configuracion para validar si se actualiza el doctype en la factura (requiere mapeo de campos)

# Version 2.1.8
# Agrega visibilidad a los campos necesarios para validar si una venta esta duplicada, requiere grupo madkting_api

# Version 2.1.9
# Fix attachments report pdf not in same field

# Version 2.2.0
# Fix validacion partner busca case insensitive

# Version 2.2.1
# Update webhook all productos by config

# Version 2.2.2
# Actualiza mimetype

# Version 2.2.3
# AFix models and views for older models

# Version 2.2.4
# Fix Actualiza metodo conciliar facturas con pagos

# Version 2.2.5
# Fix product type

# Version 2.2.6
# Actualiza metodo para buscar mapeo de campos relacionados
