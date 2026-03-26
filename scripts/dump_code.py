import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_file = os.path.join(base_dir, "all_programs.txt")

extensions = ('.py', '.html', '.css', '.js')
exclude_dirs = ('__pycache__', '.git', 'logs', 'venv', 'env', '.gemini', 'models', 'data')

with open(output_file, 'w', encoding='utf-8') as out_f:
    for root, dirs, files in os.walk(base_dir):
        # modify dirs in place
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(extensions) and file != 'all_programs.txt' and file != 'dump_code.py':
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as in_f:
                        content = in_f.read()
                    
                    rel_path = os.path.relpath(path, base_dir)
                    out_f.write(f"\n{'='*80}\n")
                    out_f.write(f"FILE: {rel_path}\n")
                    out_f.write(f"{'='*80}\n\n")
                    out_f.write(content)
                    out_f.write("\n")
                except Exception as e:
                    pass

print("Done dumping code to all_programs.txt")
