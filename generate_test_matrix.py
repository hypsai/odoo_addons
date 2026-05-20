#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate GitHub Actions test matrix from modules_config.json
This script reads the module configuration and generates the appropriate
test matrix for the CI/CD workflow.
"""
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / 'catalog.json'

def generate_test_matrix():
    """Generate test matrix configuration for GitHub Actions"""
    
    if not CONFIG_FILE.exists():
        print(f"❌ Error: Configuration file not found: {CONFIG_FILE}")
        return None
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Group modules by Odoo version
    version_to_modules = {}
    postgres_versions = {
        '13.0': '12',
        '14.0': '12',
        '15.0': '15',
        '16.0': '15',
        '17.0': '15',
        '18.0': '15',
        '19.0': '15',
    }
    
    for module_name, module_info in config['modules'].items():
        for version in module_info['supported_versions']:
            if version not in version_to_modules:
                version_to_modules[version] = []
            version_to_modules[version].append(module_name)
    
    # Generate matrix entries
    matrix_entries = []
    for version in sorted(version_to_modules.keys(), key=lambda x: float(x)):
        modules = sorted(version_to_modules[version])
        modules_str = ','.join(modules)
        
        entry = {
            'odoo_version': version,
            'postgres_version': postgres_versions.get(version, '15'),
            'modules_to_test': modules_str,
            'test_db': f'test_{version.replace(".", "")}'
        }
        matrix_entries.append(entry)
    
    return matrix_entries

def print_yaml_config():
    """Print the YAML configuration for GitHub Actions"""
    matrix = generate_test_matrix()
    
    if not matrix:
        return
    
    print("      matrix:")
    print("        include:")
    
    for entry in matrix:
        print(f"          # Odoo {entry['odoo_version']} - {entry['modules_to_test'].replace(',', ', ')}")
        print(f"          - odoo_version: '{entry['odoo_version']}'")
        print(f"            postgres_version: '{entry['postgres_version']}'")
        print(f"            modules_to_test: '{entry['modules_to_test']}'")
        print(f"            test_db: '{entry['test_db']}'")
        print()

if __name__ == '__main__':
    print("# Auto-generated test matrix from modules_config.json")
    print("# Run this script to update .github/workflows/test.yml")
    print()
    print_yaml_config()
