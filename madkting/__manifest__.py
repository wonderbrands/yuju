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
    'version': '18.0.2.8.6',
    'license': 'Other proprietary',

    # any module necessary for this one to work correctly
    'depends': [
        # 'base',
        'sale_management',
        'stock',
        # 'component_event'
    ],
    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron_rule.xml',
        'data/config.xml',
        'data/webhook.xml',
        'data/cron_webhook_all.xml',
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

# Version 2.8.6
# Quita dependencia cachetools

# Version 2.8.5
# Fix folio sin serie

# Version 2.8.4
# Actualiza flujo webhooks precio

# Version 2.8.3
# Agrega detalle customer and address creation

# Version 2.8.2
# Actualiza busqueda por RUT en direccion de factura

# Version 2.8.1
# Agrega nuevo tipo de campo en mapeos

# Version 2.8.0
# Agrega funcion CRON para actualizar stock de productos x dia

# Version 2.7.0
# Agrega valores por default en config

# Version 2.6.7
# Agrupar Webhooks

# Version 2.6.6
# Fix campo lst_price en webhook de producto, fix en pago de factura campo requerido.

# Version 2.6.5
# Agrega campos marketplace_fee y seller_shipping_cost en update

# Version 2.6.4
# Agrega campos fechas

# Version 2.6.3
# BUG Fix creacion de atributos en producto

# Version 2.6.2
# Agrega opcion para quitar campo despues del mapeo

# Version 2.6.1
# Fix doctype serie invoice

# Version 2.6.0
# Fix yuju_due_date field

# Version 2.5.9
# Fix agregar direccion customer sin company_id

# Version 2.5.8
# Fix tipo de producto en actualizacion general de stock.

# Version 2.5.7
# Agrega opcion para buscar stock en campos calculados, oculta opcion de ubicaciones hijas
# TODO: se va a agregar funcion para agreupar stock de ubicaciones hijas en ubicacion padre

# Version 2.5.6
# Agrega opcion para actualizar nombre del cliente con direccion de factura

# Version 2.5.5
# Agrega opcion para buscar stock en ubicaciones hijas

# Version 2.5.4
# Fix webhook simple

# Version 2.5.3
# Fix metodo busqueda partners active.

# Version 2.5.2
# Actualiza metodo sen webhook_all para enviar webhook de los productos.

# Version 2.5.1
# Agrega configuracion de envio de webhooks stock por CRON, si no se activa, 
# se envia al momento de crear o actualizar el stock

# Version 2.5.0
# Agrega optimizacion de consultas pedidos y productos, agrega indices a campos usados en busquedas frecuentes

# Version 2.4.4
# Optimiza busqueda de pedidos existentes, ahora se puede configurar los dias a buscar desde la configuracion del modulo
# Fix no se actualiza webhook_price_pending en pricelist item y product template si no se activa en la config

# Version 2.4.3
# Actualiza CRON para reintentar envio de facturas,

# Version 2.4.2
# Agrega CRON para reintentar envio de facturas

# Version 2.4.1
# Fix name function in webhook record

# Version 2.4.0
# Actualiza permisos por defecto de los grupos de seguridad

# Version 2.3.9
# Actualiza metodo webhook price desde product template y pricelist con una tarea programada cada 10 minutos

# Version 2.3.8
# Actualiza metodo webhook price product not mapped

# Version 2.3.7
# Agrega yuju_due_date como campo actualizable

# Version 2.3.6
# Quita referencia a configuracion que no existe

# Version 2.3.5
# Actualiza funcion que lee el mimetype del archivo adjunto de la factura

# Version 2.3.4
# Agrega funcion para obtener stock de producto

# Version 2.3.3
# Update function create_webhook_record to update only records in status completed

# Version 2.3.2
# Fix location channels

# Version 2.3.1
# Fix reference product_data in process_webhooks
