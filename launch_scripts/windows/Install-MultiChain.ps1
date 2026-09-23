<#
.SYNOPSIS
    Downloads and installs MultiChain for Windows, then verifies it runs.

.DESCRIPTION
    Called by launch_scripts\setup_windows_relay.bat.

    The Windows archive has NO top-level folder: multichaind.exe,
    multichain-cli.exe, multichain-util.exe and multichain-v8.dll all sit at the
    archive root and must stay in the same directory, so this extracts straight
    into the destination rather than moving individual files out of a temp dir.

.PARAMETER Destination
    Directory to install into, e.g. $env:LOCALAPPDATA\SentiNet\multichain

.PARAMETER Version
    MultiChain version to fetch.
#>
param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [string]$Version = '2.3.3'
)

$ErrorActionPreference = 'Stop'

$url = "https://www.multichain.com/download/multichain-windows-$Version.zip"
$zip = Join-Path $env:TEMP "multichain-windows-$Version.zip"

try {
    if (-not (Test-Path $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    # Some Windows builds still default to TLS 1.0, which multichain.com rejects.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Write-Host "      Downloading $url"
    # Progress rendering makes Invoke-WebRequest dramatically slower.
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

    $sizeMb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host "      Downloaded $sizeMb MB"

    if ((Get-Item $zip).Length -lt 1MB) {
        throw "downloaded file is only $sizeMb MB - expected ~19 MB. A proxy or captive portal may have intercepted the request."
    }

    Write-Host "      Extracting to $Destination"
    Expand-Archive -Path $zip -DestinationPath $Destination -Force
    Remove-Item $zip -Force

    # The DLL is required alongside the executables; its absence means a partial
    # or wrong archive, which would otherwise surface as a cryptic startup crash.
    foreach ($required in @('multichaind.exe', 'multichain-cli.exe', 'multichain-util.exe', 'multichain-v8.dll')) {
        $path = Join-Path $Destination $required
        if (-not (Test-Path $path)) {
            throw "expected file missing after extraction: $required"
        }
    }

    Write-Host '      All expected files present.'
    exit 0
}
catch {
    Write-Host "      ERROR: $($_.Exception.Message)"
    if (Test-Path $zip) { Remove-Item $zip -Force -ErrorAction SilentlyContinue }
    exit 1
}
