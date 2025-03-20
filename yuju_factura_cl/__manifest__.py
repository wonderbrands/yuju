# -*- coding: utf-8 -*-
{
    'name': "Yuju Factura CL",

    'summary': """
        Facturacion Yuju CL""",

    'description': """
        Module Facturacion Yuju CL
    """,

    'author': "Gerardo A Lopez Vega @glopzvega",
    'email': "gerardo.lopez@yuju.io",
    'website': "https://yuju.io/",
    'category': 'Sales',
    'version': '0.0.2',
    'license': 'Other proprietary',

    # any module necessary for this one to work correctly
    'depends': [
        'madkting',
        'l10n_latam_invoice_document',
        'l10n_cl_edi'
    ],
    # always loaded
    'data': [
        'views/config_view.xml',
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
