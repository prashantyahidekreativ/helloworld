from openerp import models, fields, api, _
from openerp.exceptions import UserError
from openerp import SUPERUSER_ID
class UserWizard(models.Model):
    _name='create.user.wizard'
    _description = "User Creation Wizard"
   
    
    company_id = fields.Many2one('res.company','Primary Client',required=True)
    group_id = fields.Many2one('res.groups','User Type',required=True,)
    user_first=fields.Char('User First Name',required=True)
    user_last=fields.Char('User Last Name',required=True)
    email=fields.Char('Email Address',required=True)
    login=fields.Char('Login',required=True)
    pwd=fields.Char('Password',required=True)
    open_flag=fields.Boolean('Open User Settings',default=False)
    
    @api.multi
    def create_user_button(self):
        self.ensure_one()
        dataobj = self.pool.get('ir.model.data')
        result = []
        dummy,group_id = dataobj.get_object_reference(self._cr, SUPERUSER_ID, 'base', 'group_user')
        result.append(group_id)
        dummy,group_id = dataobj.get_object_reference(self._cr, SUPERUSER_ID, 'base', 'group_partner_manager')
        result.append(group_id)
        result.append(self.group_id.id)
        vals={'company_id':self.company_id.id,
              'groups_id':[(4,res) for res in result],
              'name':self.user_first+' '+self.user_last,
              'email':self.email,
              'login':self.login,
              'password':self.pwd,
              'alias_contact':'everyone',
              }
        user_id=self.env['res.users'].create(vals)
        
        if self.open_flag:
            data_obj = self.env['ir.model.data']
            view = data_obj.xmlid_to_res_id('base.view_users_form')
        
            return { 'type': 'ir.actions.act_window', 
                'res_model':'res.users', 
                'res_id':user_id.id, 
                'view_type':'form', 
                'view_mode': 'form', 
                'views': [(view, 'form')],
                'view_id': view,
                'target': 'current',
                'context': self._context 
                 }
            
class  UserWizardGroup(models.Model):
    _inherit='res.groups'
    create_wizard_flag=fields.Boolean('Add in create User Wizard',default=False)           
            