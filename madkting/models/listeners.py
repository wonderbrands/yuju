from odoo.addons.component.core import Component
from ..log.logger import logger
from ..log.logger import logs
from ..notifier import notifier

class MadktingStockMoveListener(Component):
    _name = 'madkting.stock.move.listener'
    _inherit = 'base.event.listener'
    _apply_on = ['stock.move']

    def on_record_create(self, record, fields=None):
        """
        :param record:
        :param fields:
        :return:
        """
        self.__send_stock_webhook(record)

    def on_record_write(self, record, fields=None):
        """
        :param record:
        :param fields:
        :return:
        """
        self.__send_stock_webhook(record)

    def on_record_unlink(self, record):
        """
        :param record:
        :return:
        """
        self.__send_stock_webhook(record)

    def __send_stock_webhook(self, record):
        """
        :param record:
        :return:
        """
        config = self.env['madkting.config'].sudo().get_config()

        # logs("LISTENER STOCK MOVE", config)
        # logs(record, config)

        if not config or not config.webhook_stock_enabled:
            return

        record_state = getattr(record, 'state', None)
        # logs(record_state, config)
        record_product = getattr(record, 'product_id', None)
        # logs(record_product, config)
        record_product_yuju = getattr(record_product, 'id_product_madkting', None)
        # logs(record_product_yuju, config)
        if record_state in ['assigned', 'done'] and record_product_yuju:            
            # logs("############## ok #############", config)
            try:
                notifier.send_stock_webhook(self.env, record.product_id, record.company_id.id)
            except Exception as ex:
                logger.exception(ex)
        
# https://apps.yuju.io/api/sales/in/2301?id_shop=1085876
