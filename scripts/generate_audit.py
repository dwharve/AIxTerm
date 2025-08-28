#!/usr/bin/env python3
"""
AIxTerm Repository Audit Generator

Generates a comprehensive baseline audit of the AIxTerm codebase including:
- Repository structure and metrics
- Code patterns and annotations
- Dependencies and tooling
- Maintenance hotspots and findings

This script uses only Python standard library to avoid external dependencies.
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional


class AuditGenerator:
    """Generates comprehensive repository audit reports."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.findings = []
        self.finding_id_counter = 1

        # Directories to exclude from analysis
        self.exclude_dirs = {
            '.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
            'node_modules', 'dist', 'build', '.tox', '.mypy_cache',
            '.coverage', 'htmlcov', '.eggs', '*.egg-info'
        }

        # File extensions to analyze for code patterns
        self.code_extensions = {'.py', '.js', '.ts', '.sh', '.yml', '.yaml', '.json'}

    def check_git_clean(self) -> bool:
        """Check if git working tree is clean."""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return len(result.stdout.strip()) == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Warning: Could not check git status")
            return True

    def get_git_info(self) -> Dict[str, str]:
        """Get current git commit information."""
        info = {"commit_hash": "unknown", "branch": "unknown"}
        try:
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            info["commit_hash"] = result.stdout.strip()

            # Get branch name
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            info["branch"] = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return info

    def get_repository_structure(self, max_depth: int = 4) -> str:
        """Generate repository structure tree."""
        try:
            # Try using tree command first
            result = subprocess.run(
                ['tree', '-d', '-L', str(max_depth), '-I',
                 '|'.join(self.exclude_dirs)],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass

        # Fallback to find command
        try:
            result = subprocess.run(
                ['find', '.', '-type', 'd', '-name', '__pycache__', '-prune', '-o',
                 '-type', 'd', '-print'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            dirs = sorted([d for d in result.stdout.split('\n') if d and d != '.'])
            # Simple tree-like formatting
            output = ".\n"
            for dir_path in dirs[:50]:  # Limit output
                depth = dir_path.count('/')
                if depth <= max_depth:
                    indent = "│   " * (depth - 1) + "├── " if depth > 0 else ""
                    dir_name = os.path.basename(dir_path)
                    output += f"{indent}{dir_name}\n"
            return output
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "Could not generate repository structure"

    def get_cloc_metrics(self) -> Optional[str]:
        """Get code metrics using cloc if available."""
        try:
            result = subprocess.run(
                ['cloc', '.', '--exclude-dir=' + ','.join(self.exclude_dirs)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def get_file_metrics(self) -> Dict[str, Any]:
        """Get file size and count metrics."""
        metrics = {
            'total_files': 0,
            'by_extension': defaultdict(int),
            'largest_files': [],
            'total_size': 0
        }

        all_files = []

        for root, dirs, files in os.walk(self.repo_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if file.startswith('.') and file not in ['.gitignore', '.flake8', '.rules']:
                    continue

                file_path = Path(root) / file
                try:
                    size = file_path.stat().st_size
                    ext = file_path.suffix.lower()

                    metrics['total_files'] += 1
                    metrics['by_extension'][ext or 'no_extension'] += 1
                    metrics['total_size'] += size

                    # Track largest files
                    rel_path = file_path.relative_to(self.repo_root)
                    all_files.append((size, str(rel_path)))

                except (OSError, ValueError):
                    continue

        # Get top 20 largest files
        all_files.sort(reverse=True, key=lambda x: x[0])
        metrics['largest_files'] = all_files[:20]

        return metrics

    def analyze_dependencies(self) -> Dict[str, List[str]]:
        """Analyze project dependencies from configuration files."""
        deps = defaultdict(list)

        # Python dependencies
        for file_name in ['requirements.txt', 'requirements-dev.txt', 'pyproject.toml', 'setup.py']:
            file_path = self.repo_root / file_name
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    if file_name.endswith('.txt'):
                        # Parse requirements.txt format
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Extract package name (before any version specifiers)
                                pkg = re.split(r'[<>=!]', line)[0].strip()
                                if pkg:
                                    deps[file_name].append(pkg)
                    elif file_name == 'pyproject.toml':
                        # Basic pyproject.toml parsing (dependencies section)
                        in_deps = False
                        for line in content.split('\n'):
                            if 'dependencies' in line and '[' in line:
                                in_deps = True
                            elif in_deps and line.strip().startswith('"'):
                                match = re.search(r'"([^"<>=!]+)', line)
                                if match:
                                    deps[file_name].append(match.group(1))
                            elif in_deps and ']' in line:
                                in_deps = False
                    elif file_name == 'setup.py':
                        # Extract from install_requires
                        matches = re.findall(
                            r'install_requires.*?\[(.*?)\]', content, re.DOTALL)
                        for match in matches:
                            for line in match.split('\n'):
                                line = line.strip().strip(',').strip('"\'')
                                if line and not line.startswith('#'):
                                    pkg = re.split(r'[<>=!]', line)[0].strip()
                                    if pkg:
                                        deps[file_name].append(pkg)
                except Exception:
                    continue

        return dict(deps)

    def analyze_makefile_targets(self) -> List[str]:
        """Extract Makefile targets."""
        makefile_path = self.repo_root / 'Makefile'
        targets = []

        if makefile_path.exists():
            try:
                content = makefile_path.read_text()
                # Find target definitions (lines starting with word followed by colon)
                for line in content.split('\n'):
                    match = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*):(?!\=)', line)
                    if match:
                        targets.append(match.group(1))
            except Exception:
                pass

        return targets

    def analyze_ci_workflows(self) -> List[str]:
        """Analyze CI/CD workflows."""
        workflows = []
        workflows_dir = self.repo_root / '.github' / 'workflows'

        if workflows_dir.exists():
            for file in workflows_dir.glob('*.yml'):
                try:
                    content = file.read_text()
                    # Extract workflow name
                    name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
                    name = name_match.group(1).strip() if name_match else file.stem
                    workflows.append(name)
                except Exception:
                    workflows.append(file.stem)

        return workflows

    def find_config_patterns(self) -> Dict[str, Any]:
        """Find configuration and environment variable access patterns."""
        patterns = defaultdict(list)
        env_var_names = defaultdict(list)  # Track specific env var names

        # Patterns to search for
        config_patterns = {
            'env_vars': r'\b(?:os\.environ|getenv|ENV)\b',
            'config_files': r'\.(?:config|cfg|ini|conf|yaml|yml|json|toml)\b',
            'settings': r'\b(?:settings|config|configuration)\b'
        }

        # Patterns to extract specific environment variable names
        env_var_patterns = [
            r'os\.getenv\(["\']([^"\']+)["\']',
            r'os\.environ\[["\']([^"\']+)["\']\]',
            r'os\.environ\.get\(["\']([^"\']+)["\']',
            r'getenv\(["\']([^"\']+)["\']'
        ]

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts', '.sh')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    for pattern_name, pattern in config_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            patterns[pattern_name].append(
                                f"{rel_path} ({len(matches)} occurrences)")

                    # Extract specific environment variable names
                    for pattern in env_var_patterns:
                        matches = re.findall(pattern, content)
                        for var_name in matches:
                            if var_name not in env_var_names:
                                env_var_names[var_name] = []
                            env_var_names[var_name].append(rel_path)

                except Exception:
                    continue

        result = dict(patterns)
        result['env_var_names'] = dict(env_var_names)
        return result

    def analyze_logging_patterns(self) -> Dict[str, List[str]]:
        """Analyze logging usage patterns with granular metrics."""
        patterns = defaultdict(list)

        logging_patterns = {
            'console_log': r'\bconsole\.(log|error|warn|info|debug)\b',
            'python_logging': r'\blog(?:ger)?\.(debug|info|warn|warning|error|critical)\b',
            'print_statements': r'\bprint\s*\(',
            'custom_loggers': r'getLogger|Logger\(',
            # New granular patterns
            'logger_instances': r'(?:logger\s*=\s*)?logging\.getLogger\(',
            'direct_logging_calls': r'logging\.(debug|info|warn|warning|error|critical)\(',
            'module_loggers': r'__name__.*getLogger',
        }

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    for pattern_name, pattern in logging_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            patterns[pattern_name].append(
                                f"{rel_path} ({len(matches)} occurrences)")

                except Exception:
                    continue

        return dict(patterns)

    def analyze_error_patterns(self) -> Dict[str, List[str]]:
        """Analyze error handling patterns."""
        patterns = defaultdict(list)

        error_patterns = {
            'try_except': r'\btry\s*:.*?except\b',
            'raise_statements': r'\braise\b',
            'custom_exceptions': r'class\s+\w+Exception\s*\(',
            'error_classes': r'Error\w*\s*\(',
            'result_wrappers': r'Result\[|Optional\[|Union\['
        }

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    for pattern_name, pattern in error_patterns.items():
                        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
                        if matches:
                            patterns[pattern_name].append(
                                f"{rel_path} ({len(matches)} occurrences)")

                except Exception:
                    continue

        return dict(patterns)

    def analyze_async_patterns(self) -> Dict[str, List[str]]:
        """Analyze async/concurrency patterns."""
        patterns = defaultdict(list)

        async_patterns = {
            'async_functions': r'\basync\s+def\b',
            'await_calls': r'\bawait\b',
            'callbacks': r'callback|\.on\(',
            'promises': r'Promise\[|\.then\(',
            'threading': r'\bthreading\.|Thread\(',
            'multiprocessing': r'\bmultiprocessing\.|Process\('
        }

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    for pattern_name, pattern in async_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            patterns[pattern_name].append(
                                f"{rel_path} ({len(matches)} occurrences)")

                except Exception:
                    continue

        return dict(patterns)

    def find_code_annotations(self) -> List[Dict[str, str]]:
        """Find TODO/FIXME/HACK/DEPRECATED/LEGACY annotations."""
        annotations = []

        annotation_patterns = r'\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b:?\s*(.*)'

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if file.endswith(tuple(self.code_extensions)) or file in ['Makefile', 'README.md']:
                    file_path = Path(root) / file
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        rel_path = str(file_path.relative_to(self.repo_root))

                        for i, line in enumerate(content.split('\n'), 1):
                            matches = re.finditer(
                                annotation_patterns, line, re.IGNORECASE)
                            for match in matches:
                                annotation_type = match.group(1).upper()
                                comment_text = match.group(
                                    2).strip()[:100]  # Limit length
                                annotations.append({
                                    'file': rel_path,
                                    'line': str(i),
                                    'type': annotation_type,
                                    'text': comment_text
                                })

                    except Exception:
                        continue

        return annotations

    def find_commented_code_blocks(self) -> List[Dict[str, Any]]:
        """Find large blocks of commented-out code (>5 lines)."""
        code_blocks = []

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts', '.sh')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    lines = content.split('\n')
                    i = 0
                    while i < len(lines):
                        # Look for start of commented block
                        if (lines[i].strip().startswith('#') or
                                lines[i].strip().startswith('//')):

                            block_start = i
                            # Count consecutive comment lines
                            while (i < len(lines) and
                                   (lines[i].strip().startswith('#') or
                                    lines[i].strip().startswith('//'))):
                                i += 1

                            block_length = i - block_start
                            if block_length > 5:  # Only blocks >5 lines
                                # Check if it looks like commented code vs documentation
                                block_text = '\n'.join(lines[block_start:i])
                                # Simple heuristic: look for code patterns
                                code_indicators = len(re.findall(
                                    r'[=(){}\[\];]', block_text))
                                if code_indicators > block_length * 0.3:  # 30% threshold
                                    code_blocks.append({
                                        'file': rel_path,
                                        'start_line': block_start + 1,
                                        'end_line': i,
                                        'length': block_length
                                    })
                        else:
                            i += 1

                except Exception:
                    continue

        return code_blocks

    def find_potential_duplications(self) -> Dict[str, Any]:
        """Find potential code duplications with detailed breakdown."""
        duplications = []
        function_names = defaultdict(list)
        dunder_methods = defaultdict(list)  # Track dunder methods separately

        # Look for repeated function/method names
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith(('.py', '.js', '.ts')):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(self.repo_root))

                    # Find function definitions
                    func_patterns = [
                        r'def\s+(\w+)\s*\(',  # Python functions
                        r'function\s+(\w+)\s*\(',  # JavaScript functions
                        r'(\w+)\s*:\s*function',  # JavaScript object methods
                        r'async\s+(\w+)\s*\('  # Async functions
                    ]

                    for pattern in func_patterns:
                        matches = re.findall(pattern, content)
                        for func_name in matches:
                            if len(func_name) > 3:  # Ignore very short names
                                if func_name.startswith('__') and func_name.endswith('__'):
                                    # Track dunder methods separately
                                    dunder_methods[func_name].append(rel_path)
                                else:
                                    function_names[func_name].append(rel_path)

                except Exception:
                    continue

        # Build detailed duplication table
        duplication_table = []
        for func_name, files in function_names.items():
            if len(files) > 1:
                # Remove duplicates from file list but keep count
                unique_files = list(set(files))
                file_count = len(files)
                # Truncate file paths if too many
                if len(unique_files) > 8:
                    file_paths = ", ".join(unique_files[:8]) + f" ... ({len(unique_files)-8} more)"
                else:
                    file_paths = ", ".join(unique_files)
                    
                duplication_table.append({
                    'function_name': func_name,
                    'file_count': file_count,
                    'unique_file_count': len(unique_files),
                    'file_paths': file_paths
                })
                
                duplications.append(
                    f"Function '{func_name}' appears in: {', '.join(unique_files)}")

        # Build dunder methods summary
        dunder_summary = []
        for dunder_name, files in dunder_methods.items():
            if len(files) > 1:
                unique_files = list(set(files))
                dunder_summary.append({
                    'method_name': dunder_name,
                    'file_count': len(files),
                    'unique_file_count': len(unique_files),
                    'file_paths': ", ".join(unique_files[:5]) + (f" ... ({len(unique_files)-5} more)" if len(unique_files) > 5 else "")
                })

        return {
            'duplications': duplications[:20],  # Limit to top 20 for backward compatibility
            'duplication_table': sorted(duplication_table, key=lambda x: x['unique_file_count'], reverse=True)[:20],
            'dunder_summary': sorted(dunder_summary, key=lambda x: x['unique_file_count'], reverse=True)[:10]
        }

    def analyze_test_coverage_surface(self) -> Dict[str, Any]:
        """Analyze test coverage surface (static mapping only)."""
        coverage = {
            'test_files': [],
            'source_directories': [],
            'test_to_source_mapping': [],
            'uncovered_areas': []
        }

        # Find test files
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.repo_root))

                if (file.startswith('test_') or file.endswith('_test.py') or
                        'test' in rel_path.lower()):
                    coverage['test_files'].append(rel_path)

        # Find source directories
        for item in self.repo_root.iterdir():
            if (item.is_dir() and
                item.name not in self.exclude_dirs and
                not item.name.startswith('.') and
                    item.name not in ['docs', 'tests']):
                coverage['source_directories'].append(item.name)

        # Simple mapping heuristic
        for test_file in coverage['test_files']:
            # Try to infer which source it tests
            test_name = Path(test_file).stem
            if test_name.startswith('test_'):
                source_name = test_name[5:]  # Remove 'test_' prefix
                coverage['test_to_source_mapping'].append(
                    f"{test_file} -> {source_name}")

        return coverage

    def identify_risk_hotspots(self, file_metrics: Dict) -> List[str]:
        """Identify maintenance and risk hotspots."""
        hotspots = []

        # Large files (>500 lines or >20KB)
        for size, filepath in file_metrics['largest_files'][:10]:
            if size > 20000:  # >20KB
                hotspots.append(f"Large file: {filepath} ({size} bytes)")

        # Files with many TODO/FIXME comments indicate maintenance needs
        annotations = self.find_code_annotations()
        file_annotation_count = defaultdict(int)
        for annotation in annotations:
            file_annotation_count[annotation['file']] += 1

        for file, count in sorted(file_annotation_count.items(),
                                  key=lambda x: x[1], reverse=True)[:5]:
            if count > 3:
                hotspots.append(f"High annotation count: {file} ({count} TODOs/FIXMEs)")

        # Look for potential God objects/modules
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    lines = len(content.split('\n'))
                    rel_path = str(file_path.relative_to(self.repo_root))

                    if lines > 500:  # Large file
                        # Count classes and functions
                        class_count = len(re.findall(
                            r'^\s*class\s+\w+', content, re.MULTILINE))
                        func_count = len(re.findall(
                            r'^\s*def\s+\w+', content, re.MULTILINE))

                        if class_count > 5 or func_count > 20:
                            hotspots.append(
                                f"Complex module: {rel_path} ({lines} lines, {class_count} classes, {func_count} functions)")

                except Exception:
                    continue

        return hotspots

    def add_finding(self, category: str, evidence: str, impact: str, effort: str, action: str) -> int:
        """Add a finding to the findings list and return its ID."""
        finding_id = f"F{self.finding_id_counter:03d}"
        self.finding_id_counter += 1

        self.findings.append({
            'id': finding_id,
            'category': category,
            'evidence': evidence,
            'impact': impact,
            'effort': effort,
            'action': action
        })

        return self.finding_id_counter - 1

    def generate_findings(self, annotations: List, duplications: List, file_metrics: Dict,
                          hotspots: List) -> None:
        """Generate Phase 1 findings based on analysis."""

        # Findings from code annotations
        annotation_counts = Counter([ann['type'] for ann in annotations])
        for ann_type, count in annotation_counts.items():
            if count > 5:  # Significant number of annotations
                self.add_finding(
                    category="Legacy/Dead" if ann_type in [
                        'DEPRECATED', 'LEGACY'] else "Inconsistency",
                    evidence=f"{count} {ann_type} annotations across codebase",
                    impact="Med",
                    effort="M",
                    action=f"Review and address {ann_type} annotations systematically"
                )

        # Findings from duplications
        if len(duplications) > 5:
            self.add_finding(
                category="Duplication",
                evidence=f"{len(duplications)} potentially duplicated function names",
                impact="Med",
                effort="L",
                action="Review and consolidate duplicate functions"
            )

        # Findings from large files
        large_files = [f for s, f in file_metrics['largest_files'][:5] if s > 50000]
        if large_files:
            self.add_finding(
                category="Risky Pattern",
                evidence=f"Large files detected: {', '.join(large_files)}",
                impact="High",
                effort="L",
                action="Consider modularizing large files"
            )

        # Findings from hotspots
        for hotspot in hotspots[:3]:
            if "Complex module" in hotspot:
                self.add_finding(
                    category="Risky Pattern",
                    evidence=hotspot,
                    impact="High",
                    effort="L",
                    action="Consider breaking down complex modules"
                )

    def generate_audit_report(self) -> str:
        """Generate the complete audit report."""
        git_info = self.get_git_info()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Collect all analysis data
        repo_structure = self.get_repository_structure()
        cloc_output = self.get_cloc_metrics()
        file_metrics = self.get_file_metrics()
        dependencies = self.analyze_dependencies()
        makefile_targets = self.analyze_makefile_targets()
        ci_workflows = self.analyze_ci_workflows()
        config_patterns = self.find_config_patterns()
        logging_patterns = self.analyze_logging_patterns()
        error_patterns = self.analyze_error_patterns()
        async_patterns = self.analyze_async_patterns()
        annotations = self.find_code_annotations()
        commented_blocks = self.find_commented_code_blocks()
        duplications = self.find_potential_duplications()
        test_coverage = self.analyze_test_coverage_surface()
        hotspots = self.identify_risk_hotspots(file_metrics)

        # Generate findings
        duplications_data = duplications
        self.generate_findings(annotations, duplications_data.get('duplications', []), file_metrics, hotspots)

        # Build report
        report = f"""# AIxTerm Repository Audit Report

**Generated:** {timestamp}
**Commit:** {git_info['commit_hash']}
**Branch:** {git_info['branch']}
**Script:** scripts/generate_audit.py

<!-- AUDIT_CONTENT_START -->

## Repository Structure

```
{repo_structure}
```

## Language & File Metrics

### Code Statistics (cloc)

"""

        if cloc_output:
            report += f"```\n{cloc_output}\n```\n\n"
        else:
            report += "```\ncloc not available - install with: apt-get install cloc\n```\n\n"

        report += f"""### File Distribution

- **Total Files:** {file_metrics['total_files']:,}
- **Total Size:** {file_metrics['total_size'] / 1024 / 1024:.1f} MB

#### By File Type
"""

        for ext, count in sorted(file_metrics['by_extension'].items(),
                                 key=lambda x: x[1], reverse=True)[:10]:
            report += f"- {ext or 'no extension'}: {count} files\n"

        report += "\n#### Largest Files\n"
        for size, filepath in file_metrics['largest_files'][:10]:
            size_kb = size / 1024
            report += f"- {filepath}: {size_kb:.1f} KB\n"

        report += "\n## Dependency Inventory\n\n"

        if dependencies:
            for dep_file, deps in dependencies.items():
                report += f"### {dep_file}\n"
                for dep in sorted(deps)[:20]:  # Limit to top 20
                    report += f"- {dep}\n"
                report += "\n"
        else:
            report += "No dependency files detected.\n\n"

        report += "## Tooling & Automation Inventory\n\n"

        report += "### Makefile Targets\n"
        if makefile_targets:
            for target in sorted(makefile_targets)[:20]:
                report += f"- {target}\n"
        else:
            report += "No Makefile found.\n"

        report += "\n### CI/CD Workflows\n"
        if ci_workflows:
            for workflow in sorted(ci_workflows):
                report += f"- {workflow}\n"
        else:
            report += "No GitHub workflows found.\n"

        report += "\n## Configuration Discovery\n\n"

        for pattern_name, files in config_patterns.items():
            if pattern_name == 'env_var_names':
                continue  # Handle this separately
            if files:
                report += f"### {pattern_name.replace('_', ' ').title()}\n"
                for file_info in sorted(files)[:10]:
                    report += f"- {file_info}\n"
                report += "\n"

        # Add detailed environment variable names table
        env_var_names = config_patterns.get('env_var_names', {})
        if env_var_names:
            report += "### Environment Variable Names\n\n"
            report += "| Env Var | Files | Occurrence Count |\n"
            report += "|---------|-------|------------------|\n"
            for var_name, files in sorted(env_var_names.items()):
                unique_files = list(set(files))
                occurrence_count = len(files)
                file_list = ", ".join(unique_files[:3])
                if len(unique_files) > 3:
                    file_list += f" ... ({len(unique_files) - 3} more)"
                report += f"| {var_name} | {file_list} | {occurrence_count} |\n"
            report += "\n"

        report += "## Logging Patterns\n\n"

        for pattern_name, files in logging_patterns.items():
            if files:
                report += f"### {pattern_name.replace('_', ' ').title()}\n"
                for file_info in sorted(files)[:10]:
                    report += f"- {file_info}\n"
                report += "\n"

        report += "## Error Handling Patterns\n\n"

        for pattern_name, files in error_patterns.items():
            if files:
                report += f"### {pattern_name.replace('_', ' ').title()}\n"
                for file_info in sorted(files)[:10]:
                    report += f"- {file_info}\n"
                report += "\n"

        report += "## Async/Concurrency Patterns\n\n"

        for pattern_name, files in async_patterns.items():
            if files:
                report += f"### {pattern_name.replace('_', ' ').title()}\n"
                for file_info in sorted(files)[:10]:
                    report += f"- {file_info}\n"
                report += "\n"

        report += "## Code Annotations\n\n"

        if annotations:
            report += "| File | Line | Type | Description |\n"
            report += "|------|------|------|-------------|\n"
            for ann in sorted(annotations, key=lambda x: (x['type'], x['file']))[:30]:
                report += f"| {ann['file']} | {ann['line']} | {ann['type']} | {ann['text']} |\n"
        else:
            report += "No code annotations found.\n"

        report += "\n## Commented-Out Code Blocks\n\n"

        if commented_blocks:
            report += "| File | Line Range | Length |\n"
            report += "|------|------------|--------|\n"
            for block in sorted(commented_blocks, key=lambda x: x['length'], reverse=True)[:15]:
                report += f"| {block['file']} | {block['start_line']}-{block['end_line']} | {block['length']} lines |\n"
        else:
            report += "No large commented-out code blocks detected.\n"

        report += "\n## Potential Duplication Candidates\n\n"

        duplications_data = duplications
        duplication_table = duplications_data.get('duplication_table', [])
        dunder_summary = duplications_data.get('dunder_summary', [])
        
        if duplication_table:
            report += "### Function Duplication Table\n\n"
            report += "| Function Name | File Count | File Paths |\n"
            report += "|---------------|------------|------------|\n"
            for dup in duplication_table:
                report += f"| {dup['function_name']} | {dup['unique_file_count']} | {dup['file_paths']} |\n"
            report += "\n"
        
        if dunder_summary:
            report += "### Dunder Methods Summary\n\n"
            report += "| Method Name | File Count | File Paths |\n"
            report += "|-------------|------------|------------|\n"
            for dunder in dunder_summary:
                report += f"| {dunder['method_name']} | {dunder['unique_file_count']} | {dunder['file_paths']} |\n"
            report += "\n"

        # Keep legacy format for backward compatibility
        duplications_list = duplications_data.get('duplications', [])
        if duplications_list:
            report += "### Legacy Format\n"
            for dup in duplications_list[:10]:  # Limit display
                report += f"- {dup}\n"
        else:
            report += "No obvious duplication candidates detected.\n"

        report += "\n## Test Coverage Surface Mapping\n\n"

        report += f"### Test Files ({len(test_coverage['test_files'])})\n"
        for test_file in sorted(test_coverage['test_files'])[:15]:
            report += f"- {test_file}\n"

        report += f"\n### Source Directories ({len(test_coverage['source_directories'])})\n"
        for src_dir in sorted(test_coverage['source_directories']):
            report += f"- {src_dir}/\n"

        report += "\n### Test to Source Mapping\n"
        for mapping in sorted(test_coverage['test_to_source_mapping'])[:10]:
            report += f"- {mapping}\n"

        report += "\n## Build & CI Quality Gates\n\n"

        # Extract quality gates from Makefile
        quality_gates = []
        if 'quality-check' in makefile_targets:
            quality_gates.append(
                "quality-check (format-check, lint, type-check, import-check, security-check)")
        if 'test' in makefile_targets:
            quality_gates.append("test (pytest)")
        if 'ci' in makefile_targets:
            quality_gates.append("ci (test + quality-check)")

        if quality_gates:
            for gate in quality_gates:
                report += f"- {gate}\n"
        else:
            report += "No explicit quality gates identified.\n"

        report += "\n## Risk & Maintenance Hotspots\n\n"

        if hotspots:
            for hotspot in hotspots:
                report += f"- {hotspot}\n"
        else:
            report += "No significant risk hotspots identified.\n"

        report += "\n## Phase 1 Findings\n\n"

        if self.findings:
            report += "| ID | Category | Evidence | Impact | Effort | Recommended Action |\n"
            report += "|----|----------|----------|--------|--------|-----------------|\n"
            for finding in self.findings:
                report += f"| {finding['id']} | {finding['category']} | {finding['evidence']} | {finding['impact']} | {finding['effort']} | {finding['action']} |\n"
        else:
            report += "No findings generated in Phase 1 analysis.\n"

        report += "\n## Methodology\n\n"

        report += """This audit was generated using the following commands and techniques:

### Data Collection
- `git rev-parse HEAD` - Get current commit hash
- `git rev-parse --abbrev-ref HEAD` - Get current branch
- `tree -d -L 4` or `find . -type d` - Repository structure
- `cloc . --exclude-dir=...` - Code metrics (if available)
- `os.walk()` - File system traversal and analysis
- `re.findall()` - Pattern matching for code analysis

### Analysis Patterns
- **Code Annotations:** `\\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\\b`
- **Function Definitions:** `def\\s+(\\w+)\\s*\\(`, `function\\s+(\\w+)\\s*\\(`
- **Logging:** `console\\.(log|error|warn)`, `log(?:ger)?\\.(debug|info|warn)`
- **Error Handling:** `\\btry\\s*:.*?except\\b`, `\\braise\\b`
- **Async Patterns:** `\\basync\\s+def\\b`, `\\bawait\\b`
- **Configuration:** `\\b(?:os\\.environ|getenv|ENV)\\b`

### File Analysis
- Extensions analyzed: {', '.join(sorted(self.code_extensions))}
- Directories excluded: {', '.join(sorted(self.exclude_dirs))}
- Encoding: UTF-8 with error handling
- Large file threshold: >20KB or >500 lines
- Comment block threshold: >5 consecutive lines

### Limitations
- Static analysis only (no runtime instrumentation)
- Pattern-based detection (may have false positives/negatives)
- Limited to text-based analysis
- Heuristic-based duplication detection
- Manual review recommended for all findings
"""

        report += "\n<!-- AUDIT_CONTENT_END -->\n"

        return report

    def run(self) -> None:
        """Run the audit generation process."""
        print("AIxTerm Repository Audit Generator")
        print("=" * 40)

        # Check git status
        if not self.check_git_clean():
            print("Error: Git working tree is not clean. Please commit or stash changes.")
            sys.exit(1)

        print("Generating audit report...")

        try:
            audit_content = self.generate_audit_report()

            # Write to audit file
            audit_path = self.repo_root / 'docs' / 'audit' / 'audit.md'
            audit_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists and preserve manual content
            existing_content = ""
            if audit_path.exists():
                existing_content = audit_path.read_text()

            # Replace content between markers
            start_marker = "<!-- AUDIT_CONTENT_START -->"
            end_marker = "<!-- AUDIT_CONTENT_END -->"

            if start_marker in existing_content and end_marker in existing_content:
                # Extract manual content before and after markers
                before = existing_content.split(start_marker)[0]
                after = existing_content.split(
                    end_marker)[1] if end_marker in existing_content else ""
                # Get new content between markers
                new_content = audit_content.split(start_marker)[1].split(end_marker)[0]
                audit_content = before + start_marker + new_content + end_marker + after

            audit_path.write_text(audit_content)

            print(f"Audit report generated: {audit_path}")
            print(f"Found {len(self.findings)} initial findings")
            print("Run 'make audit-baseline' to regenerate this report")

        except Exception as e:
            print(f"Error generating audit: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent.resolve()

    if not (repo_root / '.git').exists():
        print("Error: Not in a git repository")
        sys.exit(1)

    generator = AuditGenerator(repo_root)
    generator.run()


if __name__ == "__main__":
    main()
