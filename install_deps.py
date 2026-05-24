#!/usr/bin/env python3
"""
Auto-install Odoo addon dependencies for CI/CD testing.

Reads each module's __manifest__.py, finds 'depends' entries that are NOT:
  1. Core Odoo built-in modules (always available)
  2. Already present in the repo

For missing dependencies, downloads them from configured sources:
  - Git repositories (recommended, most reliable)
  - Direct zip URLs (e.g. Odoo App Store download links)

Configuration is read from external_deps.json in the repo root.
"""

import json
import os
import re
import subprocess
import sys
import io
import zipfile
from pathlib import Path

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen


# Core Odoo modules — always available in any Odoo installation.
# Extracted from odoo/addons/ shipped with official Docker images.
CORE_MODULES = {
    'account', 'account_accountant', 'account_edi', 'account_edi_ubl_bis3',
    'account_invoice_extract', 'account_payment', 'account_peppol',
    'analytic', 'approvals', 'attachment_indexation', 'auth_ldap',
    'auth_oauth', 'auth_password_policy', 'auth_signup', 'auth_totp',
    'barcodes', 'base', 'base_automation', 'base_geolocalize',
    'base_iban', 'base_import', 'base_import_module', 'base_setup',
    'board', 'bus', 'calendar', 'contacts', 'crm', 'data_merge',
    'delivery', 'digest', 'documents', 'event', 'event_booth',
    'event_sale', 'fetchmail', 'fleet', 'gamification', 'google_calendar',
    'google_drive', 'google_gmail', 'google_spreadsheet', 'helpdesk',
    'hr', 'hr_appraisal', 'hr_attendance', 'hr_contract',
    'hr_expense', 'hr_holidays', 'hr_recruitment', 'hr_skills',
    'http_routing', 'iap', 'im_livechat', 'l10n_generic_coa', 'link_tracker',
    'loyalty', 'lunch', 'mail', 'mail_bot', 'maintenance',
    'manufacturing', 'mass_mailing', 'mass_mailing_crm',
    'mass_mailing_event', 'mass_mailing_sale', 'microsoft_calendar',
    'microsoft_outlook', 'mrp', 'mrp_subcontracting', 'note', 'pad',
    'payment', 'phone_validation', 'planning', 'point_of_sale',
    'portal', 'pos_adyen', 'pos_discount', 'pos_loyalty', 'pos_mercury',
    'pos_restaurant', 'pos_sale', 'pos_six', 'pos_stripe', 'privacy_lookup',
    'product', 'project', 'purchase', 'repair', 'resource', 'sale',
    'sale_loyalty', 'sale_management', 'sale_project', 'sales_team',
    'sign', 'sms', 'snailmail', 'social', 'spreadsheet',
    'spreadsheet_dashboard', 'stock', 'survey', 'test_access_rights',
    'test_action_bindings', 'test_assets_bundle', 'test_base_automation',
    'test_converter', 'test_exceptions', 'test_impex', 'test_limits',
    'test_mail', 'test_mass_mailing', 'test_new_api', 'test_performance',
    'test_populate', 'test_read_group', 'test_rpc', 'test_search_panel',
    'test_timer', 'test_translation_import', 'test_web_cohort',
    'test_web_grid', 'test_web_studio', 'test_xlsx_export',
    'timesheet_grid', 'transifex', 'uom', 'utm', 'web', 'web_editor',
    'web_unsplash', 'web_studio', 'web_tour', 'website', 'website_blog',
    'website_crm', 'website_event', 'website_forum', 'website_hr',
    'website_links', 'website_livechat', 'website_mail_group',
    'website_mass_mailing', 'website_partner', 'website_sale',
    'website_slides', 'website_sms',
}


def read_manifest(module_path):
    """Read 'depends' and 'version' from __manifest__.py"""
    manifest = Path(module_path) / '__manifest__.py'
    if not manifest.exists():
        return []

    content = manifest.read_text(encoding='utf-8')

    match = re.search(r"""['"]depends['"]\s*:\s*\[(.*?)\]""", content, re.DOTALL)
    if not match:
        return []

    raw = match.group(1)
    deps = [
        d.strip().strip("'\"")
        for d in raw.split(',')
        if d.strip() and not d.strip().startswith('#')
    ]
    return deps


def get_repo_modules(repo_path):
    """Return all valid Odoo module names found in repo_path."""
    modules = set()
    for d in Path(repo_path).iterdir():
        if d.is_dir() and (d / '__manifest__.py').exists():
            modules.add(d.name)
    return modules


