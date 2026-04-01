#!/usr/bin/env python3
"""Fix corrupted source code in off-chain-bot/main.py and related files."""

import os

def fix_file(filepath, replacements):
    """Apply replacements to a file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


# Fix off-chain-bot/main.py
bot_dir = os.path.join(os.path.dirname(__file__), "off-chain-bot")

# Read the file and do line-by-line fixes
main_path = os.path.join(bot_dir, "main.py")
with open(main_path, 'r') as f:
    lines = f.readlines()

fixes_applied = 0
for i, line in enumerate(lines):
    # Fix NODE_API_KEY=os.get...EY", "")
    if 'NODE_API_KEY=os.get' in line and 'EY' in line:
        lines[i] = 'NODE_API_KEY = os.getenv("NODE_API_KEY", "")\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: NODE_API_KEY")
    
    # Fix BOT_API_KEY=os.get...EY", "")
    elif 'BOT_API_KEY=os.get' in line and 'EY' in line:
        lines[i] = 'BOT_API_KEY = os.getenv("BOT_API_KEY", "")\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: BOT_API_KEY")
    
    # Fix player_secret_hex=get_re...R9")
    elif 'player_secret_hex=get_re' in line and 'R9' in line:
        lines[i] = '        player_secret_hex = get_reg_bytes("R9")\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: player_secret_hex")
    
    # Fix secret_data=bytes....hex) + bytes([player_choice])
    elif 'secret_data=bytes' in line and 'player_choice' in line:
        lines[i] = '        secret_data = bytes.fromhex(player_secret_hex) + bytes([player_choice])\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: secret_data")
    
    # Fix secret_bytes=bytes....hex)
    elif 'secret_bytes=bytes' in line and line.strip().endswith('hex)'):
        lines[i] = '        secret_bytes = bytes.fromhex(player_secret_hex)\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: secret_bytes")
    
    # Fix self.api_key=*** (literal asterisks)
    elif 'self.api_key=' in line and line.strip().endswith('***'):
        lines[i] = '        self.api_key = api_key\n'
        fixes_applied += 1
        print(f"Fixed line {i+1}: self.api_key=***")
    
    # Fix api_key=*** NODE_API_KEY (in function call)
    elif 'api_key=' in line and line.strip().endswith('***'):
        lines[i] = line.replace('api_key=***', 'api_key=NODE_API_KEY')
        fixes_applied += 1
        print(f"Fixed line {i+1}: api_key=***")

with open(main_path, 'w') as f:
    f.writelines(lines)

print(f"\nTotal fixes to main.py: {fixes_applied}")

# Also fix the misleading TODO comment
with open(main_path, 'r') as f:
    content = f.read()

old_comment = """                # TODO: Implement actual bet monitoring logic
                # This is a placeholder that will be replaced with real bet processing
                await self.process_bets()"""

new_comment = """                # Process pending bets: scan boxes, verify commitments, reveal outcomes
                await self.process_bets()"""

if old_comment in content:
    content = content.replace(old_comment, new_comment)
    with open(main_path, 'w') as f:
        f.write(content)
    print("Fixed misleading TODO comment")

# Fix backend/api_server.py
api_path = os.path.join(os.path.dirname(__file__), "backend", "api_server.py")
with open(api_path, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'NODE_API_KEY=os.get' in line and 'EY' in line:
        lines[i] = 'NODE_API_KEY = os.getenv("NODE_API_KEY", "")\n'
        print(f"Fixed api_server.py line {i+1}: NODE_API_KEY")
    elif 'allow_credentials=' in line and line.strip().endswith('***'):
        lines[i] = line.replace('allow_credentials=***', 'allow_credentials=True')
        print(f"Fixed api_server.py line {i+1}: allow_credentials")

with open(api_path, 'w') as f:
    f.writelines(lines)

# Fix backend/ergo_tx_builder.py
tx_path = os.path.join(os.path.dirname(__file__), "backend", "ergo_tx_builder.py")
with open(tx_path, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'NODE_API_KEY=os.get' in line and 'hello' in line:
        lines[i] = 'NODE_API_KEY = os.getenv("NODE_API_KEY", "hello")\n'
        print(f"Fixed ergo_tx_builder.py line {i+1}: NODE_API_KEY")

with open(tx_path, 'w') as f:
    f.writelines(lines)

# Fix off-chain-bot/health_server.py
hs_path = os.path.join(bot_dir, "health_server.py")
with open(hs_path, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'allow_credentials=' in line and line.strip().endswith('***'):
        lines[i] = line.replace('allow_credentials=***', 'allow_credentials=True')
        print(f"Fixed health_server.py line {i+1}: allow_credentials")

with open(hs_path, 'w') as f:
    f.writelines(lines)

print("\nAll source corruption fixes complete!")
