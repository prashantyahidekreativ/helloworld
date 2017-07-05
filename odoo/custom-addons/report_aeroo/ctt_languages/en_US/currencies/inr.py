#!/usr/bin/python
# -*- coding: utf8 -*-

from openerp.addons.report_aeroo.ctt_objects import ctt_currency
class inr(ctt_currency):
    def _init_currency(self):
        self.language = u'en_US'
        self.code = u'INR'
        self.fractions = 100
        self.cur_singular = u' rupee'
        self.cur_plural = u' rupees'
        self.frc_singular = u' paisa'
        self.frc_plural = u' paise'
        # grammatical genders: f - feminine, m - masculine, n -neuter
        self.cur_gram_gender = 'm'
        self.frc_gram_gender = 'm'
    
inr()
