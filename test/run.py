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
if len(sys.argv) < 2:
    raise Exception("Must specify odoo version！")
ver = sys.argv[1]
del sys.argv[1]

sys.argv.append(f"--addons-path={root}")
sys.argv.append(f"--config={root}/test/odoo.conf")
sys.argv.append(f"--data-dir=C:/data/odoo_addons_v{ver}")
sys.argv.append(f"--database=odoo_addons_v{ver}")
sys.argv.append(f"--dev=all")

if __name__ == "__main__":
    odoo.cli.main()
