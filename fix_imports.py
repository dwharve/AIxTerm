#!/usr/bin/env python3
"""Script to fix common linting issues."""

import os
import re
from pathlib import Path

def fix_unused_imports():
    """Fix unused imports in Python files."""
    
    # Common unused imports to remove
    unused_patterns = [
        r'^import json$',
        r'^import os$', 
        r'^import time$',
        r'^import asyncio$',
        r'^import pytest$',
        r'^from pathlib import Path$',
        r'^from typing import.*Optional.*$',
        r'^from typing import.*Union.*$',
        r'^from typing import.*List.*$',
        r'^from typing import.*Dict.*$',
        r'^from typing import.*Any.*$',
        r'^from typing import.*Callable.*$',
        r'^from typing import.*Tuple.*$',
        r'^from typing import.*Awaitable.*$',
        r'^from typing import.*cast.*$',
        r'^from unittest\.mock import.*MagicMock.*$',
        r'^from unittest\.mock import.*patch.*$',
        r'^from unittest\.mock import.*AsyncMock.*$',
        r'^from io import StringIO$',
    ]
    
    files_to_process = []
    
    # Find Python files with unused imports
    for root, dirs, files in os.walk('aixterm'):
        for file in files:
            if file.endswith('.py'):
                files_to_process.append(os.path.join(root, file))
                
    for root, dirs, files in os.walk('tests'):
        for file in files:
            if file.endswith('.py'):
                files_to_process.append(os.path.join(root, file))
    
    for file_path in files_to_process:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                # Skip lines that match unused import patterns
                skip_line = False
                for pattern in unused_patterns:
                    if re.match(pattern, line.strip()):
                        # Check if this import is actually used in the file
                        import_name = extract_import_name(line)
                        if import_name and not is_import_used(content, import_name, line):
                            skip_line = True
                            break
                
                if not skip_line:
                    new_lines.append(line)
            
            new_content = '\n'.join(new_lines)
            
            if new_content != original_content:
                with open(file_path, 'w') as f:
                    f.write(new_content)
                print(f"Fixed imports in: {file_path}")
                    
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

def extract_import_name(line):
    """Extract the imported name from an import line."""
    if line.strip().startswith('import '):
        return line.strip().split()[1].split('.')[0]
    elif ' import ' in line:
        parts = line.strip().split(' import ')
        if len(parts) > 1:
            imported = parts[1].split(',')[0].strip()
            return imported.split(' as ')[0].strip()
    return None

def is_import_used(content, import_name, import_line):
    """Check if an import is actually used in the file."""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == import_line.strip():
            continue  # Skip the import line itself
        if import_name in line:
            return True
    return False

if __name__ == '__main__':
    fix_unused_imports()
