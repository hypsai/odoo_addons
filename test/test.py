# -*- coding: utf-8 -*-
# @Time         : 19:42 2025/4/4
# @Author       : Chris
# @Description  :
# set server timezone in UTC before time module imported
import os.path

__import__('os').environ['TZ'] = 'UTC'

import odoo.cli
import sys

root = os.path.abspath(os.path.join(__file__, "../../"))
if len(sys.argv) < 3:
    raise Exception("Must specify version and name of target test addon！")
ver = sys.argv[1]
target = sys.argv[2]
del sys.argv[1:3]

sys.argv.append(f"--config={root}/test/odoo.conf")
sys.argv.append(f"--addons-path={root}")
sys.argv.append(f"--data-dir=C:/data/odoo_addons_v{ver}")
sys.argv.append(f"--database=odoo_addons_v{ver}")
# sys.argv.append(f"--init={target}")
# sys.argv.append(f"--update={target}")
sys.argv.append(f"--test-enable")
sys.argv.append(f"--stop-after-init")
sys.argv.append("--log-level=test")
sys.argv.append(f"--test-tags=/{target}")

if __name__ == "__main__":
    odoo.cli.command.main()
