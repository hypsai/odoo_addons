.. image:: /attached_field/static/description/icon.png
   :alt: Attached Field Logo
   :align: center
   :width: 200px

=================
Attached Field
=================

**One decorator.  Fields appear on the target model automatically — with DB
migration, view injection, and delegated compute/inverse.**

.. code-block:: python

    from odoo.addons.attached_field import attached

    @attached(
        picked=fields.Boolean("Picked", compute="_entity_compute_picked", inverse="_entity_inverse_picked"),
        kind=fields.Selection([("customer","Customer"),("supplier","Supplier")], "Kind",
                              compute="_entity_compute_kind", inverse="_entity_inverse_kind",
                              view={"widget": "radio"}),
    )
    def action_pick_records(self):
        return {
            'name': "Entities", 'type': 'ir.actions.act_window',
            'res_model': self.model_id.model, 'view_mode': 'tree,form',
            'target': 'current', 'context': self.env.context,
        }

Usage
=====

1. Decorate any action method that returns a view action dict with ``@attached``.
2. Implement compute / inverse methods **on the invoker model**.  They receive
   wrapped target records — user-defined field names work directly::

       def _entity_compute_picked(self, recs):
           for rec in recs:
               rec.picked = rec.id in picked_set

3. Call the action — fields are injected and the DB is migrated on-the-fly.

Field Naming
============

``<invoker_table>_<action_method>_<user_field_name>``

Example: ``attached_field_demo_set_action_pick_records_picked``.

View Injection
==============

- **Form** — floating panel (upper-right) with label | value per field.
- **Tree** — columns appended at the end.

``view={}`` — pass arbitrary ``<field/>`` attributes::

    fields.Char(..., view={"widget": "text", "class": "oe_inline"})

Maintainer
==========

.. image:: https://avatars.githubusercontent.com/u/288936625
   :alt: Chris King Github Home
   :target: https://github.com/hypsai
   :width: 80px

This module is maintained by **Chris**.
