from odoo.addons.component.core import Component
from ..log.logger import logger
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
        config = self.env['madkting.config'].get_config()

        if not config or not config.webhook_stock_enabled:
            return

        record_state = getattr(record, 'state', None)

        if config.stock_quant_available_quantity_enabled:
            if record_state in ['assigned', 'done'] and record.product_id.id_product_madkting:               
                try:
                    notifier.send_stock_webhook(self.env, record.product_id.id)
                except Exception as ex:
                    logger.exception(ex)
        else:
            if record_state == 'done' and record.product_id.id_product_madkting:
                try:
                    notifier.send_stock_webhook(self.env, record.product_id.id)
                except Exception as ex:
                    logger.exception(ex)
