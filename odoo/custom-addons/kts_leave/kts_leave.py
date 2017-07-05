from openerp import models, fields, api, _
from openerp.exceptions import UserError
from openerp.osv.fields import related
import math
import calendar
import datetime
from datetime import date, timedelta as td, datetime

class kts_leave_holidays(models.Model):
    _inherit = "hr.holidays"
    request_type=fields.Selection([
        ('leave_request', 'Leave Request'),
        ('encashment_request', 'Encashment Request'),
        ], string='Request Type')
    
    @api.onchange('request_type')
    def request_type_on_change(self):
        leave_types=[]
        if self.request_type=='encashment_request':
            leave_types=self.env['hr.holidays.status'].search([('leave_encashment','=',True)])
            self.update({'holiday_status_id':leave_types.ids})
        else:    
            leave_types=self.env['hr.holidays.status'].search([])
            self.update({'holiday_status_id':leave_types.ids})
        return {'domain':{'holiday_status_id':[('id','in',leave_types.ids)]}}
    
    @api.onchange('holiday_status_id','date_from','date_to')
    def holiday_status_on_change(self):
        calc_days=1
        no_of_days=0
        total_week_off=0
        total_holiday=0
        
        if self.holiday_status_id and self.date_from and self.date_to:
            d_from=datetime.strptime(self.date_from,"%Y-%m-%d %H:%M:%S")
            d_to=datetime.strptime(self.date_to,"%Y-%m-%d %H:%M:%S")
            d1=date(d_from.year,d_from.month,d_from.day)
            d2=date(d_to.year,d_to.month,d_to.day)
            delta=d2-d1
            total_week_off=0
            total_holiday=0
            if self.holiday_status_id.weekoff_exclude:
                for i in range(delta.days+1):
                    date_str=d1 + td(days=i)
                    cmp=str(date_str.weekday())
                    #print date_str.weekday() 
                    weekoff=self.env['kts.week.off'].search([('name','=',cmp)])
                    if weekoff:
                        total_week_off+=1;
            
            if self.holiday_status_id.holiday_exclude:
                holidays=self.env['kts.holidays.creation'].search([])
                for holiday in holidays:
                    d_holiday=datetime.strptime(holiday.holiday_date,"%Y-%m-%d %H:%M:%S")
                    d3=date(d_holiday.year,d_holiday.month,d_holiday.day)
                    
                    if (d3>=d1) and (d2>=d3):
                        total_holiday+=1
            if (self.date_to and self.date_from) and (self.date_from <= self.date_to):
                diff_day = self._get_number_of_days(self.date_from, self.date_to)
                no_of_days = round(math.floor(diff_day))+1
                self.number_of_days_temp=no_of_days-total_holiday-total_week_off
                if self.holiday_status_id.double_validation:
                    if self.employee_id and self.employee_id.parent_id:
                        self.state='validate1'
                    else:
                        raise UserError(_('You need to confirm from your manager and manager not assigned.'))
            else:
                self.number_of_days_temp = 0
        else:
            self.number_of_days_temp = 0
        return {'value':{'number_of_days_temp':self.number_of_days_temp}}
    
    def holidays_validate(self, cr, uid, ids, context=None):
        obj_emp = self.pool.get('hr.employee')
        ids2 = obj_emp.search(cr, uid, [('user_id', '=', uid)])
        manager = ids2 and ids2[0] or False
        self.write(cr, uid, ids, {'state': 'validate'}, context=context)
        data_holiday = self.browse(cr, uid, ids)
        for record in data_holiday:
            if record.double_validation:
                self.write(cr, uid, [record.id], {'manager_id2': manager})
            else:
                self.write(cr, uid, [record.id], {'manager_id': manager})
            if record.holiday_type == 'employee' and record.type == 'remove' and record.request_type != 'encashment_request':
                meeting_obj = self.pool.get('calendar.event')
                meeting_vals = {
                    'name': record.display_name,
                    'categ_ids': record.holiday_status_id.categ_id and [(6,0,[record.holiday_status_id.categ_id.id])] or [],
                    'duration': record.number_of_days_temp * 8,
                    'description': record.notes,
                    'user_id': record.user_id.id,
                    'start': record.date_from,
                    'stop': record.date_to,
                    'allday': False,
                    'state': 'open',            # to block that meeting date in the calendar
                    'class': 'confidential'
                }
                #Add the partner_id (if exist) as an attendee
                if record.user_id and record.user_id.partner_id:
                    meeting_vals['partner_ids'] = [(4,record.user_id.partner_id.id)]

                ctx_no_email = dict(context or {}, no_email=True)
                meeting_id = meeting_obj.create(cr, uid, meeting_vals, context=ctx_no_email)
                self._create_resource_leave(cr, uid, [record], context=context)
                self.write(cr, uid, ids, {'meeting_id': meeting_id})
            elif record.holiday_type == 'category':
                emp_ids = record.category_id.employee_ids.ids
                leave_ids = []
                batch_context = dict(context, mail_notify_force_send=False)
                for emp in obj_emp.browse(cr, uid, emp_ids, context=context):
                    vals = {
                        'name': record.name,
                        'type': record.type,
                        'holiday_type': 'employee',
                        'holiday_status_id': record.holiday_status_id.id,
                        'date_from': record.date_from,
                        'date_to': record.date_to,
                        'notes': record.notes,
                        'number_of_days_temp': record.number_of_days_temp,
                        'parent_id': record.id,
                        'employee_id': emp.id
                    }
                    leave_ids.append(self.create(cr, uid, vals, context=batch_context))
                for leave_id in leave_ids:
                    # TODO is it necessary to interleave the calls?
                    for sig in ('confirm', 'validate', 'second_validate'):
                        self.signal_workflow(cr, uid, [leave_id], sig)
        return True

             
