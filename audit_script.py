import os
import ast
from collections import defaultdict
import hashlib

def get_ast_hash(node):
    # Dump tree without docstrings or line numbers to get a robust hash of the logic
    class CleanNodeTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # remove docstring
            if ast.get_docstring(node):
                node.body = node.body[1:]
            self.generic_visit(node)
            return node
    
    clean_node = CleanNodeTransformer().visit(node)
    dumped = ast.dump(clean_node, annotate_fields=False, include_attributes=False)
    return hashlib.md5(dumped.encode('utf-8')).hexdigest()

def analyze_codebase(root_dir):
    defined_funcs = {}
    func_hashes = defaultdict(list)
    called_funcs = set()
    
    for dirpath, _, filenames in os.walk(root_dir):
        if 'myenv' in dirpath or '__pycache__' in dirpath or '.git' in dirpath:
            continue
            
        for file in filenames:
            if file.endswith('.py'):
                path = os.path.join(dirpath, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    
                    tree = ast.parse(source)
                    
                    # Track function definitions
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            func_name = node.name
                            func_id = f"{os.path.relpath(path, root_dir)}::{func_name}"
                            defined_funcs[func_id] = node.lineno
                            
                            # Only hash logic if func is nontrivial (e.g. >3 lines)
                            if len(node.body) > 2:
                                h = get_ast_hash(node)
                                func_hashes[h].append(func_id)
                                
                        elif isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name):
                                called_funcs.add(node.func.id)
                            elif isinstance(node.func, ast.Attribute):
                                called_funcs.add(node.func.attr)
                                
                except Exception as e:
                    pass

    return defined_funcs, called_funcs, func_hashes

if __name__ == '__main__':
    defines, calls, hashes = analyze_codebase('.')
    
    print("=== POTENTIAL DUPLICATES ===")
    for h, funcs in hashes.items():
        if len(funcs) > 1:
            print(f"- Duplicate logic found in: {', '.join(funcs)}")
            
    print("\n=== POTENTIALLY UNUSED FUNCTIONS (Heuristic) ===")
    # Filter out common flask/override names, __init__, etc.
    ignores = ['__init__', 'setup', 'main', 'get', 'post', 'put', 'delete']
    unused = []
    for f_id in defines:
        name = f_id.split('::')[-1]
        if name not in calls and not name.startswith('__') and name not in ignores and not "route" in f_id and "api" not in f_id:
            unused.append(f_id)
            
    for u in sorted(unused):
        print(f"- {u}")
