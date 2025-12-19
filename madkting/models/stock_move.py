from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.move'
    
    # === CREATE ===
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._send_madkting_stock_webhook(event="create")
        return records

    # === WRITE ===
    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._send_madkting_stock_webhook(event="write")
        return res

    # === UNLINK ===
    def unlink(self):
        for rec in self:
            rec._send_madkting_stock_webhook(event="unlink")
        return super().unlink()

    # === COMMON WEBHOOK METHOD ===
    def _send_madkting_stock_webhook(self, event):

        if isinstance(self, bool):
            _logger.debug("Bool object for record")
            return

        company_id = self.company_id.id if self and self.company_id else None
        if not company_id:
            _logger.debug("No company id for record")
            return
        
        config = self.env['madkting.config'].get_config(company_id)

        if not config:
            _logger.warning("No config set in webhook listener")
            return
        
        if not config.webhook_stock_enabled:
            _logger.debug("Webhook stock not enabled")
            return

        record_state = getattr(self, 'state', None)
        if record_state in ['assigned', 'done', 'cancel']:

            if config.webhook_stock_cron_enabled:
                if not self.product_id.webhook_pending:
                    _logger.info("Update product webhook pending")
                    self.product_id.webhook_pending = True
            else:
                _logger.info("Webhook stock cron not enabled")
                auto_send = config.webhook_auto_send_enabled
                self.product_id.send_webhook_action(auto_send=auto_send, config=config)