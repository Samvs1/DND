# Full gate: runs the 12 gates in order, prints the tail of each and PASS/FAIL.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\gate.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venv = Join-Path $root '.venv\Scripts'
$py = Join-Path $venv 'python.exe'
$ruff = Join-Path $venv 'ruff.exe'
$pyright = Join-Path $venv 'pyright.exe'
$lint = Join-Path $venv 'lint-imports.exe'
$uiBatch = 8 # UI test files per pytest process

# pytest runs as one process per test folder and the UI tests in batches of files: one process for
# the whole suite runs out of memory on this machine. Folders are found, not listed, so a new one
# is never left out; the step passes only when every batch passes.
function Get-PytestRuns {
    $tests = Join-Path $root 'tests'
    $runs = @()
    foreach ($dir in Get-ChildItem $tests -Directory | Sort-Object Name) {
        $files = @(Get-ChildItem $dir.FullName -Recurse -Filter 'test_*.py' | Sort-Object FullName | ForEach-Object { Resolve-Path -Relative $_.FullName })
        if ($files.Count -eq 0) { continue }
        if ($dir.Name -ne 'ui') {
            $runs += '-m pytest -q ' + (Resolve-Path -Relative $dir.FullName)
            continue
        }
        for ($i = 0; $i -lt $files.Count; $i += $uiBatch) {
            $last = [math]::Min($i + $uiBatch, $files.Count) - 1
            $runs += '-m pytest -q ' + ($files[$i..$last] -join ' ')
        }
    }
    $loose = @(Get-ChildItem $tests -File -Filter 'test_*.py' | ForEach-Object { Resolve-Path -Relative $_.FullName })
    if ($loose.Count -gt 0) { $runs += '-m pytest -q ' + ($loose -join ' ') }
    return $runs
}

$gates = @(
    @{ Name = 'pytest';           Exe = $py;      Runs = @(Get-PytestRuns) },
    @{ Name = 'ruff check';       Exe = $ruff;    Args = 'check .' },
    @{ Name = 'ruff format';      Exe = $ruff;    Args = 'format --check .' },
    @{ Name = 'pyright';          Exe = $pyright; Args = '' },
    @{ Name = 'lint-imports';     Exe = $lint;    Args = '' },
    @{ Name = 'check_structure';  Exe = $py;      Args = 'scripts/check_structure.py' },
    @{ Name = 'check_secrets';    Exe = $py;      Args = 'scripts/check_secrets.py' },
    @{ Name = 'gen_protocol';     Exe = $py;      Args = 'scripts/gen_protocol.py --check' },
    @{ Name = 'build_manifest';   Exe = $py;      Args = 'scripts/build_manifest.py --check' },
    @{ Name = 'gen_assets_todo';  Exe = $py;      Args = 'scripts/gen_assets_todo.py --check' },
    @{ Name = 'scribe_voice';     Exe = $py;      Args = 'scripts/gen_scribe_voice.py --check' },
    @{ Name = 'gen_manual';       Exe = $py;      Args = 'scripts/gen_manual.py --check' }
)

$failed = @()
foreach ($g in $gates) {
    Write-Output "== $($g.Name) =="
    $runs = if ($g.Runs) { $g.Runs } else { @($g.Args) }
    $ok = $true
    foreach ($run in $runs) {
        $cmd = "`"$($g.Exe)`" $run 2>&1"
        $lines = @(cmd /c $cmd | ForEach-Object { "$_" })
        $code = $LASTEXITCODE
        if ($runs.Count -gt 1) {
            Write-Output "-- $run"
            $tail = if ($code -eq 0) { 1 } else { 15 }
        } else {
            $tail = 8
        }
        $lines | Select-Object -Last $tail | ForEach-Object { Write-Output $_ }
        if ($code -ne 0) { $ok = $false }
    }
    if ($ok) {
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
