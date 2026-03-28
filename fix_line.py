#!/usr/bin/env python3
import sys

# Read the file
with open('off-chain-bot/main.py', 'r') as f:
    lines = f.readlines()

# Fix line 41 (index 40)
if len(lines) > 40:
    lines[40] = 'API_KEY=os.getenv("API_KEY", "")\n'
    
# Write back
with open('off-chain-bot/main.py', 'w') as f:
    f.writelines(lines)

print("Fixed API_KEY line")