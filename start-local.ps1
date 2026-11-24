param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$InstallDeps,
    [switch]$CheckOnly,
    [string]$VenvPath = ""
)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if (-not $VenvPath) {
        $VenvPath = Join-Path $PSScriptRoot ".venv"
        # PyTorch wheels contain deeply nested license paths. Keep the full
        # install below Windows MAX_PATH without requiring administrator changes.
        if ($VenvPath.Length -gt 85) {
            $ecgHasher = [System.Security.Cryptography.SHA256]::Create()
            try {
                $ecgKey = [BitConverter]::ToString($ecgHasher.ComputeHash(
                    [Text.Encoding]::UTF8.GetBytes($PSScriptRoot.ToLowerInvariant())
                )).Replace("-", "").Substring(0, 12)
            } finally { $ecgHasher.Dispose() }
            $VenvPath = Join-Path $env:LOCALAPPDATA "ECG-AI\venvs\$ecgKey"
        }
    }
    $VenvPath = [IO.Path]::GetFullPath($VenvPath)
    if ($VenvPath.Length -gt 85) { throw "Use -VenvPath with a shorter absolute path (85 characters or less)." }
    $ecgPython = Join-Path $VenvPath "Scripts\python.exe"
    Write-Host "Python environment: $VenvPath"
    if (-not (Test-Path -LiteralPath $ecgPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -m venv $VenvPath
        } else {
            & python -m venv $VenvPath
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
