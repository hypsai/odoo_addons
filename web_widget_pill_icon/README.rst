====================
Web Widget Pill Icon
====================

.. image:: /web_widget_pill_icon/static/description/icon.png
   :alt: Web Widget YAML Logo
   :align: center
   :width: 200px

.. image:: https://img.shields.io/badge/license-%20%20GNU%20LGPLv3%20-green?style=plastic&logo=gnu
   :target: https://www.gnu.org/licenses/lgpl-3.0.txt
   :alt: License: LGPL-3

.. image:: https://img.shields.io/badge/github-repo-blue?logo=github
   :target: https://github.com/chrisking94/odoo_addons/tree/main/web_widget_pill_icon
   :alt: Github Repo

This module provides a highly flexible, **pure frontend** widget to transform any text, selection, or numeric field into a stylish "Pill" or "Badge" with dynamic icons and semantic colors.

The standout feature is its **decoupling from the backend**: you can configure icons and styles entirely within the XML view options, making your list and form views significantly more recognizable without touching Python code.

Key Features
============

* **Type Agnostic**: Works with ``Selection``, ``Char``, ``Integer``, ``Float``, and ``Many2one`` fields.
* **Always Readonly**: Designed as a visualization tool; it maintains its clean UI even when the form is in Edit mode.
* **Semantic Mapping**: Map specific database values to FontAwesome icons and CSS classes.
* **Smart Alignment**: Custom CSS fixes common Odoo "drifting" issues when clicking rows in List View.
* **Built-in Utility Classes**: Includes pre-defined styles like ``pill``, ``outline``, and soft semantic colors (``success``, ``danger``, etc.).

Usage
=====

To apply the widget, use ``widget="pill_icon"`` and provide a mapping in the ``options`` attribute:

.. code-block:: xml

    <field name="kind"
           widget="pill_icon"
           options="{
               'base': 'pill outline sm',
               'values': {
                   'create': 'fa-plus-circle success',
                   'update': 'fa-pencil warning',
                   'delete': 'fa-trash danger'
               }
           }""")/>>

Configuration Options
=====================

The widget accepts two main keys in the ``options`` dictionary:

1. **base** (String): Global CSS classes applied to the widget container.
    * ``pill``: Rounded corners and standard padding.
    * ``outline``: Transparent background with a colored border.
    * ``sm`` / ``lg``: Adjusts the scale of the pill.

2. **values** (Dictionary): A mapping where the **Key** is the field's raw value and the **Value** is a string containing:
    * **Icons**: FontAwesome class (e.g., ``fa-star``, ``fa-pencil``).
    * **Colors**: Semantic classes like ``success``, ``warning``, ``danger``, ``info``, ``primary``, or ``muted``.

CSS Utility Reference
=====================

This module includes optimized **"Soft UI"** colors:

.. list-table::
   :header-rows: 1

   * - Class
     - Background (Light)
     - Text Color
   * - ``success``
     - Soft Green
     - Dark Green
   * - ``warning``
     - Soft Yellow
     - Dark Gold
   * - ``danger``
     - Soft Red
     - Dark Red
   * - ``info``
     - Soft Blue
     - Dark Blue
   * - ``primary``
     - Soft Royal Blue
     - Dark Royal Blue
   * - ``muted``
     - Light Grey
     - Dark Grey

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/chrisking94/odoo_addons/issues>`_.

Maintainer
==========

.. image:: https://avatars.githubusercontent.com/u/29966935
   :alt: Chris King Github Home
   :target: https://github.com/chrisking94
   :width: 80px

This module is maintained by **Chris**.
