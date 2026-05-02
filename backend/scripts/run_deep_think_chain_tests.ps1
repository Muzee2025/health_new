param(
  [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

& $PythonExe -m pytest `
  tests/test_deep_think_mode.py `
  tests/test_deep_think_realtime_chain.py `
  tests/test_advanced_chat_stream.py

if ($LASTEXITCODE -ne 0) {
  throw "Deep-think chain tests failed"
}

Write-Host "Deep-think chain tests passed"
