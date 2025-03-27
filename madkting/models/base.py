# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-08-01

from odoo import models, api

from ..log.logger import logger


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)  # Keep it as a recordset
        for record, vals in zip(records, vals_list):  # Iterate through records and vals_list
            try:
                self._event('on_record_create').notify(record, fields=vals.keys())
            except Exception as ex:
                logger.exception(ex)
        return records  


    def write(self, vals):
        record = super(Base, self).write(vals)
        try:
            self._event('on_record_write').notify(record, fields=vals.keys())
        except Exception as ex:
            logger.exception(ex)
        return record
