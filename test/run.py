# -*- coding: utf-8 -*-
# @Time         : 19:42 2025/4/4
# @Author       : Chris
# @Description  :
# set server timezone in UTC before time module imported
import os.path

__import__('os').environ['TZ'] = 'UTC'

import odoo
import sys

root = os.path.normpath(os.path.join(__file__, "../../"))

sys.argv.append(f"--addons-path={root}")
sys.argv.append(f"--config={root}/test/odoo.conf")

if __name__ == "__main__":
    odoo.cli.main()
