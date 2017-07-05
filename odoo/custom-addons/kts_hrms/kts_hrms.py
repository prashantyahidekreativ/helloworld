
import time
from openerp import SUPERUSER_ID
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.exceptions import UserError

DEFAULT_LOCAL_DATE_FORMAT='%d/%m/%Y'
DEFAULT_LOCAL_DATETIME_FORMAT='%d/%m/%Y %H:%M:%S'

def get_date_time_format(self, cr, context={}):
    pool_lang = self.pool.get('res.lang')
    lang = context.get('lang', 'en_US') or 'en_US'
    lang_ids = pool_lang.search(cr,SUPERUSER_ID,[('code','=',lang)])[0]
    lang_obj = pool_lang.browse(cr,SUPERUSER_ID,lang_ids)
    return lang_obj.date_format,lang_obj.time_format
    
def str_to_class(str):
    return getattr(sys.modules[__name__], str)

def getDateFromDateTime(self,cr,dateTime,context,format=DEFAULT_LOCAL_DATETIME_FORMAT, Obj=True):
    dateTimeStr=convertTimeInLocal(self,cr,dateTime,context)    
    obj= datetime.strptime(dateTimeStr, format)   
    return (obj.date() if Obj else obj.date().strftime(DEFAULT_SERVER_DATE_FORMAT)) 

def convertTimeInLocal(self,cr,date,context):
    obj= datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT)     
    date = datetime_field.context_timestamp(cr, SUPERUSER_ID,obj, context)
    dateFormat,timeFormat=get_date_time_format(self,cr, context)
    return date.strftime(dateFormat+' '+timeFormat)
                    
def get_time_in_UTC(dateTime,context={}):
    local = pytz.timezone (context.get('tz','Asia/Calcutta'))
    naive = datetime.strptime (dateTime, DEFAULT_SERVER_DATE_FORMAT+' %H:%M:%S')
    local_dt = local.localize(naive, is_dst=None)
    utc_dt= local_dt.astimezone (pytz.UTC)
    return utc_dt.strftime (DEFAULT_SERVER_DATETIME_FORMAT)

def get_label(self,cr,uid,field,context):
    labels = self.fields_get(cr, uid, allfields=[field], context=context)
    return labels[field]['string']    

def get_field_value(self,cr,uid,id,field,context):
    obj=self.browse(cr,uid,id,context)
    return obj[field] 

def getDateTimeInGivenFormat(date,inFormat,outFormat):
    if date==False or date==None:
        return ''
    obj= datetime.strptime(date,inFormat)     
    return obj.strftime(outFormat)    
    
def getSqlDate(date):
    return getDateTimeInGivenFormat(date,DEFAULT_LOCAL_DATE_FORMAT,DEFAULT_SERVER_DATE_FORMAT)


def get_authorized_users(self,cr,uid,context):
    users=[]
    group_ids = self.pool.get('res.groups').search(cr, uid, [('name','=', 'HR Manager')])
    if group_ids:
        group=self.pool.get('res.groups').browse(cr,uid,group_ids[0],context)
        for user in group.users:
            users.append(user.id)
            
    super_user=self.pool.get('res.users').browse(cr,uid,SUPERUSER_ID,context)
    if super_user.id not in users:
        users.append(super_user.id)
            
    return users


