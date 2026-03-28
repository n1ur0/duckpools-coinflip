import ast, sys

files = [
    'api_server.py',
    'services/bankroll_monitor.py',
    'services/bankroll_autoreload.py',
    'services/bankroll_manager.py',
    'services/autoreload_routes.py',
    'bankroll_routes.py',
    'bankroll_risk.py',
]

for fname in files:
    try:
        with open(fname) as f:
            source = f.read()
        ast.parse(source)
        print(f'{fname}: SYNTAX OK')
    except SyntaxError as e:
        print(f'{fname}: SYNTAX ERROR at line {e.lineno}: {e.msg}')
    except FileNotFoundError:
        print(f'{fname}: NOT FOUND')
