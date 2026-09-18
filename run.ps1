Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

$env:PRODUCTION_CONFIG = "$PSScriptRoot\backend\production.local.json"
$env:DATA_MODE = "production"
$env:MATOMO_URL = "https://matomo.istanapresiden.go.id"
$env:MATOMO_TOKEN_AUTH = "3661d419ce3be50613490646ca8e2574"
$env:PROMETHEUS_URL = "https://192.168.32.247:30443"
$env:PROMETHEUS_BEARER_TOKEN = "uk2_xLM8CfhIizcHbmTAYG4L1sGufsJBWbZqQtjsPAc6"
$env:SIGNOZ_URL = "https://192.168.32.247:30444"
$env:SIGNOZ_API_KEY = "yHsIv9EK7EZi0DcCK38B4kEovI/wBTBv8EBufOulngg="

Set-Location "$PSScriptRoot\backend"
python server.pyc