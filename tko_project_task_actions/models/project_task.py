# -*- encoding: utf-8 -*-
# © 2017 TKO <http://tko.tko-br.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, fields
from datetime import datetime
from  dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
import time
from odoo.exceptions import Warning


class ProjectTaskActions(models.Model):
    _name = 'project.task.action'

    name = fields.Char(string='Name', required=True)
    expected_duration = fields.Integer(u'Expected Time', default=1, required=True)
    expected_duration_unit = fields.Selection([('d', 'Day'), ('w', 'Week'), ('m', 'Month'), ('y', 'Year')],
                                              default='d', required=True, string=u'Expected Time Unit')
    done_filter_id = fields.Many2one('ir.filters', 'Done Filter')
    done_filter_warning_message = fields.Text("Done Warning Message")
    done_server_action_id = fields.Many2one('ir.actions.server', string='Done Server Action',
                                            help=u'This server action will be executed when Actions is set to done')
    cancel_filter_id = fields.Many2one('ir.filters', 'Cancel Filter')
    cancel_filter_warning_message = fields.Text("Cancel Warning Message")
    cancel_server_action_id = fields.Many2one('ir.actions.server', string='Cancel Server Action',
                                              help=u'This server action will be executed when Actions is set to cancel')


class ProjectTaskActionsLine(models.Model):
    _name = 'project.task.action.line'

    action_id = fields.Many2one('project.task.action', u'Actions')
    expected_date = fields.Date(u'Expected Date', compute='onchange_action', store=True)
    done_date = fields.Date(u'Done Date', readonly=True)
    task_id = fields.Many2one('project.task', 'Task')
    state = fields.Selection([('i', u'In Progress'), ('d', u'Done'), ('c', u'Cancelled')], default='i', required=True,
                             string='State')

    @api.model
    def _eval_context(self):
        """Returns a dictionary to use as evaluation context for
           ir.rule domains."""
        return {'user': self.env.user, 'time': time}

    @api.one
    @api.depends('action_id')
    def onchange_action(self):
        if self.action_id:
            days = weeks = months = years = 0
            if self.action_id.expected_duration_unit == 'd':
                days = self.action_id.expected_duration
            if self.action_id.expected_duration_unit == 'w':
                weeks = self.action_id.expected_duration
            if self.action_id.expected_duration_unit == 'm':
                months = self.action_id.expected_duration
            if self.action_id.expected_duration_unit == 'y':
                years = self.action_id.expected_duration
            self.expected_date = datetime.today() + relativedelta(years=years, months=months, weeks=weeks, days=days)

    # Validate action done filter
    def validate_action_done_filter(self):
        """

        Context must have active_id
        :return:
        """
        model_name = 'project.task'
        eval_context = self._eval_context()
        active_id = self.task_id.id
        if active_id and model_name:
            domain = self.action_id.done_filter_id.domain
            rule = expression.normalize_domain(safe_eval(domain, eval_context))
            Query = self.env[model_name].sudo()._where_calc(rule, active_test=False)
            from_clause, where_clause, where_clause_params = Query.get_sql()
            where_str = where_clause and (" WHERE %s" % where_clause) or ''
            query_str = 'SELECT id FROM ' + from_clause + where_str
            self._cr.execute(query_str, where_clause_params)
            result = self._cr.fetchall()
            if active_id in [id[0] for id in result]:
                return True
        return False

        # Validate action cancel filter
        def validate_action_cancel_filter(self):
            """

            Context must have active_id
            :return:
            """
            model_name = 'project.task'
            eval_context = self._eval_context()
            active_id = self.task_id.id
            if active_id and model_name:
                domain = self.action_id.cancel_filter_id.domain
                rule = expression.normalize_domain(safe_eval(domain, eval_context))
                Query = self.env[model_name].sudo()._where_calc(rule, active_test=False)
                from_clause, where_clause, where_clause_params = Query.get_sql()
                where_str = where_clause and (" WHERE %s" % where_clause) or ''
                query_str = 'SELECT id FROM ' + from_clause + where_str
                self._cr.execute(query_str, where_clause_params)
                result = self._cr.fetchall()
                if active_id in [id[0] for id in result]:
                    return True
            return False

    def set_done(self):
        if self.action_id.done_filter_id:
            # validate filter here
            if not self.validate_action_done_filter():
                raise Warning(self.action_id.done_filter_warning_message or "Warning message not set for done filter")
                # set to done and execute server action

        self.write({'state': 'd', 'done_date': fields.Date.today()})
        if self.action_id.done_server_action_id:
            new_context = dict(self.env.context)
            if 'active_id' not in new_context.keys():
                new_context.update({'active_id': self.id, 'active_model': 'project.task.action.line'})
            recs = self.action_id.done_server_action_id.with_context(new_context)
            recs.run()

    def set_cancel(self):
        if self.action_id.cancel_filter_id:
            # validate filter here
            if not self.validate_action_cancel_filter():
                raise Warning(
                    self.action_id.cancel_filter_warning_message or "Warning message not set for cancel filter")
        self.state = 'c'
        if self.action_id.cancel_server_action_id:
            self.action_id.cancel_server_action_id.run()


class ProjectTask(models.Model):
    _inherit = 'project.task'

    action_line_ids = fields.One2many('project.task.action.line', 'task_id', 'Actions')
