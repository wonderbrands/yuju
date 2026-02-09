from odoo.addons.component.core import Component
from ..log.logger import logger
from ..log.logger import logs

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
        if isinstance(record, bool):
            logger.debug("Bool object for record")
            return

        company_id = record.company_id.id if record and record.company_id else None
        if not company_id:
            logger.debug("No company id for record")
            return
        
        config = self.env['madkting.config'].get_config(company_id)

        if not config:
            logger.warning("No config set in webhook listener")
            return
        
        if not config.webhook_stock_enabled:
            logger.debug("Webhook stock not enabled")
            return

        record_state = getattr(record, 'state', None)
        if record_state in ['assigned', 'done', 'cancel']:

            # if config.webhook_stock_cron_enabled:
            #     if not record.product_id.webhook_pending:
            #         logger.info("Update product webhook pending")
            #         record.product_id.webhook_pending = True
            # else:
            # logger.info("Webhook stock cron not enabled")
            auto_send = config.webhook_auto_send_enabled
            record.product_id.send_webhook_action(auto_send=auto_send, config=config)


# https://apps.yuju.io/api/sales/in/2301?id_shop=1085876
