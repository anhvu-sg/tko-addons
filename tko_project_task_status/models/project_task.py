# -*- encoding: utf-8 -*-
# © 2017 TKO <http://tko.tko-br.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, fields


class ProjectTask(models.Model):
    _inherit = 'project.task'

    status = fields.Selection([('n', 'NEW'), ('ip', 'In Progress'), ('d', 'Done'),
                               ('c', 'Cancelled'), ('b', 'Blocked')], default='n', required=True, string='Status')
