from datetime import datetime
from openerp import models, fields, api,_
from dateutil.relativedelta import relativedelta
import openerp.addons.decimal_precision as dp
from openerp import exceptions, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class account_invoice_tdscal(models.Model):
    _inherit='account.invoice'
    tds_account=fields.Many2one('account.tds', 'TDS Account', readonly=True, states={'draft': [('readonly', False)]},)
    tds_charges= fields.Float('TDS charges', readonly=True, states={'draft': [('readonly', False)]},)            
    tds_charges_type= fields.Selection([('fixed','Fixed'), ('variable','Percentage'),('nil','Nil')], 'TDS Charges Type', readonly=True, states={'draft': [('readonly', False)]})
    tds_amount = fields.Monetary('TDS',digits=dp.get_precision('account'), compute='_compute_amount')
    
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id','tds_charges','tds_charges_type','tds_amount')
    def _compute_amount(self):
        res = super(account_invoice_tdscal, self)._compute_amount()    
        if self.tds_charges_type=='variable': 
            amount = self.amount_untaxed
            digits=2
            if self.tds_account.precision:
                digits=self.tds_account.precision.digits
            self.tds_amount = round(amount*self.tds_account.perc/100.0,digits)
               
        elif self.tds_charges_type=='fixed': 
             self.tds_amount=self.tds_charges
    
    
    @api.model
    def tds_line_get(self):
        res = []
        if self.tds_amount > 0.0:
            res.append({
                    'invoice_id': self.id,
                    'type': 'src',
                    'name': self.tds_account.name,
                    'price_unit': self.tds_amount,
                    'quantity': 1,
                    'price': (-1)*self.tds_amount,
                    'account_id': self.tds_account.tds_account.id,
                    'account_analytic_id': False,
                })
        return res
    
    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml =  inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()
            iml += inv.tds_line_get()
            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.with_context(currency_id=inv.currency_id.id).compute(total, date_invoice)[0]
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)

            date = inv.date or date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['dont_create_taxes'] = True
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True
 
    
class account_tds(models.Model):
    _name = "account.tds"
    name= fields.Char('Name', size=256, select=True)
    tds_account=fields.Many2one('account.account', 'TDS Account')
    precision=fields.Many2one('decimal.precision', 'Precision')
    active= fields.Boolean('Active',default=True) 
    perc = fields.Float('Percentage',default=0.0)
    