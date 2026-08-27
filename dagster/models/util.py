# -*- coding: utf-8 -*-
# Helpers for the generic dagster plugin.
import logging

from odoo import models

_logger = logging.getLogger(__name__)


def get_dagster_client(self: models.Model):
    """Return a Dagster client for submitting job executions.

    Extension point: override / monkey-patch to provide a real client bound to
    your Dagster deployment. Returns None by default, making run/call no-ops.
    """
    return None
