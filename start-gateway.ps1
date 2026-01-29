# Moltbot Gateway Launcher
# This script sets the environment variable and starts the gateway
# All data will be stored in the project folder (.moltbot-data/)

$ProjectDir = "C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot"
$MoltbotData = "$ProjectDir\.moltbot-data"

Write-Host "=== Moltbot Gateway Launcher ===" -ForegroundColor Cyan
Write-Host ""

# Set environment variable for moltbot state directory
$env:MOLTBOT_STATE_DIR = $MoltbotData

Write-Host "Data Dir: $MoltbotData" -ForegroundColor Gray
Write-Host ""
Write-Host "Starting Moltbot Gateway..." -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectDir
pnpm moltbot gateway --verbose
