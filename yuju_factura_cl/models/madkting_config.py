# -*- coding: utf-8 -*-
# File:           madkting_config.py
# Author:         Gerardo Lopez
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2023-04-18

from odoo import models, fields


class MadktingConfig(models.Model):
    _inherit = 'madkting.config'
    _description = 'Config'

    validate_doctype_nit = fields.Boolean("Valida tipo de identificacion NIT")
    vat_separator = fields.Boolean("Separador VAT", help="Si se habilita, se agrega un separador al VAT en el penultimo digito")
    # validate_cafs = fields.Boolean('Valida folios facturacion')
    # cafs_document_type_id = fields.Many2one('l10n_latam.document.type', 'Tipo de documento')
    # doctype_default = fields.Char("Default Doc Type", help="Si se habilita la validacion de doc_type asigna este valor por defecto")
    # vat_prefix = fields.Char("Prefijo VAT", help="Si se habilita, se agrega un prefijo al VAT recibido")
