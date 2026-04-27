#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo Addons Release Script
Usage:
  python release.py <module> <version>     # Release a module
  python release.py --list [modules...]    # List current versions

Examples:
  python release.py mcp_base 1.0.6
  python release.py --list
  python release.py --list mcp_base oql
"""
import subprocess
import sys
import re
import shutil
from pathlib import Path


# Module to supported Odoo versions mapping
MODULE_VERSIONS = {
    "mcp_base": ['12.0', '13.0', '14.0', '15.0', '16.0', '17.0', '18.0', '19.0'],
    "oql": ['15.0'],
    "oql_web": ['15.0'],
    "web_widget_pill_icon": ['15.0'],
    "web_widget_yaml": ['15.0'],
}


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
    match = re.search(r"'version':\s*'([^']+)'", content)
    if match and match.group(1) == version:
        print(f"✅ Version is already {version}, no update needed")
        return False
    
    # Replace version
    new_content = re.sub(
        r"'version':\s*'[^']+'",
        f"'version': '{version}'",
        content
    )
    
    manifest_path.write_text(new_content, encoding='utf-8')
    print(f"✅ Version updated to: {version}")
    return True


def get_odoo_version(branch, main_version):
    """Get Odoo version from branch name and main version
    
    Example: branch='13.0', main_version='1.0.5' -> '13.0.1.0.5'
    """
    # Extract sub-version from main version (e.g., '1.0.5' -> '5')
    parts = main_version.split('.')
    if len(parts) >= 3:
        sub_version = parts[-1]  # Last part is the patch/sub version
    else:
        sub_version = '0'
    
    return f"{branch}.1.0.{sub_version}"


def get_current_version(module):
    """Get current version from manifest file"""
    manifest_path = get_manifest_path(module)
    
    if not manifest_path.exists():
        return None
    
    content = manifest_path.read_text(encoding='utf-8')
    match = re.search(r"'version':\s*'([^']+)'", content)
    
    if match:
        return match.group(1)
    return None


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
                branch_version = get_odoo_version(branch, version)
                print(f"  Branch {branch}: {branch_version}")
        else:
            print(f"\n{module}: ❌ Version not found")
    
    print("\n" + "=" * 60)


def main():
    # Handle --list option
    if '--list' in sys.argv or '-l' in sys.argv:
        # Get modules to list (all if none specified)
        args = [arg for arg in sys.argv[1:] if arg not in ['--list', '-l']]
        list_versions(args if args else None)
        return
    
    # Handle release mode
    if len(sys.argv) != 3:
        print("Usage:")
        print("  python release.py <module> <version>     # Release a module")
        print("  python release.py --list [modules...]    # List current versions")
        print("\nExamples:")
        print("  python release.py mcp_base 1.0.6")
        print("  python release.py --list")
        print("  python release.py --list mcp_base oql")
        sys.exit(1)
    
    module = sys.argv[1]
    new_version = sys.argv[2]
    
    # Validate module
    if module not in MODULE_VERSIONS:
        print(f"❌ Error: Unknown module '{module}'")
        print(f"Available modules: {', '.join(MODULE_VERSIONS.keys())}")
        sys.exit(1)
    
    print(f"\n🚀 Starting release {module} v{new_version}\n")
    
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
    odoo_branches = MODULE_VERSIONS[module]
    
    # Get the commit hash for this module's release
    if version_updated:
        release_commit = run_command("git rev-parse HEAD")
    else:
        # Find last commit that modified this module
        release_commit = run_command(f"git log -1 --format=%H -- {manifest_path}")
    
    for branch in odoo_branches:
        if branch == 'main':
            continue  # Skip main, already processed
            
        odoo_version = get_odoo_version(branch, new_version)
        print(f"\n{'='*60}")
        print(f"📋 Processing branch: {branch} (Odoo {odoo_version})")
        print('='*60)
        
        # Switch to branch
        run_command(f"git checkout {branch}")
        
        # Pull latest code
        run_command(f"git pull origin {branch}")
        
        # Force sync with main branch (main takes full precedence)
        print(f"→ Syncing {branch} with main (main takes full precedence)")
        run_command(f"git reset --hard main")
        
        # Update version to Odoo version format
        print(f"→ Updating version to {odoo_version}")
        version_updated = update_manifest_version(module, odoo_version)
        
        if version_updated:
            # Commit and push
            run_command(f"git add {manifest_path}")
            try:
                run_command(f'git commit -m "Update {module} version to {odoo_version} for Odoo {branch}"')
                print(f"✅ Version committed")
            except SystemExit:
                # No changes to commit, version already set
                print(f"⚠️ No changes to commit (version already {odoo_version})")
        else:
            print(f"⚠️ No changes to commit (version already {odoo_version})")
        
        # Clean up modules not supported in this branch
        print(f"→ Cleaning up unsupported modules in {branch}")
        all_modules = set(MODULE_VERSIONS.keys())
        supported_modules = set()
        
        # Find all modules supported in this branch
        for mod, branches in MODULE_VERSIONS.items():
            if branch in branches:
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
            try:
                run_command(f'git commit -m "chore: remove unsupported modules from {branch}"')
            except SystemExit:
                pass  # No changes
        
        run_command(f"git push origin {branch}")
        print(f"✅ Branch {branch} released successfully")
    
    # 6. Switch back to main
    print(f"\n{'='*60}")
    print("📋 Done! Switching back to main branch")
    print('='*60)
    run_command("git checkout main")
    
    print(f"\n🎉 Module {module} v{new_version} released successfully!")
    print(f"\nReleased branches:")
    for branch in odoo_branches:
        print(f"  - {branch}: {get_odoo_version(branch, new_version)}")
    print(f"  - main: {new_version}")
    print(f"\nCheck CI/CD status: https://github.com/chrisking94/odoo_addons/actions")


if __name__ == '__main__':
    main()
