#!/usr/bin/env python3
"""Fix corrupted API_KEY lines in bankroll files."""

files_to_fix = [
    'backend/services/bankroll_monitor.py',
    'backend/services/bankroll_autoreload.py',
]

for path in files_to_fix:
    with open(path, 'rb') as f:
        data = f.read()

    lines = data.split(b'\n')
    fixed = 0
    new_lines = []

    for i, line in enumerate(lines):
        if b'os.get' in line and (b'API_KEY' in line or b'api_key' in line):
            # Check if it's the corrupted version (not a proper os.getenv call)
            if b'os.getenv' not in line:
                # This is the corrupted line - fix it
                is_local = b'api_key=' in line  # lowercase for autoreload
                if is_local:
                    new_line = b'            api_key = os.getenv("API_KEY", "hello")'
                else:
                    new_line = b'API_KEY = os.getenv("API_KEY", "hello")'
                print(f"  Fixed line {i+1} in {path}: {line[:60]}...")
                print(f"    -> {new_line}")
                new_lines.append(new_line)
                fixed += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if fixed > 0:
        with open(path, 'wb') as f:
            f.write(b'\n'.join(new_lines))
        print(f"  Wrote {fixed} fix(es) to {path}")
    else:
        print(f"  No fixes needed in {path}")

print("Done!")
