# Check actual content of lines 46 and 48 in api_server.py
with open('api_server.py') as f:
    lines = f.readlines()

# Check for any garbled env reads
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if 'os.get' in stripped and 'os.getenv' not in stripped:
        print(f'LINE {i}: POTENTIAL BUG: {stripped[:100]}')
    if 'API_KEY' in stripped or 'LP_TOKEN' in stripped:
        print(f'LINE {i}: {stripped[:120]}')