def load_deps_config():
    """Load external dependencies from external_deps.json"""
    config_path = Path('external_deps.json')
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def clone_git(name, config, target_dir):
    """Git-clone a dependency into target_dir."""
    repo = config['repo']
    branch = config.get('branch', config.get('version', 'main'))
    dest = Path(target_dir) / name

    if dest.exists():
        print(f"  [git] {name} already exists → skip")
        return True

    cmd = ['git', 'clone', '--depth', '1', '--branch', branch, repo, str(dest)]
    print(f"  [git] cloning {repo} @ {branch}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [git] FAILED: {result.stderr.strip()}")
        return False
    return True


def download_zip(name, url, target_dir):
    """Download and extract a zip into target_dir."""
    dest = Path(target_dir) / name
    if dest.exists():
        print(f"  [zip] {name} already exists → skip")
        return True

    print(f"  [zip] downloading {name} from {url}")
    try:
        req = Request(url, headers={'User-Agent': 'odoo-ci/1.0'})
        with urlopen(req, timeout=60) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(str(dest))
        print(f"  [zip] {name} extracted")
        return True
    except Exception as exc:
        print(f"  [zip] FAILED: {exc}")
        return False


def download_app_store(name, odoo_version, target_dir):
    """Attempt Odoo App Store download (best-effort, may need auth)."""
    dest = Path(target_dir) / name
    if dest.exists():
        print(f"  [app-store] {name} already exists → skip")
        return True

    url = f"https://apps.odoo.com/apps/modules/{odoo_version}/{name}/"
    print(f"  [app-store] trying {url}")

    try:
        req = Request(url, headers={'User-Agent': 'odoo-ci/1.0'})
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # Look for a download link in the page
        match = re.search(r'href="([^"]*download[^"]*\.zip[^"]*)"', html)
        if not match:
            match = re.search(r'href="([^"]*\.zip[^"]*)"', html)

        if match:
            dl = match.group(1)
            if not dl.startswith('http'):
                dl = f"https://apps.odoo.com{dl}"
            return download_zip(name, dl, target_dir)

        print(f"  [app-store] no download link found (maybe needs login)")
        return False
    except Exception as exc:
        print(f"  [app-store] FAILED: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def install_missing_deps(module, odoo_version, addons_path='.'):
    """Find and install missing dependencies for *module*.

    Returns (installed, failed) lists.
    """
    manifest_deps = read_manifest(module)
    if not manifest_deps:
        # No depends array — nothing to do
        return [], []

    repo_modules = get_repo_modules('.')
    deps_config = load_deps_config()

    missing = []
    for dep in manifest_deps:
        if dep in CORE_MODULES:
            continue
        if dep in repo_modules:
            continue
        if Path(addons_path, dep).exists() and (Path(addons_path, dep) / '__manifest__.py').exists():
            continue
        missing.append(dep)

    if not missing:
        return [], []

    print(f"\n📦 Module '{module}' has external dependencies: {', '.join(missing)}")

    installed = []
    failed = []

    for dep in missing:
        if dep in deps_config:
            cfg = deps_config[dep]
            kind = cfg.get('type', 'git')

            if kind == 'git':
                ok = clone_git(dep, cfg, addons_path)
            elif kind == 'url':
                ok = download_zip(dep, cfg['url'], addons_path)
            elif kind == 'app_store':
                ok = download_app_store(dep, cfg.get('version', odoo_version), addons_path)
            else:
                print(f"  ⚠ unknown type '{kind}' for {dep}")
                failed.append(dep)
                continue

            if ok:
                installed.append(dep)
            else:
                failed.append(dep)
        else:
            # No config entry — try App Store as a fallback
            print(f"  ⚠ {dep}: no entry in external_deps.json, trying Odoo App Store…")
            if download_app_store(dep, odoo_version, addons_path):
                installed.append(dep)
            else:
                failed.append(dep)

    if installed:
        print(f"  ✅ installed: {', '.join(installed)}")
    if failed:
        print(f"  ❌ failed: {', '.join(failed)}")
        print(f"  → Add them to external_deps.json, e.g.:")
        for dep in failed:
            print(f'    "{dep}": {{"type": "git", "repo": "https://github.com/USER/{dep}.git", "branch": "{odoo_version}"}},')

    return installed, failed


if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser(description='Install missing Odoo addon dependencies')
    p.add_argument('module', help='Module to check dependencies for')
    p.add_argument('--odoo-version', default=os.environ.get('ODOO_VERSION', '17.0'),
                   help='Odoo version (for App Store fallback)')
    p.add_argument('--addons-path', default='.',
                   help='Where to place downloaded deps')
    args = p.parse_args()

    _, failed = install_missing_deps(args.module, args.odoo_version, args.addons_path)
    if failed:
        sys.exit(1)
    sys.exit(0)
