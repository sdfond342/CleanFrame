# Sign with the official Tizen CLI on Windows. Does not install, launch, or query a TV.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:CLEANFRAME_REQUIRE_OWN_IDENTITY = '1'

function Invoke-CleanFramePython {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PythonArgs)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -B @PythonArgs
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -B @PythonArgs
    } else {
        Write-Error 'Python 3.10 or newer was not found on PATH.'
        exit 1
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Invoke-CleanFramePython (Join-Path $PSScriptRoot 'package.py')
Invoke-CleanFramePython (Join-Path $PSScriptRoot 'package.py') --verify (Join-Path (Get-Location) 'dist\CleanFrame.wgt')
