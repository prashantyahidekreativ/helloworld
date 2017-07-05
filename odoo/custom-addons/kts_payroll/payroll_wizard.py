from openerp import models, fields, api, _
from openerp.exceptions import UserError

class kts_payroll_wizard(models.TransientModel):
    _name='kts.payroll.wizard'
    journal_id=fields.Many2one('account.journal',string='Journal')
    journal_amt_id=fields.Many2one('account.journal',string='Salary Journal', domain=[('type','=','bank')])
   
    @api.multi
    def register_employee_payment(self):
        if self.journal_amt_id and self.journal_id:
           context = dict(self._context or {})
           active_ids = context.get('active_ids', []) or []

           for record in self.env['kts.employee.salary'].browse(active_ids):
               if record.state not in ('draft'):
                  raise UserError(_("Selected Records cannot be payed as they are not in 'Draft' state."))
               record.write({'journal_id':self.journal_id.id, 'journal_amt_id':self.journal_amt_id.id})
               record.action_post_salary()
           return {'type': 'ir.actions.act_window_close'}
        else:
            raise UsserError(_('Please select Salary and Journal to post Salary '))