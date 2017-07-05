import xmlrpclib
import socket
import os
import time
import datetime
import base64
import re
import logging
from openerp import models,api,fields,_
from openerp import tools, _
from openerp.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

def execute(connector, method, *args):
    res = False
    try:        
        res = getattr(connector,method)(*args)
    except socket.error,e:        
            raise e
    return res


class kts_database_utils(models.Model):
    _name='kts.database.utils'
    
    @api.model
    def _get_backup_flag(self):
        if self._context:
            flag=self._context.get('backup_flag')
            return flag
    @api.multi
    def get_db_list(self,host, port):
        self.ensure_one()
        _logger.debug("Host: " + host)
        _logger.debug("Port: " + port)
        uri = 'http://' + host + ':' + port
        conn = xmlrpclib.ServerProxy(uri + '/xmlrpc/db')
        db_list = execute(conn, 'list')
        return db_list

    @api.model
    def _get_db_name(self):
        attach_pool = self.pool.get("ir.logging")
        dbName = self._cr.dbname
        return dbName
    backup_flag=fields.Boolean('Backup DB',default=_get_backup_flag)
    restore_flag=fields.Boolean('Restore DB')
    name = fields.Char('Database', size=100, help='Database you want to schedule backups for',default=_get_db_name)
    new_name=fields.Char('New Database Name')
    bkp_dir = fields.Char('File Path', size=100, help='Absolute path for storing the backups')
    backup_type= fields.Selection([('zip', 'Zip'), ('dump', 'Dump')], 'Backup Type')
    note=fields.Text('Note',readonly=True)                
    backup_date=fields.Datetime('Backup Date',readonly=True)
                
    @api.multi
    def schedule_backup(self):
        self.ensure_one()
        for rec in self:
            host='localhost'
            port='8069'
            db_list = self.get_db_list('localhost','8069')
            if rec.name in db_list:
                try:
                    if not os.path.isdir(rec.bkp_dir):
                        os.makedirs(rec.bkp_dir)
                except:
                    raise
                bkp_file='%s_%s.%s' % (time.strftime('%d_%m_%Y_%H_%M_%S'),rec.name, rec.backup_type)
                file_path = os.path.join(rec.bkp_dir,bkp_file)
                uri = 'http://' + host + ':' + port
                conn = xmlrpclib.ServerProxy(uri + '/xmlrpc/db')
                bkp=''
                try:
                    bkp = execute(conn, 'dump', tools.config['admin_passwd'], rec.name, rec.backup_type)
                except:
                    _logger.debug("Couldn't backup database %s. Bad database administrator password for server running at http://%s:%s" %(rec.name, rec.host, rec.port))
                    continue
                bkp = base64.decodestring(bkp)
                fp = open(file_path,'wb')
                fp.write(bkp)
                fp.close()
            else:
                _logger.debug("database %s doesn't exist on http://%s:%s" %(rec.name, host, port))
            self.write({'note':'Database Backup is done successfully',
                        'backup_date':fields.Datetime.now()
                        })
            
        return True
    
    @api.multi
    def schedule_restore(self):
            self.ensure_one()
            host='localhost'
            port='8069'
            db_list = self.get_db_list('localhost','8069')
            if self.new_name not in db_list:
                new_file_name=self.new_name
                file_name=self.bkp_dir
                db_file = open(file_name, "rb")
                if not db_file:
                   db_file.close() 
                   return            
                data = base64.b64encode(db_file.read())
                uri = 'http://' + host + ':' + port
                conn = xmlrpclib.ServerProxy(uri + '/xmlrpc/db')
                try:
                   execute(conn, 'restore', tools.config['admin_passwd'],new_file_name,data)
                except:
                    _logger.debug("Couldn't restore database %s. Bad database administrator password for server running at http://%s:%s" %(rec.name, rec.host, rec.port))
                    
                
            else:
                _logger.debug("database %s already exist on http://%s:%s" %(self.new_name, host, port))
            self.write({'note':'Database Restore is done successfully',
                        'backup_date':fields.Datetime.now()
                        })
            return True
    
    
    