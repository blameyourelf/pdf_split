# Troubleshooting

## Common Issues

### ModuleNotFoundError: No module named 'fitz'

This happens when the PyMuPDF package is not installed. To fix this:

```bash
pip install PyMuPDF
```

Or run our installation helper:

```bash
./install_missing_deps.sh
```

### get_static_doc error with Google Drive API

If you see an error like `'object' object has no attribute 'get_static_doc'`, this is a known issue with the Google Drive API. Our scripts attempt to automatically patch this issue, but if you still encounter it, you can manually fix it by running:

```bash
python -c "
import os
patch_dir = os.path.expanduser('~/.googleapiclient')
os.makedirs(patch_dir, exist_ok=True)
with open(os.path.join(patch_dir, '__init__.py'), 'w') as f:
    f.write('# Patching discovery for static_discovery issues\\n')
with open(os.path.join(patch_dir, 'discovery.py'), 'w') as f:
    f.write('from googleapiclient import discovery\\n')
    f.write('_original_build = discovery.build\\n')
    f.write('def patched_build(*args, **kwargs):\\n')
    f.write('    kwargs[\"static_discovery\"] = False\\n')
    f.write('    return _original_build(*args, **kwargs)\\n')
    f.write('discovery.build = patched_build\\n')
print('Patch applied successfully!')
"
```

### Other dependency issues

If you're encountering other missing dependencies, you can run our dependency installation script:

```bash
./install_missing_deps.sh
```
