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


def get_branch_version(branch, main_version):
    """Get version for a specific branch
    
    Format: {branch}.{main_version}
    Example: branch='15.0', main_version='1.1.0' -> '15.0.1.1.0'
    For main branch, return main_version as-is
    """
    if branch == 'main':
        return main_version
    return f"{branch}.{main_version}"


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
        
        # Update version to branch format
        print(f"→ Updating version to {branch_version}")
        version_updated = update_manifest_version(module, branch_version)
        
        if version_updated or has_cleanup:
            # Commit all changes together with meaningful message
            run_command(f"git add {manifest_path}")
            if has_cleanup:
                run_command(f"git add -A")
            
            commit_msg = f"Release {module} v{new_version} for Odoo {branch}"
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
    for branch in odoo_branches:
        branch_ver = get_branch_version(branch, new_version)
        print(f"  - {branch}: {branch_ver}")
    
    # 7. Trigger CI/CD
    print(f"\n{'='*60}")
    print("📋 Step 7: CI/CD will be triggered automatically")
    print('='*60)
    print(f"\nGitHub Actions will automatically test the following modules on each branch:")
    for branch in odoo_branches:
        # Find all modules supported in this branch
        branch_modules = [mod for mod, branches in MODULE_VERSIONS.items() if branch in branches]
        print(f"  - {branch}: {', '.join(branch_modules)}")
    
    print(f"\nCheck CI/CD status: https://github.com/chrisking94/odoo_addons/actions")


if __name__ == '__main__':
    main()
