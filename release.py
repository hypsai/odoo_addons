#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo Addons Release Script
Usage:
  python release.py <module> [version] [options]   # Release a module
  python release.py -l [modules...]                # List current versions

Options:
  --major            Bump major version (X.0.0)
  --minor            Bump minor version (x.Y.0)
  --patch            Bump patch version (x.y.Z) [default when no version is given]
  -b, --branch VER   Only release for specific branch(es), repeatable

Examples:
  python release.py mcp_base 1.0.6
  python release.py oql --minor -b 18.0 19.0
  python release.py oql                     # auto patch bump, all branches
  python release.py -l oql
"""
import argparse
import subprocess
import sys
import re
import shutil
import json
from pathlib import Path

# Load module configuration from JSON file
CONFIG_FILE = Path(__file__).parent / 'catalog.json'

def load_module_config():
    """Load module configuration from modules_config.json"""
    if not CONFIG_FILE.exists():
        print(f"❌ Error: Configuration file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Convert to MODULE_VERSIONS format for backward compatibility
    module_versions = {}
    for module_name, module_info in config['modules'].items():
        module_versions[module_name] = module_info['supported_versions']
    
    return module_versions

# Module to supported Odoo versions mapping (loaded from config)
MODULE_VERSIONS = load_module_config()


def get_manifest_path(module):
    """Get manifest file path for a module"""
    return Path(f'{module}/__manifest__.py')


def run_command(cmd, cwd=None):
    """Run command and return result"""
    print(f"→ {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def update_manifest_version(module, version):
    """Update version in manifest file"""
    manifest_path = get_manifest_path(module)
    
    if not manifest_path.exists():
        print(f"❌ Error: Manifest file not found: {manifest_path}")
        sys.exit(1)
    
    content = manifest_path.read_text(encoding='utf-8')
    
    # Check if version is already set
    match = re.search(r'[\'"]version[\'"]:\s*[\'"]([^\'"]+)[\'"]', content)
    if match and match.group(1) == version:
        print(f"✅ Version is already {version}, no update needed")
        return False
    
    # Replace version (support both single and double quotes, preserve original quote style)
    def replace_version(match):
        prefix = match.group(1)  # e.g., '"version": ' or "'version': "
        # Detect quote style from original content
        if '"' in prefix:
            return f'{prefix}"{version}"'
        else:
            return f"{prefix}'{version}'"
    
    new_content = re.sub(
        r'([\'"]version[\'"]:)\s*[\'"][^\'"]+[\'"]',
        replace_version,
        content
    )
    
    manifest_path.write_text(new_content, encoding='utf-8')
    print(f"✅ Version updated to: {version}")
    return True


def strip_odoo_prefix(version):
    """Strip detected Odoo major.minor prefix (e.g. '19.0') from version.

    Returns the bare version without Odoo prefix, or the original if no
    prefix is detected.  Safe: ``'1.5.13'`` stays ``'1.5.13'``.
    """
    parts = version.split('.')
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
        major = int(parts[0])
        if 8 <= major <= 99:  # plausible Odoo major version
            return '.'.join(parts[2:])
    return version


def get_branch_version(branch, main_version):
    """Get version for a specific branch

    ``main_version`` is expected to be a *bare* version (e.g. ``'1.5.13'``).
    If an Odoo prefix accidentally slips in, it is stripped automatically.

    Format: ``{branch}.{main_version}``

    Example: branch='15.0', main_version='1.5.13' -> '15.0.1.5.13'

    For main branch, return main_version as-is.
    """
    if branch == 'main':
        return main_version
    bare = strip_odoo_prefix(main_version)
    return f"{branch}.{bare}"


def get_current_version(module):
    """Get current version from manifest file"""
    manifest_path = get_manifest_path(module)
    
    if not manifest_path.exists():
        return None
    
    content = manifest_path.read_text(encoding='utf-8')
    match = re.search(r'[\'"]version[\'"]:\s*[\'"]([^\'"]+)[\'"]', content)
    
    if match:
        return match.group(1)
    return None


def bump_version(version, bump_type='patch'):
    """Auto-increment version number.

    Args:
        version: Current version string, e.g. '1.2.3' or '15.0.1.2.3'.
        bump_type: 'major', 'minor', or 'patch'.

    Returns:
        New version string.
    """
    parts = version.split('.')
    if len(parts) < 2:
        print(f"❌ Error: Cannot auto-bump version '{version}' (expected X.Y.Z)")
        sys.exit(1)

    # The last three components are treated as major.minor.patch.
    # Anything before that is a prefix (e.g. Odoo branch version '15.0').
    prefix = '.'.join(parts[:-3])
    seg = list(map(int, parts[-3:]))  # [major, minor, patch]

    if bump_type == 'major':
        seg[0] += 1
        seg[1] = seg[2] = 0
    elif bump_type == 'minor':
        seg[1] += 1
        seg[2] = 0
    else:  # patch
        seg[2] += 1

    bumped = '.'.join(map(str, seg))
    return f"{prefix}.{bumped}" if prefix else bumped


def list_versions(modules=None):
    """List current versions of modules"""
    if modules is None:
        modules = list(MODULE_VERSIONS.keys())
    
    print("\n📦 Current Module Versions")
    print("=" * 60)
    
    for module in modules:
        if module not in MODULE_VERSIONS:
            print(f"⚠️  Unknown module: {module}")
            continue
        
        version = get_current_version(module)
        odoo_versions = MODULE_VERSIONS[module]
        
        if version:
            print(f"\n{module}:")
            print(f"  Main version: {version}")
            print(f"  Supported Odoo versions: {', '.join(odoo_versions)}")
            
            # Show branch versions
            for branch in odoo_versions:
                branch_version = get_branch_version(branch, version)
                print(f"  Branch {branch}: {branch_version}")
        else:
            print(f"\n{module}: ❌ Version not found")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Odoo Addons Release Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python release.py mcp_base 1.0.6\n'
               '  python release.py oql --minor -b 18.0 19.0\n'
               '  python release.py oql                   # auto patch bump, all branches\n'
               '  python release.py -l oql',
    )
    # Positional args for release mode
    parser.add_argument('module', nargs='?',
                        help='Module to release')
    parser.add_argument('version', nargs='?',
                        help='Version number (omit to auto-increment)')

    # Bump type (mutually exclusive)
    bump_group = parser.add_mutually_exclusive_group()
    bump_group.add_argument('--major', action='store_true',
                            help='Bump major version (X.0.0)')
    bump_group.add_argument('--minor', action='store_true',
                            help='Bump minor version (x.Y.0)')
    bump_group.add_argument('--patch', action='store_true',
                            help='Bump patch version (x.y.Z) [default]')

    # Branch filter
    parser.add_argument('-b', '--branch', nargs='+', metavar='VER',
                        help='Only release for specific branch(es)')

    # List mode
    parser.add_argument('-l', '--list', nargs='*', metavar='MODULE',
                        dest='list_modules',
                        help='List current module versions')

    args = parser.parse_args()

    # ── List mode ────────────────────────────────────────────────────────────
    if args.list_modules is not None:
        modules = args.list_modules if args.list_modules else None
        list_versions(modules)
        return

    # ── Release mode ─────────────────────────────────────────────────────────
    if not args.module:
        parser.error('module is required for release mode')

    module = args.module
    if module not in MODULE_VERSIONS:
        print(f"❌ Error: Unknown module '{module}'")
        print(f"Available modules: {', '.join(MODULE_VERSIONS.keys())}")
        sys.exit(1)

    # Determine version
    if args.version:
        new_version = args.version
        bump_desc = ''
    else:
        current = get_current_version(module)
        if not current:
            print(f"❌ Error: Cannot find current version for '{module}'")
            sys.exit(1)
        bump_type = 'major' if args.major else ('minor' if args.minor else 'patch')
        new_version = bump_version(current, bump_type)
        bump_desc = f' (auto {bump_type}: {current} → {new_version})'

    print(f"\n🚀 Starting release {module} v{new_version}{bump_desc}\n")

    # Resolve which version branches to process
    all_branches = MODULE_VERSIONS[module]
    if args.branch:
        # Validate that requested branches are in the module's supported list
        for b in args.branch:
            if b not in all_branches and b != 'main':
                print(f"❌ Error: Branch '{b}' not in {module}'s supported "
                      f"versions: {all_branches}")
                sys.exit(1)
        target_branches = [b for b in args.branch if b != 'main']
    else:
        target_branches = all_branches

    # 0. Check workspace status
    print("📋 Step 0: Checking workspace status")
    status = run_command("git status --porcelain")
    if status:
        print("❌ Error: Workspace has uncommitted changes, please commit or stash first")
        print(status)
        sys.exit(1)
    print("✅ Workspace is clean")

    # 1. Switch to main branch
    print("\n📋 Step 1: Switching to main branch")
    run_command("git checkout main")

    # 2. Pull latest code
    print("\n📋 Step 2: Pulling latest code")
    run_command("git pull origin main")

    # 3. Update main branch version
    print(f"\n📋 Step 3: Updating main branch version to {new_version}")
    manifest_path = get_manifest_path(module)
    version_updated = update_manifest_version(module, new_version)

    if version_updated:
        # 4. Commit main branch
        print("\n📋 Step 4: Committing main branch")
        run_command(f"git add {manifest_path}")
        run_command(f'git commit -m "Release {module} version {new_version}"')
        run_command("git push origin main")
    else:
        print("⚠️ Main branch version unchanged, skipping commit")

    # 5. Merge to version branches and update versions
    # Get the commit hash for this module's release
    if version_updated:
        release_commit = run_command("git rev-parse HEAD")
    else:
        # Find last commit that modified this module
        release_commit = run_command(f"git log -1 --format=%H -- {manifest_path}")

    if not target_branches:
        print("\n⚠️ No version branches to process")

    for branch in target_branches:
        branch_version = get_branch_version(branch, new_version)
        print(f"\n{'='*60}")
        print(f"📋 Processing branch: {branch}")
        print('='*60)

        # Switch to branch
        run_command(f"git checkout {branch}")

        # Pull latest code
        run_command(f"git pull origin {branch}")

        # Force sync with main branch (main takes full precedence)
        print(f"→ Syncing {branch} with main (main takes full precedence)")
        run_command(f"git reset --hard main")

        # Clean up modules not supported in this branch BEFORE updating version
        print(f"→ Cleaning up unsupported modules in {branch}")
        all_modules = set(MODULE_VERSIONS.keys())
        supported_modules = set()

        # Find all modules supported in this branch
        for mod, versions in MODULE_VERSIONS.items():
            if branch in versions:
                supported_modules.add(mod)

        # Remove unsupported module directories
        has_cleanup = False
        for mod in (all_modules - supported_modules):
            mod_path = Path(mod)
            if mod_path.exists():
                print(f"   Removing {mod} (not supported in {branch})")
                shutil.rmtree(mod_path)
                has_cleanup = True

        if has_cleanup:
            run_command(f"git add -A")

        # Apply Odoo-version compatibility transforms via OCA odoo-module-migrate
        print(f"→ Running OCA module migrator for Odoo {branch}")
        has_migrated = False
        oldest = MODULE_VERSIONS[module][0]
        if oldest != branch:
            try:
                from odoo_module_migrate.migration import Migration
                migration = Migration(
                    str(Path(__file__).parent),   # directory
                    oldest,                        # init_version_name
                    branch,                        # target_version_name
                    module_names=[module],
                    format_patch=False,
                    commit_enabled=False,           # release.py handles commits
                    pre_commit=False,
                    remove_migration_folder=False,
                )
                migration.run()
                has_migrated = True
                print(f"   ✅ Migration {oldest}→{branch} completed")
            except ImportError:
                print(f"   ⚠️ odoo-module-migrator not installed, skipping transforms")
        else:
            print(f"   ℹ️ No migration needed ({oldest} == {branch})")

        # Update version to branch format
        print(f"→ Updating version to {branch_version}")
        branch_version_updated = update_manifest_version(module, branch_version)

        if branch_version_updated or has_cleanup or has_migrated:
            # Commit all changes together with meaningful message
            run_command(f"git add {manifest_path}")
            if has_cleanup or has_migrated:
                run_command(f"git add -A")

            commit_msg = f"Release {module} v{new_version} for Odoo {branch} [skip ci]"
            try:
                run_command(f'git commit -m "{commit_msg}"')
                print(f"✅ Changes committed: {commit_msg}")
            except SystemExit:
                # No changes to commit
                print(f"⚠️ No changes to commit")
        else:
            print(f"⚠️ No changes to commit (version already {branch_version})")

        # Force push because we used git reset --hard
        run_command(f"git push origin {branch} --force")
        print(f"✅ Branch {branch} released successfully")

    # 6. Switch back to main
    print(f"\n{'='*60}")
    print("📋 Done! Switching back to main branch")
    print('='*60)
    run_command("git checkout main")

    print(f"\n🎉 Module {module} v{new_version} released successfully!")
    print(f"\nReleased branches:")
    for branch in target_branches:
        branch_ver = get_branch_version(branch, new_version)
        print(f"  - {branch}: {branch_ver}")

    # 7. Trigger CI/CD
    print(f"\n{'='*60}")
    print("📋 Step 7: CI/CD will be triggered automatically")
    print('='*60)
    print(f"\nGitHub Actions will automatically test the following modules on each branch:")
    for branch in target_branches:
        # Find all modules supported in this branch
        branch_modules = [mod for mod, versions in MODULE_VERSIONS.items()
                          if branch in versions]
        print(f"  - {branch}: {', '.join(branch_modules)}")

    print(f"\nCheck CI/CD status: https://github.com/chrisking94/odoo_addons/actions")


if __name__ == '__main__':
    main()
