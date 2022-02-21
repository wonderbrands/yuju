from odoo.api import Environment
from datetime import datetime as dt
from ..log.logger import logger
import requests
import json


def send_stock_webhook(env, product_id, hook_id=None):
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
    logger.debug("###Notifier send_stock_webhook")
    product = env['product.product'].search([('id', '=', product_id)], limit=1)

    if hook_id:
        webhook_suscriptions = env['madkting.webhook'].search([('id', '=', hook_id)])
    else:
        webhook_suscriptions = env['madkting.webhook'].search([
            ('hook_type', '=', 'stock'),
            ('active', '=', True)
        ])

    config = env['madkting.config'].get_config()

    logger.debug("### VALIDANDO SI SE TIENE LA CONFIGURACION DE STOCK HABILITADA ###")
    if config and config.stock_quant_available_quantity_enabled:
        logger.debug(True)
        ubicaciones_stock = {}
        for branch_id, stock in product.get_stock_by_location().items():
            location = env['stock.location'].search([('id', '=', int(branch_id))])
            qty_in_branch = env['stock.quant']._get_available_quantity(product, location)
            ubicaciones_stock.update({branch_id : qty_in_branch})
    else:
        logger.debug(False)
        ubicaciones_stock = product.get_stock_by_location()
        
    webhook_body = {
        'product_id': product.id,
        'default_code': product.default_code,
        'id_product_madkting': product.id_product_madkting,
        'event': 'stock_update',
        'qty_available': product.qty_available,
        'quantities': ubicaciones_stock
    }
    data = json.dumps(webhook_body)
    logger.debug(data)
    
    webhook_body.update({
        "fecha" : dt.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    webhook_data = json.dumps(webhook_body)
    product.write({"last_webhook_madkting" : webhook_data})

    headers = {'Content-Type': 'application/json'}
    for webhook in webhook_suscriptions:
        """
        TODO: if the webhook fails store it into a database for retry implementation
        """
        success = send_webhook(webhook.url, data, headers)


def send_webhook(url, data, headers):
    """
    :param url:
    :param data:
    :param headers:
    :return:
    """
    try:
        response = requests.post(url, data=data, headers=headers)
    except Exception as ex:
        logger.exception(ex)
        return False
    else:
        if not response.ok:
            logger.error(response.text)
            return False
        return True
