param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$InstallDeps,
    [switch]$CheckOnly
)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    $ecgPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $ecgPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -m venv .venv
        } else {
            & python -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required." }
    }
    $ecgArguments = @("deploy/local.py", "--host", $BindHost, "--port", "$Port")
    if ($InstallDeps) { $ecgArguments += "--install" }
    if ($CheckOnly) { $ecgArguments += "--check" }
    & $ecgPython @ecgArguments
    if ($LASTEXITCODE -ne 0) { throw "Local deployment exited with code $LASTEXITCODE." }
} finally {
    Pop-Location
}
