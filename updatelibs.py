#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update addon libraries from requirements.txt files.

This script scans all addon directories for requirements.txt files and installs
dependencies into each addon's libs directory using pip install -t.

Usage:
    python updatelibs.py [addon_paths...]
    
If no addon paths are provided, it will scan the current directory for addons.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional


def find_addons(base_path: Path) -> List[Path]:
    """
    Find all addon directories that contain __manifest__.py file.
    
    Args:
        base_path: Base directory to search for addons
        
    Returns:
        List of addon directory paths
    """
    addons = []
    for item in base_path.iterdir():
        if item.is_dir() and (item / '__manifest__.py').exists():
            addons.append(item)
    return addons


def clean_dist_info(target_dir: Path) -> None:
    """
    Remove .dist-info, .egg-info, and __pyinstaller directories from target directory.
    
    Args:
        target_dir: Directory to clean
    """
    import shutil
    for item in target_dir.iterdir():
        if item.is_dir() and (item.name.endswith('.dist-info') or 
                              item.name.endswith('.egg-info') or
                              item.name == '__pyinstaller'):
            shutil.rmtree(item)
            print(f"  Cleaned: {item.name}")


def clean_pycache_and_pyinstaller(addon_path: Path) -> None:
    """
    Remove __pycache__, __pyinstaller, and bin directories from addon.
    
    Args:
        addon_path: Path to the addon directory
    """
    import shutil
    # Clean __pycache__ directories
    for pycache_dir in addon_path.rglob('__pycache__'):
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)
            print(f"  Cleaned: {pycache_dir.relative_to(addon_path)}")
    
    # Clean __pyinstaller directories
    for pyinstaller_dir in addon_path.rglob('__pyinstaller'):
        if pyinstaller_dir.is_dir():
            shutil.rmtree(pyinstaller_dir)
            print(f"  Cleaned: {pyinstaller_dir.relative_to(addon_path)}")
    
    # Clean bin directories (typically contain example scripts)
    for bin_dir in addon_path.rglob('bin'):
        if bin_dir.is_dir() and bin_dir.parent.name == 'libs':
            shutil.rmtree(bin_dir)
            print(f"  Cleaned: {bin_dir.relative_to(addon_path)}")


def git_commit_changes(addon_path: Path, message: Optional[str] = None) -> bool:
    """
    Git add and commit changes in addon directory.
    
    Args:
        addon_path: Path to the addon directory
        message: Custom commit message (optional)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if directory is a git repository
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=str(addon_path),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  ⊘ Not a git repository: {addon_path.name}")
            return True
        
        # Git add all changes
        subprocess.run(
            ['git', 'add', '.'],
            cwd=str(addon_path),
            capture_output=True,
            check=True
        )
        
        # Check if there are staged changes
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=str(addon_path),
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"  ⊘ No changes to commit in {addon_path.name}")
            return True
        
        # Git commit
        commit_msg = message or f"Update libs for {addon_path.name}"
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=str(addon_path),
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"  ✓ Committed changes in {addon_path.name}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Git commit failed for {addon_path.name}: {e.stderr}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error during git commit for {addon_path.name}: {str(e)}")
        return False


def install_requirements(addon_path: Path, target_dir: Optional[Path] = None, 
                        trusted_host: Optional[str] = None, clean: bool = True,
                        auto_commit: bool = False) -> bool:
    """
    Install dependencies from requirements.txt into addon's libs directory.
    
    Args:
        addon_path: Path to the addon directory
        target_dir: Target directory for installation (defaults to addon_path/libs)
        trusted_host: Trusted host for pip (e.g., 'pypi.org')
        clean: Whether to remove .dist-info, .egg-info, and __pyinstaller directories after installation
        auto_commit: Whether to automatically git commit changes
        
    Returns:
        True if successful, False otherwise
    """
    requirements_file = addon_path / 'requirements.txt'
    
    # Check if requirements.txt exists
    if not requirements_file.exists():
        print(f"⊘ No requirements.txt found in {addon_path.name}")
        return True
    
    # Check if requirements.txt is empty
    if requirements_file.stat().st_size == 0:
        print(f"⊘ Empty requirements.txt in {addon_path.name}")
        return True
    
    # Set target directory
    if target_dir is None:
        target_dir = addon_path / 'libs'
    
    # Create libs directory if it doesn't exist
    target_dir.mkdir(exist_ok=True)
    
    print(f"→ Installing dependencies for {addon_path.name}...")
    print(f"  Requirements: {requirements_file}")
    print(f"  Target: {target_dir}")
    
    try:
        # Run pip install command
        cmd = [
            sys.executable, '-m', 'pip', 'install',
            '-r', str(requirements_file),
            '-t', str(target_dir),
            '--upgrade',
            '--no-cache-dir'
        ]
        
        # Add trusted host if specified
        if trusted_host:
            cmd.extend(['--trusted-host', trusted_host])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Clean up dist-info directories if requested
        if clean:
            clean_dist_info(target_dir)
        
        # Clean __pycache__ and __pyinstaller directories
        clean_pycache_and_pyinstaller(addon_path)
        
        # Auto commit if requested
        if auto_commit:
            git_commit_changes(addon_path)
        
        print(f"✓ Successfully installed dependencies for {addon_path.name}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies for {addon_path.name}")
        print(f"  Error: {e.stderr}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error for {addon_path.name}: {str(e)}")
        return False


def main():
    """Main function to process all addons."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Update addon libraries from requirements.txt files.'
    )
    parser.add_argument(
        'addons',
        nargs='*',
        help='Addon paths to process (default: auto-detect in current directory)'
    )
    parser.add_argument(
        '--trusted-host',
        help='Trusted host for pip (e.g., pypi.org)'
    )
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='Do not remove .dist-info and .egg-info directories'
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        help='Automatically git add and commit changes'
    )
    parser.add_argument(
        '--commit-message',
        help='Custom git commit message'
    )
    
    args = parser.parse_args()
    
    # Determine base path
    if args.addons:
        # Use provided addon paths
        addon_paths = [Path(arg).resolve() for arg in args.addons]
        # Filter out non-existent paths
        valid_paths = []
        for path in addon_paths:
            if path.exists():
                valid_paths.append(path)
            else:
                print(f"⚠ Warning: Path does not exist: {path}")
        addon_paths = valid_paths
    else:
        # Auto-detect addons in current directory
        base_path = Path(__file__).parent.resolve()
        addon_paths = find_addons(base_path)
        print(f"Found {len(addon_paths)} addon(s) in {base_path}")
    
    if not addon_paths:
        print("No addons to process.")
        return
    
    # Process each addon
    success_count = 0
    fail_count = 0
    
    for addon_path in addon_paths:
        if install_requirements(addon_path, trusted_host=args.trusted_host, 
                               clean=not args.no_clean, auto_commit=args.commit):
            success_count += 1
        else:
            fail_count += 1
    
    # Print summary
    print("\n" + "="*60)
    print(f"Summary: {success_count} succeeded, {fail_count} failed")
    print("="*60)
    
    if fail_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
