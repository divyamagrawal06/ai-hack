param(
    [string]$RuntimeRoot = (Join-Path $PSScriptRoot '..\var\local-ai'),
    [string]$Model = '',
    [switch]$SkipModel
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$Endpoint = python -c "import sys; sys.path.insert(0, sys.argv[1]); from clinic.assessors import _local_endpoint; print(_local_endpoint())" $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'Set CLINIC_OLLAMA_URL to a valid loopback HTTP address before installing.' }
if (-not $Model) {
    $Model = if ($env:CLINIC_LOCAL_MODEL) { $env:CLINIC_LOCAL_MODEL } else { 'qwen3:4b-instruct' }
}
if ($Model -match 'cloud') { throw 'Choose a local model. Cloud inference is disabled for this setup.' }
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$OllamaDirectory = Join-Path $RuntimeRoot 'ollama'
$ModelsDirectory = Join-Path $RuntimeRoot 'models'
New-Item -ItemType Directory -Force $RuntimeRoot, $ModelsDirectory | Out-Null

python (Join-Path $PSScriptRoot 'install_ollama_runtime.py') $OllamaDirectory
if ($LASTEXITCODE -ne 0) { throw 'Ollama runtime installation failed.' }
$OllamaExe = Join-Path $OllamaDirectory 'ollama.exe'
$Signature = Get-AuthenticodeSignature -LiteralPath $OllamaExe
if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'O=Ollama Inc\.') {
    throw 'The Ollama executable does not have a valid Ollama Inc. signature.'
}

# Environment is scoped to this process and the hidden child; no user-wide changes.
$env:OLLAMA_HOST = $Endpoint
$env:OLLAMA_MODELS = $ModelsDirectory
$env:OLLAMA_VULKAN = '1'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_KEEP_ALIVE = '30m'
$AlreadyRunning = $false
try {
    $null = Invoke-RestMethod "$Endpoint/api/version" -TimeoutSec 2
    $AlreadyRunning = $true
} catch {}
if ($AlreadyRunning) {
    Write-Host "Using the existing Ollama server at $Endpoint (its configured model storage is retained)."
} else {
    $ServerProcess = Start-Process -FilePath $OllamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RuntimeRoot 'ollama-out.log') `
        -RedirectStandardError (Join-Path $RuntimeRoot 'ollama-err.log')
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        try {
            $null = Invoke-RestMethod "$Endpoint/api/version" -TimeoutSec 2
            $Ready = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $Ready) { throw "Ollama did not start. Check $RuntimeRoot\ollama-err.log" }
    $ServerProcess.Id | Set-Content (Join-Path $RuntimeRoot 'ollama.pid')
}
if (-not $SkipModel) {
    Write-Host "Downloading $Model (about 2.5 GB for the default model)..."
    & $OllamaExe pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed; rerun this script to resume.' }
}
if ($SkipModel) {
    Write-Host "Ollama runtime is ready at $Endpoint. Model installation was skipped."
} else {
    Write-Host "Local AI model $Model is installed at $Endpoint."
}
Write-Host 'Start CareRoute with: python tools/start_demo.py'
