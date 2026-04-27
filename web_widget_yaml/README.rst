================
Web Widget YAML
================

.. image:: /web_widget_yaml/static/description/icon.png
   :alt: Web Widget YAML Logo
   :align: center
   :width: 200px

.. image:: https://img.shields.io/badge/license-%20%20GNU%20LGPLv3%20-green?style=plastic&logo=gnu
   :target: https://www.gnu.org/licenses/lgpl-3.0.txt
   :alt: License: LGPL-3

.. image:: https://img.shields.io/badge/github-repo-blue?logo=github
   :target: https://github.com/chrisking94/odoo_addons/tree/main/web_widget_yaml
   :alt: Github Repo

This module provides a dedicated YAML code editor widget for Odoo form views, 
extending the capabilities of the standard Ace Editor.

The standout feature of this addon is its **flexibility**: unlike the standard
Odoo Ace widget, this one allows developers to pass any configuration option
directly via the ``options`` attribute in the XML view.

Usage
=====

To apply the YAML editor to a field, use ``widget="yaml"`` in your XML view:

.. code-block:: xml

    <field name="my_yaml_config"
           widget="yaml"
           options="{'fontSize': 14, 'theme': 'ace/theme/monokai', 'minLines': 15}"/>

Advanced Configuration
======================

This widget supports all standard Ace Editor options. You can find a complete list of
supported configuration keys and their values in the `Official Ace Configuration Wiki <https://github.com/ajaxorg/ace/wiki/Configuring-Ace>`_.

Commonly used options include:

* ``theme``: Visual style (e.g., ``'ace/theme/monokai'``, ``'ace/theme/chrome'``).
* ``fontSize``: Text size in pixels (e.g., ``14``).
* ``minLines`` / ``maxLines``: Control editor height.
* ``showPrintMargin``: Show or hide the vertical guide line.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/chrisking94/odoo_addons/issues>`_.

Maintainer
==========

.. image:: https://avatars.githubusercontent.com/u/29966935
   :alt: Chris King Github Home
   :target: https://github.com/chrisking94
   :width: 80px

This module is maintained by Chris.
