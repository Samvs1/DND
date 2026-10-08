$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Project folder is DnD2. The old v1 project (C:\Users\vanst\Desktop\DnD) is a read-only reference.
$project = "C:\Users\vanst\Desktop\DnD2"
$v1 = "C:\Users\vanst\Desktop\DnD"
Set-Location $project

Write-Host "== keep the PC awake while plugged in ==" -ForegroundColor Cyan
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

Write-Host "`n== git state ==" -ForegroundColor Cyan
git status --short
Write-Host "-- stashes:"
git stash list
Write-Host "-- last commits:"
git log --oneline -3

Write-Host "`n== variable NAMES in .env (values are never printed) ==" -ForegroundColor Cyan
if (Test-Path ".env") {
    Select-String -Path ".env" -Pattern '^[A-Z_]+=' | ForEach-Object { ($_.Line -split '=')[0] }
} else {
    Write-Host "WARNING: .env is missing in $project" -ForegroundColor Red
}

if (Test-Path ".\.venv\Scripts\Activate.ps1") { . ".\.venv\Scripts\Activate.ps1" }

# Put the asset goal on the clipboard so you can paste it after the recovery report.
$goalFile = Join-Path $project "docs\next\GOAL_ASSETS.txt"
if (Test-Path $goalFile) {
    Get-Content $goalFile -Raw | Set-Clipboard
    Write-Host "`nThe /goal text is on your clipboard. Paste it AFTER Claude's recovery report." -ForegroundColor Green
}

$prompt = @'
We were interrupted by a PC shutdown mid-M10 (the project folder is C:\Users\vanst\Desktop\DnD2; C:\Users\vanst\Desktop\DnD is the old v1 read-only reference). Before anything else: run git status and git stash list, read PROGRESS.md and CLAUDE.md. If there are uncommitted or half-written files, either finish them if clearly complete or restore them with git checkout and redo that checkpoint from NEXT. Run .\scripts\gate.ps1 and show the tail. Fix anything broken before continuing. Report in 5 lines, then wait for my /goal.
'@

Write-Host "`n== launching Claude Code (Sonnet, high effort, auto permissions) ==" -ForegroundColor Cyan
claude --model sonnet --effort high --permission-mode auto --add-dir $v1 $prompt