class hr_attendance_sheet(osv.osv):
    _name = 'hr.attendance_sheet'
    _order = 'name, employee_id, state desc'
    _columns = {
        'name': fields.date('Attendance Date', required=True, select=1,readonly=True, states={'waiting': [('readonly', False)]}),
        'sign_in': fields.datetime('Sign In', required=True,readonly=True, states={'waiting': [('readonly', False)]}),
        'sign_out': fields.datetime('Sign Out', required=True,readonly=True, states={'waiting': [('readonly', False)]}),
        'action_desc': fields.char('Note', size=256,readonly=True, states={'waiting': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', "Employee's Name", required=True, select=True,readonly=True, states={'waiting': [('readonly', False)]}),
        'total': fields.char('Total Time', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'late': fields.char('Late', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'short': fields.char('Short', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'ot': fields.char('OT', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'auth_ot': fields.char('Auth OT', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'shift': fields.char('Shift No', size=16,readonly=True, states={'waiting': [('readonly', False)]}),
        'state': fields.selection( [ ('waiting','Waiting for approval'), ('approved','Approved'),
                        ('rejected','Rejected')],'State' ,required=1, select=1),        
    }
    _defaults = {
        'state': 'waiting',
        'name': fields.date.context_today,
        'sign_in': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'sign_out': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S')
    }
        
    _sql_constraints = [
        ('name_uniq', 'unique (name,employee_id)',
            'Attendance for this employee and date already created!') ,
        ] 
           
    def default_get(self, cr, uid, fields, context=None):
        res = super(hr_attendance_sheet, self).default_get(cr, uid, fields, context=context)
        employee=self.pool.get('hr.employee').search(cr,uid,[('user_id','=',uid)])
        res.update({'employee_id':(employee[0] if employee else False)})
        return res
                    
    def _search(self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False, access_rights_uid=None):  
        authorized_users=get_authorized_users(self, cr, uid, context)        
        if uid not in authorized_users:
            employee=self.pool.get('hr.employee').search(cr,uid,[('user_id','=',uid)])
            args += [('employee_id', '=', employee[0] if employee else uid)]
        return super(hr_attendance_sheet, self)._search(cr, uid, args, offset, limit, order,
            context, count, access_rights_uid)     
                   
    def action_approve(self, cr, uid, ids, context=None):
        vals={'state':'approved'}
        return self.updateState(cr, uid, ids, vals, context)
        
    def action_reject(self, cr, uid, ids, context=None):
        vals={'state':'rejected'}
        return self.updateState(cr, uid, ids, vals, context)
            
    def action_edit(self, cr, uid, ids, context=None):
        vals={'state':'waiting'}
        return self.updateState(cr, uid, ids, vals, context)
                
    def updateState(self, cr, uid, ids,vals,context=None):
        this=self.browse(cr,uid,ids[0], context)
        data=self.pool.get('hr.attendance').search(cr,uid,[('day','=',this.name),
                        ('employee_id', '=', this.employee_id.id)])
        if data:
            self.pool.get('hr.attendance').write(cr,uid,data,vals,context)        
        return super(hr_attendance_sheet, self).write(cr, uid, ids, vals, context)    
                    
    def write(self, cr, uid, ids, vals, context=None):
        this=self.browse(cr,uid,ids[0], context)
        
        if vals.get('name', False) or vals.get('employee_id', False):
            raise osv.except_osv('Error', 'You can not change employee or attendance date!')  
        
        dayObj= datetime.strptime(this.name,DEFAULT_SERVER_DATE_FORMAT).date()     
        if vals.get('sign_in', False):
            signInObj=getDateFromDateTime(self,cr,vals['sign_in'],context)
            if dayObj!=signInObj:
                raise osv.except_osv('Error', 'You can not change date, you can change only time!')  
            
            data=self.pool.get('hr.attendance').search(cr,SUPERUSER_ID,[('day','=',this.name),
                            ('employee_id', '=', this.employee_id.id),('action','=','sign_in')])
            if data:
                self.pool.get('hr.attendance').write(cr,SUPERUSER_ID,data,{'name':vals['sign_in']})
            else:
                attendance={'name':vals['sign_in'], 'action':'sign_in', 'employee_id':this.employee_id.id}                
                self.pool.get('hr.attendance').create(cr,SUPERUSER_ID,attendance,context)

        if vals.get('sign_out', False):
            signOutObj=getDateFromDateTime(self,cr,vals['sign_out'],context)
            if dayObj!=signOutObj:
                raise osv.except_osv('Error', 'You can not change date, you can change only time!') 
                        
            data=self.pool.get('hr.attendance').search(cr,SUPERUSER_ID,[('day','=',this.name),
                    ('action','=','sign_out'),('employee_id', '=', this.employee_id.id)])
            if data:
                self.pool.get('hr.attendance').write(cr,SUPERUSER_ID,data,{'name':vals['sign_out']})
            else:
                attendance={'name':vals['sign_out'], 'action':'sign_out', 'employee_id':this.employee_id.id}                
                self.pool.get('hr.attendance').create(cr,SUPERUSER_ID,attendance,context)
                
        oldVal={}
        for key,value in vals.iteritems():
            oldVal[key]=this[key]
            
        ret=super(hr_attendance_sheet, self).write(cr, uid, ids, vals, context=context)
        self.generate_data_for_approval(cr, uid, ids[0], vals, oldVal, context)
        return ret

    def create(self, cr, uid, vals, context=None):
        oldVal={}
        dayObj= datetime.strptime(vals['name'],DEFAULT_SERVER_DATE_FORMAT).date() 
        if vals.get('sign_in', False):
            signInObj=getDateFromDateTime(self,cr,vals['sign_in'],context)
            
            if dayObj!=signInObj:
                raise osv.except_osv('Error', 'Attendance date and sign in date must be same!')              
        if vals.get('sign_out', False):
            signOutObj=getDateFromDateTime(self,cr,vals['sign_out'],context)
            
            if dayObj!=signOutObj:
                raise osv.except_osv('Error', 'Attendance date and sign out date must be same!')              
                    
        ret= super(hr_attendance_sheet, self).create(cr, uid, vals, context=context)
        
        if(vals.get('sign_in', False)):
            attendance={'name':vals['sign_in'], 'action':'sign_in', 'employee_id':vals['employee_id'],'state':vals['state']}
            self.pool.get('hr.attendance').create(cr,SUPERUSER_ID,attendance,context)
        
        if(vals.get('sign_out', False)):
            attendance={'name':vals['sign_out'], 'action':'sign_out', 'employee_id':vals['employee_id'],
                       'state':vals['state']}
            self.pool.get('hr.attendance').create(cr,SUPERUSER_ID,attendance,context)
        
        newVals={}
        for key,val in vals.iteritems():
            if val and key != 'employee_id' and key !='state':
               newVals[key]=val
        self.generate_data_for_approval(cr, uid, ret, newVals, oldVal, context)
        return ret
             
    def generate_data_for_approval(self, cr, uid, id,newVals, oldVals={}, context={}):
        this= self.browse(cr,uid,id,context)
        if this.state !='waiting':
            return False
        if not this.employee_id.parent_id:
            return False

        authorized_users=get_authorized_users(self, cr, uid, context)        
        if uid in authorized_users:
            return False
        
        modified_data={}
        newVal={}
        oldVal={}
        
        for key,value in newVals.iteritems():
            if key=='name':
                value=getDateTimeInGivenFormat(value,DEFAULT_SERVER_DATE_FORMAT,DEFAULT_LOCAL_DATE_FORMAT) 
            if key=='sign_in' or key=='sign_out':
                value=convertTimeInLocal(self,cr,value,context)  
            newVal[get_label(self,cr,uid,key,context)]=value
        
        for key,value in oldVals.iteritems():
            if key=='name':
                value=getDateTimeInGivenFormat(value,DEFAULT_SERVER_DATE_FORMAT,DEFAULT_LOCAL_DATE_FORMAT) 
            if key=='sign_in' or key=='sign_out':
                value=convertTimeInLocal(self,cr,value,context)  
            oldVal[get_label(self,cr,uid,key,context)]=value

        info= 'Changes in ' if oldVal else 'Created new '
        modified_data['data_detail']=str(newVals)
        modified_data['data']=info+'attendance for date %s' %(getDateTimeInGivenFormat(this.name, 
                                        DEFAULT_SERVER_DATE_FORMAT,DEFAULT_LOCAL_DATE_FORMAT ))
        modified_data['new_value']=str(newVal)
        modified_data['old_value']=str(oldVal)
        modified_data['name']=this.employee_id.name
        modified_data['model']='hr.attendance_sheet'
        modified_data['data_owner_id']=this.id
        modified_data['class_name']='hr_attendance_sheet'

        line_obj=self.pool.get('hr.transitional.data')
        manager_transitional_data_ids=[]
        manager_transitional_data_ids.append((4,line_obj.create(cr,SUPERUSER_ID,modified_data,context),False))
                                                 
        super(kts_hr_employee, self.pool.get('hr.employee')).write(cr, SUPERUSER_ID, [this.employee_id.parent_id.id], 
                    {'self_transitional_data_ids':manager_transitional_data_ids}, context=context)
        super(kts_hr_employee, self.pool.get('hr.employee')).write(cr, SUPERUSER_ID, [this.employee_id.id], 
                    {'manager_transitional_data_ids':manager_transitional_data_ids}, context=context)            
        return True           
         
hr_attendance_sheet()

class kts_hr_attendance(osv.osv):
    _inherit = "hr.attendance"
    _columns = {
        'state': fields.selection( [ ('waiting','Waiting for approval'), ('approved','Approved'),
                        ('rejected','Rejected')],'State' , select=1),        
    }    
    _defaults = {
        'state': 'waiting',
    }    

    def _altern_si_so(self, cr, uid, ids, context={}):
        this=self.browse(cr,SUPERUSER_ID,ids[0],context)
        data=self.search(cr,SUPERUSER_ID,[('day','=',getDateFromDateTime(self,cr,this.name,context,DEFAULT_LOCAL_DATETIME_FORMAT,False)),
                    ('action','=',this.action),('employee_id', '=', this.employee_id.id)])
        #if len(data)>0:
        #    return False
        return True    
    _constraints = [(_altern_si_so, 'Error: Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]
    
kts_hr_attendance()    


class hr_attendance_loader(osv.osv):
    _name = 'hr.attendance_loader'
    _columns = {
        'name': fields.char('File Path', size=256, required=1),
        'datas_fname': fields.char('File Path', size=256),
        'message': fields.text('Message', readonly=1),
        'datas': fields.binary("Attendance File", required=1,
            help="select attendance file which you want to upload."),
    }
    _defaults = {
        'name': '/home/ubuntu/Dropbox/ERP/HR/Daily_Attendance/daily_attendance.txt'
    }
    
    def write(self, cr, uid, ids, vals, context=None):
        vals.update({'message':False})
        return super(hr_attendance_loader, self).write(cr, uid, ids, vals, context)
        
    def create(self, cr, uid, vals, context=None):
        vals.update({'message':False})
        return super(hr_attendance_loader, self).create(cr, uid, vals, context=context)
            
    def default_get(self, cr, uid, fields, context=None):
        res = super(hr_attendance_loader, self).default_get(cr, uid, fields, context=context)
        scheduledActions=self.pool.get('ir.cron').search(cr,uid,[('model','=','hr.attendance_loader')])
        if scheduledActions:
            model=self.pool.get('ir.cron').browse(cr,uid,scheduledActions[0],context)
            res.update({'name':(eval(model.args)[0] if model.args else False)})
        return res
        
    def _write_attendance_file(self,datas):
        import os,sys,re,string,array
        curr_dir = os.path.dirname(os.path.realpath(__file__))    
        file_name= curr_dir+'/attendance.txt'
        fo = open(file_name, "w")
        if fo:
            import base64
            fo.write(base64.b64decode(datas))
            fo.close()        
        return file_name
            
    def button_attendance_upload(self, cr, uid, ids,context={}):
        this= self.browse(cr,uid,ids[0],context)
        file_name = self._write_attendance_file(this.datas);
        try:
            with open(file_name, 'rb') as f:
                f.close()
                self.upload_attendance_data(cr, uid, ids, file_name, context)
        except Exception, e:
            raise osv.except_osv('Error', 'Error in uploading attendance, please contact support: \"%s\" '%(str(e.message)+'\n\n'+ str(e.args)))
            #raise osv.except_osv('Error', 'file \"%s\" does not exits. Please check file path!'%this.name)
        return True  
                                  
    def upload_attendance_data(self, cr, uid, ids, file_path,context={}):
        
        errorList=[]
        errorRowList=[]
        errorSignInSignOutList=[]
        errorEmployeeList=[]
        errorCreateSheetList=[]
        
        attendance_date=''
        
        starts='<div><strong>'
        ends='</strong></div>'
        error_start='<div><span style="color:#0000ff;">'
        error_end=' </strong></span></div><div>'
        line_start='<div>'
        line_end='</div>'
        extra_line='<div>&nbsp;</div>'
        def getErrorLine(errList):
            return [str(i)+extra_line for i in errList]

        line1=[]
        import csv
        try:
            with open(file_path, 'rb') as f:
                reader = csv.reader(f, delimiter='|', quoting=csv.QUOTE_NONE)
                i=0
                for row in reader:
                    i=i+1
                    if i==1:
                        line1=row
                        continue
                    if i==2:
                        row = line1+row
                    try:
                        attendance_date=row[8]
                        vals={
                              'name':getSqlDate(row[8]),
                              'sign_in':row[26],'sign_out':row[27],'total':row[30],
                              'late':row[31], 'ot':row[33], 'action_desc':'Daily attendance',
                              'auth_ot':row[34], 'shift':row[25], 'state':'approved',
                              'short':row[32], 'employee_id':row[23]
                              }
                    except Exception, e:
                        row.append(('detailedError: %s'%(str(e))))
                        errorRowList.append({'Line No '+str(i):row})
                        continue
                        
                    try:
                        sign_hrs=' %s:%s:00'%(vals['sign_in'][:2],vals['sign_in'][2:])
                        vals['sign_in']=get_time_in_UTC(vals['name']+sign_hrs) 
                            
                        sign_hrs=' %s:%s:00'%(vals['sign_out'][:2],vals['sign_out'][2:])
                        vals['sign_out']=get_time_in_UTC(vals['name']+sign_hrs) 
                    except Exception, e:
                        row.append(('detailedError: %s'%(str(e))))
                        errorSignInSignOutList.append({'Line No '+str(i):row})
                        continue
                    
                    try:
                        employee=self.pool.get('hr.employee').search(cr,uid,[('employee_id','=',vals['employee_id'])])
                        vals['employee_id']=employee[0]
                    except Exception, e:
                        row.append(('detailedError: %s'%(str(e))))
                        errorEmployeeList.append({'Line No '+str(i):row})
                        continue
                    
                    try:
                        data=self.pool.get('hr.attendance_sheet').search(cr,uid,[('employee_id','=',vals['employee_id']),('name','=',vals['name'])])
                        if data:
                            errorCreateSheetList.append({'Line No '+str(i)+'(attendance for %s for date %s already exists)'%(row[24],row[8]):row})                   
                            continue    
                        self.pool.get('hr.attendance_sheet').create(cr,uid,vals,context)
                    except IntegrityError, e:
                        row.append(('detailedError: %s'%(str(e))))
                        errorCreateSheetList.append({'Line No '+str(i)+'(Major Error failed to create any attendance)'%(row[24],row[8]):row})
                        break                   
                    except Exception, e:
                        row.append(('detailedError: %s'%(str(e))))
                        errorCreateSheetList.append({'Line No '+str(i)+'(%s)'%(str(e)):row})                   
                        continue
            f.close()
        except Exception, e:
            errorList.append(starts+error_start+'Attendance file not found!'+error_end+ends+extra_line)
            errorList.append(starts+error_start+'Please keep daily attendance file at following location:'+ends+file_path+error_end)
                        
        i=0
        if errorRowList:
             i=i+1
             errorList.append(starts+error_start+str(i)+'. Error in reading following %d lines(Lines are not in correct format):'%len(errorRowList)+error_end+ends+extra_line)
             errorList=errorList+getErrorLine(errorRowList)
             
        if errorSignInSignOutList:
             i=i+1
             errorList.append(starts+error_start+str(i)+'. Error in reading sign-in and/or sign out time in following %d lines:\n\n'%len(errorSignInSignOutList)+error_end+ends+extra_line)
             errorList=errorList+getErrorLine(errorSignInSignOutList)
             
        if errorEmployeeList:
             i=i+1
             errorList.append(starts+error_start+str(i)+'. Error in reading employee information in following %d lines(Please check employee id):\n\n'%len(errorEmployeeList)+error_end+ends+extra_line)
             errorList=errorList+getErrorLine(errorEmployeeList)
                          
        if errorCreateSheetList:
             i=i+1
             errorList.append(starts+error_start+str(i)+'. Error in creating attendance sheet entry for following %d lines:\n\n'%len(errorCreateSheetList)+error_end+ends+extra_line)
             errorList=errorList+getErrorLine(errorCreateSheetList)
        
        stmt=''
        for o in errorList:
            stmt= stmt+o
        
        print stmt
        if not errorList:
            stmt=error_start+'Attendance successfully updated!'+error_end
     
        attendanceDate='Attendance Upload Notification For Date %s'%attendance_date
        mail=self.pool.get('general.email_notification')
     
        message = 'Attendance successfully updated for the date: %s'%attendance_date
        messageList = errorRowList+errorSignInSignOutList+errorEmployeeList+errorCreateSheetList
        if messageList:
            message='Following are the errors in uploading attendance for the date %s\n\n'%attendance_date
        j=0
        for i in messageList:
            message = message+(str(i)+'\n\n')
            j=j+1
            if j>3:
                message = message+'...............\n there are more errors, please refer mail for details'
                break

        super(hr_attendance_loader, self).write(cr, uid, ids, 
                                                {'message':message}, context)
        
        mail.send_system_hr_attendance_notification(cr,uid,attendanceDate,stmt,context)
        return True
                        
hr_attendance_loader()

