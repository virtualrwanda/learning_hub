@echo off
REM Auto-inserts `await db.refresh(obj)` after flush() in endpoint files.
REM Idempotent: won't double-insert if already present.
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Auto-fixing refresh-after-flush pattern
echo ============================================================

".venv\Scripts\python.exe" -c "import pathlib, re, sys; \
files = list(pathlib.Path('app/api/v1').glob('*.py')); \
patched = 0; \
[ \
  (lambda p: ( \
    lambda content: ( \
      lambda new: ( \
        p.write_text(new, encoding='utf-8') if new != content else None, \
        setattr(sys.modules[__name__], 'patched', patched + (1 if new != content else 0)) \
      )( \
        re.sub( \
          r'(await db\.flush\(\)\s*\n(?:\s*\n)?\s*)(return\s+\w+Public\.model_validate\()', \
          r'\1await db.refresh(obj)\n        \2', \
          content \
        ) \
      ) \
    ))(p.read_text(encoding='utf-8')) \
  )(p) for p in files if p.name not in ('__init__.py',) ]; \
print(f'Patched {patched} file(s)') \
"

echo.
echo Manual check: after running, look at any route file. You should
echo see `await db.refresh(obj)` right before the return statement.
echo.
pause