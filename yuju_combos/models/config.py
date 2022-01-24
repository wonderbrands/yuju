# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-08-01

from odoo import models, api, fields
from urllib import parse
from ..responses import results
from ..log.logger import logger


class MadktingConfig(models.Model):
    _inherit = 'madkting.config'
    _description = 'Config'

    mrp_route = fields.Many2one('stock.location.route', string='Ruta para Fabricacion')