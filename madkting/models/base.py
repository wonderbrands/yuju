# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-08-01

from odoo import models, api

from ..log.logger import logger


class Base(models.AbstractModel):
    # events notifiers
    _inherit = 'base'

    @api.model
    def create(self, vals):
        record = super(Base, self).create(vals)
        try:
            self._event('on_record_create').notify(record, fields=vals.keys())
        except Exception as ex:
            logger.exception(ex)
        return record

    def write(self, vals):
        record = super(Base, self).write(vals)
        try:
            self._event('on_record_write').notify(record, fields=vals.keys())
        except Exception as ex:
            logger.exception(ex)
        return record
