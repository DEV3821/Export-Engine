# Development

Run tests:

```powershell
python -m compileall export_engine tests
python -m pytest
```

Default tests should not require live Outlook.

Live Outlook tests should be explicitly marked or run manually.
