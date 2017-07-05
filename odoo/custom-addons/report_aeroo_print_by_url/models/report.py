# -*- coding: utf-8 -*-
#
#    Jamotion GmbH, Your Odoo implementation partner
#    Copyright (C) 2013-2015 Jamotion GmbH.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Created by renzo.meister on 03.03.2016.
#
from openerp import models, SUPERUSER_ID
from openerp.report import render_report
import logging

_logger = logging.getLogger(__name__)


class Report(models.Model):
    _inherit = 'report'

    def _get_report_from_name(self, cr, uid, report_name):
        """Get the first record of ir.actions.report.xml having the ``report_name`` as value for
        the field report_name.
        """
        report_obj = self.pool['ir.actions.report.xml']
        conditions = [('report_type', '=', 'aeroo'), ('report_name', '=', report_name)]
        idreport = report_obj.search(cr, uid, conditions)
        if idreport:
            return report_obj.browse(cr, uid, idreport[0])
        return super(Report, self)._get_report_from_name(cr, uid, report_name)

    def get_pdf(self, cr, uid, ids, report_name, html=None, data=None, context=None):

        if context is None:
            context = {}

        if data is None:
            data = {}

        report = self._get_report_from_name(cr, SUPERUSER_ID, report_name)
        if report.report_type == 'aeroo':
            data.update({
                'report_type': 'aeroo',
                'model': report.model,
            })

            pdf = render_report(cr, SUPERUSER_ID, ids, report_name, data, context)
            if pdf:
                return pdf[0]
            return False
        else:
            return super(Report, self).get_pdf(
                cr,
                uid,
                ids,
                report_name,
                html=html,
                data=data,
                context=context
            )
