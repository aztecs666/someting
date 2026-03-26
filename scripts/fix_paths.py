# ============================================================
# ONE-TIME MIGRATION SCRIPT — ALREADY USED, KEPT FOR REFERENCE
# This script was used to patch all import paths and DB/model
# paths when the project was restructured from flat to modular.
# It should NOT be run again.
# ============================================================

import os
import glob
import re

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original_content = content

    sys_code = """import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
"""

    # Inject sys path logic
    if "import sys" not in content and "PROJECT_ROOT" not in content:
        content = content.replace("import os\n", sys_code)
    elif "import os" in content and "PROJECT_ROOT" not in content:
        content = content.replace("import os\n", sys_code)
        
    # Replace BASE_DIR entirely
    content = re.sub(
        r'BASE_DIR = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\nDB_PATH = os\.path\.join\(BASE_DIR, "shipments\.db"\)',
        r'DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")',
        content
    )
    
    content = re.sub(
        r'DB_PATH = os\.path\.join\(os\.path\.dirname\(os\.path\.abspath\(__file__\)\), "shipments\.db"\)',
        r'DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")',
        content
    )

    content = re.sub(
        r'MODEL_PATH = os\.path\.join\(BASE_DIR, "benchmark_model\.joblib"\)',
        r'MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.joblib")',
        content
    )

    content = re.sub(
        r'BACKUP_MODEL_PATH = os\.path\.join\(BASE_DIR, "benchmark_model\.backup\.joblib"\)',
        r'BACKUP_MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.backup.joblib")',
        content
    )

    content = re.sub(
        r'FEATURES_PATH = os\.path\.join\(BASE_DIR, "benchmark_features\.joblib"\)',
        r'FEATURES_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_features.joblib")',
        content
    )
    
    # Fix import paths
    content = re.sub(r'from fetch_fred_data', r'from data.fetch_fred_data', content)
    content = re.sub(r'from build_train_data', r'from pipeline.build_train_data', content)
    content = re.sub(r'from stream_engine', r'from app.stream_engine', content)
    content = re.sub(r'from real_data_fetcher', r'from data.real_data_fetcher', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched: {filepath}")

for root_dir, dirs, files in os.walk(root):
    if '.git' in root_dir or '__pycache__' in root_dir: continue
    for file in files:
        if not file.endswith('.py'): continue
        if file == 'fix_paths.py': continue
        patch_file(os.path.join(root_dir, file))
