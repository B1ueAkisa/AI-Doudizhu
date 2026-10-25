import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

for root, dirs, files in os.walk('.'):
    # Skip noisy directories
    if any(k in root for k in ['.git', 'node_modules', '__pycache__', 'recordings', 'videos']):
        continue
    for f in sorted(files):
        if f.endswith(('.html', '.js', '.css')) and not f.startswith('test') and not f.startswith('temp'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    count = sum(1 for _ in fp)
                rel = os.path.normpath(path)
                status = "⚠️ TOO LONG (>600)" if count > 600 else "✅ OK (<600)"
                print(f"{status:20s} {rel:35s}: {count} lines")
            except Exception as e:
                pass
