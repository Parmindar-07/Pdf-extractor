Set-Location -LiteralPath "H:\work"
$logPath = Join-Path $env:TEMP "credit_ocr_web_app.log"
python -u web_app.py *> $logPath
