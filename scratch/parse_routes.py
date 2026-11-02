import ast

with open("backend/ai_backend.py", "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

routes = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and getattr(dec.func.value, "id", "") == "app":
                method = dec.func.attr.upper()
                path = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else "unknown"
                
                # Check for get_authenticated_user in args
                has_auth = False
                for arg in node.args.args:
                    # check default or annotation
                    pass
                for default in node.args.defaults:
                    if isinstance(default, ast.Call) and getattr(default.func, "id", "") == "Depends":
                        if default.args and getattr(default.args[0], "id", "") == "get_authenticated_user":
                            has_auth = True
                routes.append((method, path, node.name, has_auth))

print(f"Total routes found: {len(routes)}")
for m, p, n, a in sorted(routes, key=lambda x: x[1]):
    print(f"[{m:6}] {p:40} -> {n:30} (Auth: {'YES' if a else 'NO'})")
