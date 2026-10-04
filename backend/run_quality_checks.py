#!/usr/bin/env python3
"""
Code quality checks for AskDocs backend.
Run syntax checks, count lines, and basic code analysis.
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple

def check_syntax(file_path: Path) -> Tuple[bool, str]:
    """Check Python file syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def count_lines(file_path: Path) -> Dict[str, int]:
    """Count lines of code."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total = len(lines)
        code = 0
        comments = 0
        blank = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank += 1
            elif stripped.startswith('#'):
                comments += 1
            else:
                code += 1
        
        return {
            'total': total,
            'code': code,
            'comments': comments,
            'blank': blank
        }
    except Exception:
        return {'total': 0, 'code': 0, 'comments': 0, 'blank': 0}

def analyze_complexity(file_path: Path) -> Dict[str, int]:
    """Basic complexity analysis."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        functions = 0
        classes = 0
        imports = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports += 1
        
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports
        }
    except Exception:
        return {'functions': 0, 'classes': 0, 'imports': 0}

def main():
    print("=" * 70)
    print("🔍 AskDocs Backend Code Quality Report")
    print("=" * 70)
    print()
    
    # Find all Python files
    app_dir = Path('app')
    if not app_dir.exists():
        print("❌ app directory not found. Run from backend/ directory.")
        sys.exit(1)
    
    python_files = list(app_dir.rglob('*.py'))
    print(f"📁 Found {len(python_files)} Python files")
    print()
    
    # Check syntax
    print("🔍 Syntax Check:")
    print("-" * 70)
    syntax_errors = []
    for file_path in python_files:
        is_valid, message = check_syntax(file_path)
        if not is_valid:
            syntax_errors.append((file_path, message))
            print(f"❌ {file_path}: {message}")
    
    if not syntax_errors:
        print("✅ All files have valid syntax!")
    print()
    
    # Count lines
    print("📊 Code Statistics:")
    print("-" * 70)
    total_stats = {'total': 0, 'code': 0, 'comments': 0, 'blank': 0}
    
    for file_path in python_files:
        stats = count_lines(file_path)
        for key in total_stats:
            total_stats[key] += stats[key]
    
    print(f"Total Lines:    {total_stats['total']:>6}")
    print(f"Code Lines:     {total_stats['code']:>6}")
    print(f"Comment Lines:  {total_stats['comments']:>6}")
    print(f"Blank Lines:    {total_stats['blank']:>6}")
    
    if total_stats['code'] > 0:
        comment_ratio = (total_stats['comments'] / total_stats['code']) * 100
        print(f"Comment Ratio:  {comment_ratio:>5.1f}%")
    print()
    
    # Complexity analysis
    print("🏗️ Code Structure:")
    print("-" * 70)
    total_complexity = {'functions': 0, 'classes': 0, 'imports': 0}
    
    for file_path in python_files:
        complexity = analyze_complexity(file_path)
        for key in total_complexity:
            total_complexity[key] += complexity[key]
    
    print(f"Total Functions: {total_complexity['functions']:>5}")
    print(f"Total Classes:   {total_complexity['classes']:>5}")
    print(f"Total Imports:   {total_complexity['imports']:>5}")
    print()
    
    # Module breakdown
    print("📦 Module Breakdown:")
    print("-" * 70)
    modules = {}
    for file_path in python_files:
        module = file_path.parts[1] if len(file_path.parts) > 1 else 'root'
        modules[module] = modules.get(module, 0) + 1
    
    for module, count in sorted(modules.items(), key=lambda x: x[1], reverse=True):
        print(f"{module:.<40} {count:>3} files")
    print()
    
    # Code quality score
    print("🏆 Code Quality Score:")
    print("-" * 70)
    
    score = 100
    issues = []
    
    # Deduct for syntax errors
    if syntax_errors:
        score -= len(syntax_errors) * 10
        issues.append(f"❌ {len(syntax_errors)} syntax errors found")
    
    # Check comment ratio
    if total_stats['code'] > 0:
        comment_ratio = (total_stats['comments'] / total_stats['code']) * 100
        if comment_ratio < 5:
            score -= 10
            issues.append(f"⚠️ Low comment ratio ({comment_ratio:.1f}%)")
        elif comment_ratio >= 10:
            issues.append(f"✅ Good comment ratio ({comment_ratio:.1f}%)")
    
    # Check file organization
    if total_complexity['classes'] > 0:
        issues.append(f"✅ Object-oriented design ({total_complexity['classes']} classes)")
    
    if total_complexity['functions'] > 0:
        avg_functions_per_file = total_complexity['functions'] / len(python_files)
        if avg_functions_per_file > 10:
            score -= 5
            issues.append(f"⚠️ High functions per file ({avg_functions_per_file:.1f})")
    
    # Final score
    score = max(0, min(100, score))
    
    print(f"Overall Score: {score}/100")
    print()
    
    for issue in issues:
        print(f"  {issue}")
    
    print()
    print("=" * 70)
    
    if score >= 90:
        print("🎉 Excellent code quality!")
    elif score >= 70:
        print("✅ Good code quality!")
    elif score >= 50:
        print("⚠️  Acceptable code quality with room for improvement")
    else:
        print("❌ Code quality needs attention")
    
    print("=" * 70)
    
    return 0 if score >= 70 else 1

if __name__ == "__main__":
    sys.exit(main())


