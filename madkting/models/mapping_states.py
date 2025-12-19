# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-07-19

from odoo import models, api, fields

class YujuMappingState(models.Model):
    _name = "yuju.mapping.state"
    _description = 'Yuju Mapping States'

    name = fields.Char('Estado Yuju')
    name_state = fields.Char('Estado')
    name_city = fields.Char('Ciudad')
    country_id = fields.Many2one('res.country', 'Pais')
