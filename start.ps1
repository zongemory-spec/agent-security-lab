$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv-engineering\Scripts\python.exe' init_demo.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv-engineering\Scripts\python.exe' -m uvicorn api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
