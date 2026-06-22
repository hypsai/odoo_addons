# -*- coding: utf-8 -*-
# @Time         : 19:42 2025/4/4
# @Author       : Chris
# @Description  :
# set server timezone in UTC before time module imported
import json
import os.path

__import__('os').environ['TZ'] = 'UTC'

import odoo.cli
import sys

root = os.path.normpath(os.path.join(__file__, "../../"))
pro_addons = os.path.join(os.path.dirname(root), "odoo_addons_pro")
if len(sys.argv) < 3:
    raise Exception("Must specify version and name of target test addon！")
ver = sys.argv[1]
target = sys.argv[2]
del sys.argv[1:3]
with open(f"{root}/catalog.json", "r", encoding="utf-8") as f:
    catalog = json.load(f)
base_port = catalog["base_port"]
module2meta = catalog["modules"]
module_meta = module2meta.get(target)
if not module_meta:
    raise Exception(f"Addon `{target}` is not found in `catalog.json`.")
port = module_meta.get("port")
if port is None:
    raise Exception(f"`{port}` not configured for addon `{target}`.")
port += base_port

sys.argv.append(f"--addons-path={root},{pro_addons}")
sys.argv.append(f"--config={root}/test/odoo.conf")
sys.argv.append(f"--data-dir=C:/data/odoo{ver}_test_{target}")
sys.argv.append(f"--database=odoo{ver}_test_{target}")
sys.argv.append(f"--dev=all")
sys.argv.append(f"--init={target}")
sys.argv.append(f"--update={target}")
sys.argv.append(f"--http-port={port}")

if __name__ == "__main__":
    odoo.cli.command.main()
