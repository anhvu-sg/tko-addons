# -*- encoding: utf-8 -*-
# © 2017 TKO <http://tko.tko-br.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from datetime import datetime
from dateutil.relativedelta import *

from odoo.addons.base.ir.ir_cron import _intervalTypes
from odoo.http import request
from odoo.http import root
from odoo import fields, models, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class res_users(models.Model):
    _inherit = 'res.users'

    def _check_session_validity(self, db, uid, passwd):
        if not request:
            return
        now = fields.datetime.now()
        session = request.session

        if session.db and session.uid:
            session_obj = request.env['ir.sessions']
            cr = self.pool.cursor()
            # autocommit: our single update request will be performed atomically.
            # (In this way, there is no opportunity to have two transactions
            # interleaving their cr.execute()..cr.commit() calls and have one
            # of them rolled back due to a concurrent access.)
            cr.autocommit(True)
            session_ids = session_obj.search([('session_id', '=', session.sid),
                                              ('expiration_date', '>', now.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                                              ('logged_in', '=', True)], order='expiration_date asc')
            if session_ids:
                if request.httprequest.path[:5] == '/web/' or \
                                request.httprequest.path[:9] == '/im_chat/':
                    open_sessions = session_ids.read(['logged_in',
                                                      'date_login',
                                                      'session_seconds',
                                                      'expiration_date'])
                    for s in open_sessions:
                        seconds = s['session_seconds']
                        expiration_date = now + relativedelta(seconds=seconds)
                        session_duration = str(now - datetime.strptime(s['date_login'], DEFAULT_SERVER_DATETIME_FORMAT))
                        # write as superuser
                        session_obj.browse(s['id']).sudo().write(
                            {
                                'expiration_date': expiration_date,
                                'session_duration': session_duration,
                            })
                    cr.commit()
            else:
                session.logout(logout_type='to', keep_db=True)
            cr.close()
        return True

    @classmethod
    def check(cls, db, uid, passwd):
        res = super(res_users, cls).check(db, uid, passwd)
        cr = cls.pool.cursor()
        self = api.Environment(cr, uid, {})[cls._name]
        cr.commit()
        cr.close()
        self.browse(uid)._check_session_validity(db, uid, passwd)
        return res

    @api.depends('interval_number', 'interval_type', 'groups_id.interval_number', 'groups_id.interval_type')
    def _get_session_default_seconds(self):
        now = datetime.now()
        seconds = (now + _intervalTypes['weeks'](1) - now).total_seconds()
        for user in self:
            if user.interval_number and user.interval_type:
                u_seconds = (
                    now +
                    _intervalTypes[
                        user.interval_type](
                        user.interval_number) -
                    now).total_seconds()
                if u_seconds < seconds:
                    seconds = u_seconds
            else:
                # Get lowest session time
                for group in user.groups_id:
                    if group.interval_number and group.interval_type:
                        g_seconds = (
                            now +
                            _intervalTypes[
                                group.interval_type](
                                group.interval_number) -
                            now).total_seconds()
                        if g_seconds < seconds:
                            seconds = g_seconds
            user.session_default_seconds = seconds

    login_calendar_id = fields.Many2one('resource.calendar',
                                        'Allowed Login Calendar', company_dependent=True,
                                        help='The user will be only allowed to login in the calendar defined here.\nNOTE:The calendar defined here will overlap all defined in groups.')
    multiple_sessions_block = fields.Boolean('Block Multiple Sessions', company_dependent=True, default=False,
                                             help='Select this to prevent user to start more than one session.')
    interval_number = fields.Integer('Default Session Duration', company_dependent=True,
                                     help='This is the timeout for this user.\nNOTE: The timeout defined here will overlap all the timeouts defined in groups.')
    interval_type = fields.Selection([('minutes', 'Minutes'),
                                      ('hours', 'Hours'), ('work_days', 'Work Days'),
                                      ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
                                     'Interval Unit', company_dependent=True)
    session_default_seconds = fields.Integer(compute=_get_session_default_seconds,
                                             string='Session Seconds', )
    session_ids = fields.One2many('ir.sessions', 'user_id', 'User Sessions')
    ip = fields.Char(related='session_ids.ip', string='Latest ip adress')
