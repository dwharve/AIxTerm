#!/usr/bin/env python3
"""
More precise annotation finder that only looks for annotations in comments.
"""

import re
import os
from pathlib import Path
from collections import Counter

def find_annotations():
    """Find annotations only in comments."""
    annotations = []
    exclude_dirs = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'node_modules', 'dist', 'build', '.tox', '.mypy_cache', '.coverage', 'htmlcov', '.eggs', 'tmp'}
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if not (file.endswith('.py') or file.endswith('.md') or file.endswith('.sh') or file.endswith('.yml') or file.endswith('.yaml') or file in ['Makefile']):
                continue
                
            file_path = Path(root) / file
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(file_path.relative_to('.'))
                
                for i, line in enumerate(content.split('\n'), 1):
                    line_stripped = line.strip()
                    
                    # Skip empty lines
                    if not line_stripped:
                        continue
                    
                    # For Python files, look for comments starting with # or docstrings
                    if file.endswith('.py'):
                        # Look for comments that start with #
                        if line_stripped.startswith('#'):
                            matches = re.finditer(r'\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b:?\s*(.*)', line_stripped, re.IGNORECASE)
                            for match in matches:
                                annotation_type = match.group(1).upper()
                                comment_text = match.group(2).strip()[:100]
                                if comment_text:
                                    annotations.append({
                                        'file': rel_path,
                                        'line': str(i),
                                        'type': annotation_type,
                                        'text': comment_text
                                    })
                        # Also check for annotations in triple-quoted docstrings
                        elif '"""' in line or "'''" in line:
                            matches = re.finditer(r'\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b:?\s*(.*)', line, re.IGNORECASE)
                            for match in matches:
                                annotation_type = match.group(1).upper()
                                comment_text = match.group(2).strip()[:100]
                                if comment_text and not comment_text.startswith('"') and not comment_text.startswith("'"):
                                    annotations.append({
                                        'file': rel_path,
                                        'line': str(i),
                                        'type': annotation_type,
                                        'text': comment_text
                                    })
                    
                    # For Markdown files, look for annotations anywhere  
                    elif file.endswith('.md'):
                        matches = re.finditer(r'\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b:?\s*(.*)', line, re.IGNORECASE)
                        for match in matches:
                            annotation_type = match.group(1).upper()
                            comment_text = match.group(2).strip()[:100]
                            if comment_text:
                                annotations.append({
                                    'file': rel_path,
                                    'line': str(i),
                                    'type': annotation_type,
                                    'text': comment_text
                                })
                    
                    # For shell scripts and Makefiles, look for comments starting with #
                    elif file.endswith('.sh') or file in ['Makefile']:
                        if line_stripped.startswith('#'):
                            matches = re.finditer(r'\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b:?\s*(.*)', line_stripped, re.IGNORECASE)
                            for match in matches:
                                annotation_type = match.group(1).upper()
                                comment_text = match.group(2).strip()[:100]
                                if comment_text:
                                    annotations.append({
                                        'file': rel_path,
                                        'line': str(i),
                                        'type': annotation_type,
                                        'text': comment_text
                                    })
                                    
            except Exception as e:
                print(f"Error processing {rel_path}: {e}")
                continue

    return annotations

if __name__ == '__main__':
    annotations = find_annotations()
    type_counts = Counter([ann['type'] for ann in annotations])
    
    print(f'Precise scan found {len(annotations)} annotations in comments')
    print('Type summary:')
    for ann_type, count in sorted(type_counts.items()):
        print(f'  {ann_type}: {count}')
    
    print('\nDetailed list:')
    for ann in sorted(annotations, key=lambda x: (x['file'], int(x['line']))):
        print(f"{ann['file']}:{ann['line']} - {ann['type']}: {ann['text']}")