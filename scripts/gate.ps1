# Full gate: runs the 8 gates in order, prints the tail of each and PASS/FAIL.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\gate.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venv = Join-Path $root '.venv\Scripts'
$py = Join-Path $venv 'python.exe'
$ruff = Join-Path $venv 'ruff.exe'
$pyright = Join-Path $venv 'pyright.exe'
$lint = Join-Path $venv 'lint-imports.exe'

$gates = @(
    @{ Name = 'pytest';           Exe = $py;      Args = '-m pytest -q' },
    @{ Name = 'ruff check';       Exe = $ruff;    Args = 'check .' },
    @{ Name = 'ruff format';      Exe = $ruff;    Args = 'format --check .' },
    @{ Name = 'pyright';          Exe = $pyright; Args = '' },
    @{ Name = 'lint-imports';     Exe = $lint;    Args = '' },
    @{ Name = 'check_structure';  Exe = $py;      Args = 'scripts/check_structure.py' },
    @{ Name = 'check_secrets';    Exe = $py;      Args = 'scripts/check_secrets.py' },
    @{ Name = 'gen_protocol';     Exe = $py;      Args = 'scripts/gen_protocol.py --check' }
)

$failed = @()
foreach ($g in $gates) {
    Write-Output "== $($g.Name) =="
    $cmd = "`"$($g.Exe)`" $($g.Args) 2>&1"
    $lines = @(cmd /c $cmd | ForEach-Object { "$_" })
    $code = $LASTEXITCODE
    $lines | Select-Object -Last 8 | ForEach-Object { Write-Output $_ }
    if ($code -eq 0) {
        Write-Output 'PASS'
    } else {
        Write-Output 'FAIL'
        $failed += $g.Name
    }
}

$total = $gates.Count
if ($failed.Count -eq 0) {
    Write-Output "GATE: PASS ($total/$total)"
    exit 0
}
Write-Output "GATE: FAIL ($($failed.Count) failed: $($failed -join ', '))"
exit 1
