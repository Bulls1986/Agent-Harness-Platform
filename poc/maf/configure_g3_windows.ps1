# Configure G3 provider credential locally; never pass it in CLI or commit it.
# Launch interactively from Windows PowerShell / pwsh in the local machine.
# The User environment is a convenience, NOT an encrypted secret vault.
param([switch] $ConfigureOnly)
$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") { throw "Windows local runner required." }

$keyName = "POC_LITELLM_API_KEY"
$current = [Environment]::GetEnvironmentVariable($keyName, "User")
if ([string]::IsNullOrWhiteSpace($current)) {
    Write-Host "The LiteLLM key will be stored in your Windows User environment."
    Write-Host "Warning: Windows User environment values are not encrypted secrets."
    $secret = Read-Host "Paste LiteLLM API Key (input hidden)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        if ([string]::IsNullOrWhiteSpace($value)) { throw "API Key cannot be empty." }
        [Environment]::SetEnvironmentVariable($keyName, $value, "User")
        $env:POC_LITELLM_API_KEY = $value
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        Remove-Variable -Name value,secret -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "Existing Windows User LiteLLM environment credential will be reused."
    $env:POC_LITELLM_API_KEY = $current
}
# Read the nonsecret variables already configured under the current Windows
# User environment; this PowerShell instance need not have inherited them.
foreach ($name in @("POC_LITELLM_BASE_URL", "POC_LITELLM_MODEL")) {
    $value = [Environment]::GetEnvironmentVariable($name, "User")
    if ([string]::IsNullOrWhiteSpace($value)) { throw "Configure $name first." }
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
}
Write-Host "G3 Windows User environment: model/base URL/key configured (values hidden)."
if (-not $ConfigureOnly) {
    $python = Join-Path $env:TEMP "agent-harness-g3-venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Pinned Python environment missing. See poc/maf/README.md."
    }
    $repo = Resolve-Path (Join-Path $PSScriptRoot "../..")
    Push-Location $repo
    try {
        & $python "poc/maf/run_live_g3_local.py"
        if ($LASTEXITCODE -ne 0) {
            throw "G3 live acceptance did not pass; review redacted gate output."
        }
    } finally {
        Pop-Location
        Remove-Item Env:\POC_LITELLM_API_KEY -ErrorAction SilentlyContinue
    }
}
