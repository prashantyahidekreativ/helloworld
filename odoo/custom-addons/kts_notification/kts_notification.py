from openerp import models,fields,api,_
class kts_notification(models.Model):
    _inherit='mail.channel'
    
    @api.model
    def _referencable_models(self):
        models=self.env['res.request.link'].search([])
        return [(x.object, x.name) for x in models]
    
    ref_doc_id=fields.Selection(_referencable_models,string='Reference Document')
    
class kts_mail_message(models.Model):
    _inherit='mail.message'
    
    @api.multi
    def _notify(self, force_send=False, user_signature=True):
        channel_ids=self.env['mail.channel'].search([('ref_doc_id','=',self.model)])
        if channel_ids:
            self.channel_ids=[(6,0,channel_ids.ids)]
        
        ret=super(kts_mail_message, self)._notify(force_send, user_signature)
        return ret