class kts_leave(models.Model):
    _inherit = "hr.holidays.status"
    _description = "Kts Leave"
    holiday_exclude = fields.Boolean('Holiday Exclude')
    weekoff_exclude = fields.Boolean('Weekoff Exclude')
    leave_encashment = fields.Boolean('Leave Encashment')

class kts_holiday_creation(models.Model):
    _name = 'kts.holidays.creation'
    _description = "Kts Holiday"    
    name= fields.Char('Reason', size=56)
    holiday_date=fields.Datetime('Holiday Date')        

class kts_week_off(models.Model):
    _name = 'kts.week.off'  
    _description = "Kts week off"  
    name=fields.Selection([
        ('6', 'Sunday'),
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2','Wendsday'),
        ('3','Thursday'),
        ('4','Friday'),
        ('5','Saturday'),
        ], string='Week off day')
    
    
class kts_leave_period(models.Model):
    _name = 'kts.leave.period'  
    _description = "Kts Leave Period"  
    name= fields.Char('Leave Period Name', size=56)
    start_date=fields.Date('Start Date')
    end_date=fields.Date('End Date')
    leave_quarter = fields.Boolean('Quarter ')
    leave_semi = fields.Boolean('Semi Year')
    leave_year = fields.Boolean('Year')
    leave_generate = fields.Boolean('Leave Generate')
    
    @api.multi
    def unlink(self):
        if self.leave_generate:
            raise UserError(_('You cannot delete a period which is in Generated state.'))
        return super(kts_leave_period, self).unlink()

class kts_allocation_rules(models.Model):
    _name = 'kts.allocation.rules'  
    _description = "Kts Allocation Rues"  
    designatione= fields.Many2one('hr.job','Designation')
    hr_holiday_status=fields.Many2one('hr.holidays.status','Type')
    no_of_days=fields.Integer(string='No. of Days',)
    assignment_frequency = fields.Selection([('quarter','Quarter'),('semi','Semi quarter'),('year','Yearly')],'Assign Frequency')

class kts_generate_leave_allocation(models.Model):
    _name = 'kts.generate.leave.allocation'  
    _description = "Kts Generate Leave Allocation "
    name= fields.Char('Name', size=56)  
    period_type= fields.Many2one('kts.leave.period','Period')
    state=fields.Selection([
        ('draft', 'New'),
        ('generated', 'Generated'),
        ], string='Status', default="draft")

    @api.multi
    def unlink(self):
        if self.state=='generated':
            raise UserError(_('You cannot delete a leave allocation which is in Generated state.'))
        return super(kts_generate_leave_allocation, self).unlink()

    @api.multi
    def generate_allocation(self):
        self.ensure_one()
        if self.period_type.leave_generate:
            raise UserError(_('Leave generation process already done for this leave Period.'))
        if self.period_type:
            if self.period_type.leave_quarter:
                allocation_rules=self.env['kts.allocation.rules'].search([('assignment_frequency','=','quarter')],order='id asc')
                for allocation_id in allocation_rules:
                    hr_employee_ids=self.env['hr.employee'].search([('job_id','=',allocation_id.designatione.id)],order='id asc')
                    values={}
                    for emp_id in hr_employee_ids:
                        values={
                                'name':'%s allocated to %s for period %s'%(allocation_id.hr_holiday_status.name,emp_id.name,self.period_type.name),
                                'holiday_type':'employee',
                                'holiday_status_id':allocation_id.hr_holiday_status.id,
                                'employee_id':emp_id.id,
                                'type':'add',
                                'number_of_days_temp':allocation_id.no_of_days,
                                'state':'validate',
                                }
                        obj= self.env['hr.holidays'].create(values)

            if self.period_type.leave_semi:
                allocation_rules=self.env['kts.allocation.rules'].search([('assignment_frequency','=','semi')],order='id asc')
                for allocation_id in allocation_rules:
                    hr_employee_ids=self.env['hr.employee'].search([('job_id','=',allocation_id.designatione.id)],order='id asc')
                    values={}
                    for emp_id in hr_employee_ids:
                        values={
                                'name':'%s for %s'%(allocation_id.hr_holiday_status.name,emp_id.name),
                                'holiday_type':'employee',
                                'holiday_status_id':allocation_id.hr_holiday_status.id,
                                'employee_id':emp_id.id,
                                'type':'add',
                                'number_of_days_temp':allocation_id.no_of_days,
                                'state':'validate',
                                }
                        obj= self.env['hr.holidays'].create(values)

            
            if self.period_type.leave_year:
                allocation_rules=self.env['kts.allocation.rules'].search([('assignment_frequency','=','year')],order='id asc')
                for allocation_id in allocation_rules:
                    hr_employee_ids=self.env['hr.employee'].search([('job_id','=',allocation_id.designatione.id)],order='id asc')
                    values={}
                    for emp_id in hr_employee_ids:
                        values={
                                'name':'%s for %s'%(allocation_id.hr_holiday_status.name,emp_id.name),
                                'holiday_type':'employee',
                                'holiday_status_id':allocation_id.hr_holiday_status.id,
                                'employee_id':emp_id.id,
                                'type':'add',
                                'number_of_days_temp':allocation_id.no_of_days,
                                'state':'validate',
                                }
                        obj= self.env['hr.holidays'].create(values)
            self.period_type.leave_generate=True
            self.state='generated'

       