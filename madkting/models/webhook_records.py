# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-08-01
import json
import requests

from datetime import datetime

from odoo import models, api, fields
from urllib import parse
from ..responses import results
from ..log.logger import logger

class MadktingWebhook(models.Model):
    _name = 'madkting.webhook'
    _description = 'Web hooks'

    __allowed_hook_types = ['stock', 'price']

    hook_type = fields.Selection([('stock', 'Stock'), ('price', 'Price')], string='Webhook type', required=True, default='stock')
    url = fields.Char('Webhook endpoint', size=400, required=False)
    id_shop = fields.Char('Id Shop Yuju', required=True, default="0")
    active = fields.Boolean('Active', default=True, required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True)
    message = fields.Text('Mensaje')
    updated_at = fields.Datetime(string="Updated at", readonly=True)

    # _sql_constraints = [
    #     ('unique_webhook_company', 'unique(hook_type,company_id)', 'The webhook should be unique per company')
    # ]

    @api.model
    def get(self, hook_id=None, hook_type=None):
        """
        :param hook_id:
        :type hook_id: int
        :param hook_type:
        :type hook_type: str
        :return:
        :rtype: dict
        """
        if hook_id:
            webhook = self.search([('id', '=', hook_id)], limit=1)

            if not webhook:
                return results.error_result(
                    'not_exists',
                    'The resource that you are looking for doesn\'t exists or has been deleted'
                )
            return results.success_result(webhook.__get_data())

        if hook_type:
            if hook_type not in self.__allowed_hook_types:
                return results.error_result('invalid_hook_type')

            webhooks = self.search([('hook_type', '=', hook_type)])
        else:
            webhooks = self.search([])

        if not webhooks:
            return results.success_result([])

        data = list()

        for hook in webhooks:
            data.append(hook.__get_data())

        return results.success_result(data)

    @api.model
    def create_webhook(self, hook_type, url, company_id):
        """
        :param hook_type:
        :type hook_type: str
        :param url:
        :type url: str
        :return:
        :rtype: dict
        """
        if hook_type not in self.__allowed_hook_types:
            return results.error_result('invalid_hook_type')

        parse_result = parse.urlparse(url)

        if not parse_result.scheme or not parse_result.netloc:
            return results.error_result('invalid_hook_url')

        try:
            webhook = self.create({
                'hook_type': hook_type,
                'url': url,
                'active': True,
                'company_id' : company_id
            })
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('create_webhook_error', str(ex))
        else:
            return results.success_result(webhook.__get_data())

    @api.model
    def update_webhook(self, hook_id, **kwargs):
        """
        :param hook_id:
        :type hook_id:  int
        :param kwargs:
        :return:
        :rtype: dict
        """
        webhook = self.search([('id', '=', hook_id)], limit=1)

        if not webhook:
            return results.error_result(
                    'not_exists',
                    'The resource that you are looking for doesn\'t exists or has been deleted'
                )
        try:
            webhook.write(kwargs)
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('write_exception', str(ex))
        else:
            return results.success_result(webhook.__get_data())

    @api.model
    def activate(self, hook_id):
        """
        :param hook_id:
        :return:
        """
        webhook = self.search([('id', '=', hook_id)], limit=1)

        if not webhook:
            return results.error_result(
                    'not_exists',
                    'The resource that you are looking for doesn\'t exists or has been deleted'
                )

        return webhook.change_status(active=True)

    @api.model
    def deactivate(self, hook_id):
        """
        :param hook_id:
        :return:
        """
        webhook = self.search([('id', '=', hook_id)], limit=1)

        if not webhook:
            return results.error_result(
                    'not_exists',
                    'The resource that you are looking for doesn\'t exists or has been deleted'
                )

        return webhook.change_status(active=False)

    def change_status(self, active):
        """
        :param active:
        :type active: bool
        :return:
        :rtype: dict
        """
        self.ensure_one()
        try:
            self.active = active
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('activate_webhook_exception')
        else:
            return results.success_result()

    def __get_data(self):
        """
        :return:
        :rtype: dict
        """
        self.ensure_one()
        data = self.copy_data()[0]
        data['id'] = self.id
        return data

    def send_webhook_all(self):
        """
        :return:
        :rtype: dict
        """

        for rec in self:

            company_id = rec.company_id.id
            config = self.env['madkting.config'].get_config(company_id)

            if config.webhook_product_mapped:
                product_ids = self.env['product.product'].with_context(
                    prefetch_fields=[
                        'default_code', 
                        'id_product_madkting'
                    ]).search([('id_product_madkting', '!=', False)])
            else:
                product_ids = self.env['product.product'].with_context(
                    prefetch_fields=[
                        'default_code', 
                        'id_product_madkting'
                    ]).search([('is_storable', '=', True), ('default_code', '!=', False)])

            if not product_ids:
                user_id = self.env.user.id
                user_company_id = self.env.user.company_id.id
                rec.message = f"No products found, User: {user_id}, Company User: {user_company_id}, Company Processed: {company_id}"
                return False
            
            # En esta parte como son webhooks se va a enviar tambien incluidas las ubicaciones de stock de canales
            location_ids = self.env['product.product']._get_location_ids(config, with_channels=True)
            stock_data = self.env['product.product'].get_stock_products(
                products=product_ids,
                location_ids=location_ids,
                company_id=company_id
            )

            batchsize = config.webhook_product_batchsize if config.webhook_product_batchsize > 0 else 20
            
            wh_records = self.env["yuju.webhook.record"]
            for product_data in self.env['product.product'].split_into_chunks(stock_data, batchsize):
                # product_data = self.process_webhook_chunk(product_ids=prod_ids, config=config, company_id=company_id, location_ids=location_ids)
                auto_send = config.webhook_auto_send_enabled
                wh_records.prepare_webhook_cron(webhook_body=product_data, company_id=company_id, type_webhook='stock', auto_send=auto_send)
            
            # for product in product_ids:                
            #     wh_records.prepare_webhook(product, company_id, rec.id_shop)

            rec.message = f"Total processed: {len(product_ids.ids)}"
            rec.updated_at = datetime.now()
            return
    
class WebhookRecords(models.Model):

    _name = "yuju.webhook.record"
    _description = 'Yuju Webhook Record'
    _order = "date_webhook desc"

    product_id = fields.Many2one("product.product", string="Producto")
    company_id = fields.Many2one("res.company", string="Empresa")
    date_webhook = fields.Datetime(string="Fecha Webhook")
    date_send_webhook = fields.Datetime(string="Envio Webhook")
    date_response_webhook = fields.Datetime(string="Respuesta Webhook")
    event = fields.Selection([("stock_update", "Stock Updated"), ("price_update", "Price Update")], string="Event Type")
    data = fields.Text(string="Webhook Data")
    url = fields.Text("URL Webhook")
    message = fields.Text("Mensaje")
    state = fields.Selection([("draft", "Pendiente"), ("done", "Realizado"), ("error", "Error")], string="Status")

    # @api.model
    # def prepare_webhook(self, product, company_id, id_shop=None):
    #     """
    #     TODO: register webhook failures in order to implement "retries"
    #     :param env:
    #     :type env: Environment
    #     :param product_id:
    #     :type product_id: int
    #     :param hook_id:
    #     :type hook_id: int
    #     :return:
    #     """
    #     logger.debug('### SEND STOCK WEBHOOK ###')
    #     product_id = product.id
    #     logger.debug("Producto: {}".format(product_id))
    #     # if not product.company_id:
    #     #     company_id = env.user.company_id.id
    #     # else:
    #     #     company_id = product.company_id.id
    #     logger.debug("Company: {}".format(company_id))
    #     # product = env['product.product'].search([('id', '=', product_id)], limit=1)
    #     config = self.env['madkting.config'].get_config(company_id)

    #     logger.debug("CONFIG RETURNED {}".format(config))

    #     if not config:
    #         logger.debug("### NO CONFIG FOUND FOR COMPANY {} ###".format(company_id))
    #         return

    #     actual_dbname = self.env.cr.dbname
    #     config_dbname = config.dbname

    #     if actual_dbname != config_dbname:
    #         logger.warning(f"Database configured is different from {actual_dbname}")
    #         return

    #     if config.dropship_enabled and not config.dropship_webhook_enabled:
    #         logger.debug("### NO STOCK ON DROPSHIP WEBHOOK DISABLED ###")
    #         return

    #     if not config.stock_source_multi:
    #         logger.debug("### No se han definido las fuentes de stock ###")
    #         return
        
    #     total_stock = 0
    #     ubicaciones_stock = {}
    #     location_ids = config.stock_source_multi.split(',')
    #     location_ids = list(map(int, location_ids))

    #     for location_id in location_ids:
    #         logger.debug("Location ID {}".format(location_id))
    #         location = self.env['stock.location'].search([('id', '=', location_id)], limit=1)
    #         if location.id:
    #             logger.debug("Location ID {} Found".format(location_id))
    #             if config and config.stock_quant_available_quantity_enabled:
    #                 qty_in_branch = product.with_context({'location' : location.id}).free_qty
    #                 logger.debug("Location ID {} Qty: {}".format(location_id, qty_in_branch))
    #             else:
    #                 qty_in_branch = product.with_context({'location' : location.id}).qty_available
    #             ubicaciones_stock.update({location.id : qty_in_branch})
    #             total_stock += int(qty_in_branch)
    #         else:
    #             logger.debug("Location {} not found in company {}".format(location_id, company_id))

    #     if config.stock_source_channels:
    #         location_channel_ids = config.stock_source_channels.split(',')
    #         location_channel_ids = list(map(int, location_channel_ids))
    #         logger.debug(f"Locations Channels {location_channel_ids}")

    #         for location_id in location_channel_ids:
    #             location = self.env['stock.location'].search([('id', '=', int(location_id))], limit=1)
    #             if location.id:
    #                 if config and config.stock_quant_available_quantity_enabled:
    #                     qty_in_branch = product.with_context({'location' : location.id}).free_qty
    #                 else:
    #                     qty_in_branch = product.with_context({'location' : location.id}).qty_available
                    
    #                 if location_id not in ubicaciones_stock:
    #                     ubicaciones_stock.update({location.id : qty_in_branch})


    #     if not ubicaciones_stock:
    #         logger.debug("No quantitites found for location {} in company {}".format(location_id, company_id))
    #         return

    #     domain = [
    #         ('hook_type', '=', 'stock'),
    #         ('active', '=', True),
    #         ('company_id', '=', company_id)
    #     ]

    #     if id_shop:
    #         domain.append(('id_shop', '=', id_shop))

    #     webhook_suscriptions = self.env['madkting.webhook'].search(domain)

    #     webhook_body = {
    #         'product_id': product.id,
    #         'company_id': company_id,
    #         'default_code': product.default_code,
    #         'event': 'stock_update',
    #         'quantities' : ubicaciones_stock,
    #     }

    #     for webhook in webhook_suscriptions:
    #         """
    #         TODO: if the webhook fails store it into a database for retry implementation
    #         """
    #         url_webhook = "{}/{}?id_shop={}".format(config.service_url, webhook.url, webhook.id_shop)
    #         wh_record = self.create_webhook_record(product.id, company_id, webhook_body, url_webhook)
    #         if wh_record.id and config.webhook_stock_enabled:
    #             wh_record.send_webhook()

    @api.model
    def prepare_webhook_cron(self, webhook_body, company_id, type_webhook='stock', auto_send=False, product_id=None):
        """
        TODO: register webhook failures in order to implement "retries"
        :param env:
        :type env: Environment
        :param product_id:
        :type product_id: int
        :param hook_id:
        :type hook_id: int
        :return:
        """
        logger.debug('### SEND STOCK WEBHOOK (CRON) ###')
        logger.debug("Company: {}".format(company_id))
        config = self.env['madkting.config'].get_config(company_id)
        logger.debug("CONFIG RETURNED {}".format(config))

        if not config:
            logger.debug("### NO CONFIG FOUND FOR COMPANY {} ###".format(company_id))
            return

        actual_dbname = self.env.cr.dbname
        config_dbname = config.dbname

        if actual_dbname != config_dbname:
            logger.warning(f"Database configured is different from {actual_dbname}")
            return

        domain = [
            ('hook_type', '=', type_webhook),
            ('active', '=', True),
            ('company_id', '=', company_id)
        ]

        webhook_suscriptions = self.env['madkting.webhook'].search(domain)

        for webhook in webhook_suscriptions:
            """
            TODO: if the webhook fails store it into a database for retry implementation
            """
            url_webhook = f"{config.service_url}/{webhook.url}?id_shop={webhook.id_shop}&version=multi&event={type_webhook}_update"
            wh_record = self.create_webhook_record(product_id=product_id, company_id=company_id, webhook_body=webhook_body, url=url_webhook)
            if wh_record and auto_send:
                wh_record.send_webhook()


    # @api.model
    # def prepare_webhook_price(self, product, company_id, new_price):
    #     """
    #     TODO: register webhook failures in order to implement "retries"
    #     :param env:
    #     :type env: Environment
    #     :param product_id:
    #     :type product_id: int
    #     :param hook_id:
    #     :type hook_id: int
    #     :return:
    #     """
    #     logger.debug('### SEND PRICE WEBHOOK ###')
    #     product_id = product.id
    #     logger.debug("Producto: {}".format(product_id))
    #     logger.debug("Company: {}".format(company_id))
    #     config = self.env['madkting.config'].get_config(company_id)

    #     last_update = self.search([("product_id", "=", product_id), ("event", "=", "price_update"), ("state", "=", "done")])
    #     if last_update and config.validate_price_webhook_enabled:
    #         wh_data = json.loads(last_update.data)
    #         logger.info(wh_data)
    #         last_price = wh_data.get("price")
    #         last_price = float(last_price) if last_price else 0
    #         logger.info(last_price)
    #         if last_price == new_price:
    #             logger.info("return")
    #             return

        

    #     domain = [
    #         ('hook_type', '=', 'price'),
    #         ('active', '=', True),
    #         ('company_id', '=', company_id)
    #     ]

    #     webhook_suscriptions = self.env['madkting.webhook'].search(domain)

    #     webhook_body = {
    #         'product_id': product.id,
    #         'company_id': company_id,
    #         'default_code': product.default_code,
    #         'event': 'price_update',
    #         'price': new_price
    #     }

    #     for webhook in webhook_suscriptions:
    #         """
    #         TODO: if the webhook fails store it into a database for retry implementation
    #         """
    #         url_webhook = "{}/{}?id_shop={}".format(config.service_url, webhook.url, webhook.id_shop)
    #         wh_record = self.create_webhook_record(product.id, company_id, webhook_body, url_webhook, event="price_update")
    #         if wh_record.id and config.webhook_price_enabled:
    #             wh_record.send_webhook()
    
    @api.model
    def create_webhook_record(self, product_id, company_id, webhook_body, url, event='stock_update'):
        wh_record = None
        if product_id:
            domain = [
                ("product_id", "=", product_id),
                ("company_id", "=", company_id),
                ("event", "=", event),
                # ("url", "=", url),
                # ("state", "=", 'done'),
            ]

            wh_record = self.search(domain, order="date_webhook desc")
            if not wh_record:
                wh_record = self.create({
                    "product_id": product_id,
                    "company_id": company_id,
                    "date_webhook": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "event": event,
                    "data": json.dumps(webhook_body),
                    "url": url,
                    "state": "draft"
                })
            else:            
                wh_record[-1].write({
                    "state": "draft",
                    "date_webhook": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data": json.dumps(webhook_body)
                })
        else:
            wh_record = self.create({
                "company_id": company_id,
                "date_webhook": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": event,
                "data": json.dumps(webhook_body),
                "url": url,
                "state": "draft"
            })
        
        return wh_record

    def send_webhook(self):
        """
        :return:
        """
        headers = {'Content-Type': 'application/json'}
        for rec in self:
            # data = json.loads(rec.data)
            try:
                rec.date_send_webhook = datetime.now()
                response = requests.post(rec.url, data=rec.data, headers=headers)
            except Exception as ex:
                logger.exception(ex)
                rec.state = "error"
                rec.date_response_webhook = datetime.now()
                rec.message = f"Error sending webhook: {ex}"
                return False
            else:
                rec.date_response_webhook = datetime.now()
                if not response.ok:
                    logger.error(response.text)
                    rec.state = "error"
                    rec.message = f"Error on response webhook: {response.text}"
                    return False
                rec.state = "done"
                rec.message = response.text
                return True
