<#
.SYNOPSIS
    Checks - or stops - a MultiChain node over HTTP JSON-RPC, without multichain-cli.

.DESCRIPTION
    Called by launch_scripts\start_relay_node.bat and launch_scripts\stop_all.bat.

    Those scripts used to probe the node with `multichain-cli <chain> getinfo`.
    multichain-cli.exe is unsigned, and Windows Smart App Control or an antivirus
    can block it outright - in which case the probe fails even when the node is
    perfectly healthy. start_relay_node.bat read that as "no node is running" and
    started a SECOND multichaind on a chain that already had one, which collides
    on the permissions.db LevelDB lock and dies with "The handle is invalid".

    Nothing in SentiNet needs the CLI. admin-backend\multichain.py talks to the
    node over JSON-RPC with requests, and the RPC credentials are read straight
    out of multichain.conf. This script takes that same path, so if it succeeds
    the relay will be able to reach the node as well - which makes it a more
    honest readiness check than the CLI ever was.

    Written for PowerShell 5.1, the version that ships with Windows - no ternary
    operators, no -SkipHttpErrorCheck, nothing from PowerShell 7.

.PARAMETER ChainDir
    The chain's data directory, e.g. $env:APPDATA\MultiChain\sentinet

.PARAMETER Action
    Ping (default) - succeed if the node answers getinfo.
    Stop           - ask the node to shut down, then wait for it to stop answering.

.PARAMETER TimeoutSeconds
    Per-request timeout. Default 4.

.NOTES
    Exit codes, for `if errorlevel` in the callers:
      0  the node answered (for -Action Stop: it has now shut down)
      1  the node did not answer - down, wrong port, or connection refused
      2  cannot tell: multichain.conf is missing, so the chain has never run
      3  the node answered but rejected the credentials
      4  -Action Stop only: the node was asked to stop and did not

    1 and 4 both mean "no clean shutdown happened", but the callers need to tell
    them apart: 1 is nothing to do, 4 warrants terminating the process.
#>
param(
    [Parameter(Mandatory = $true)][string]$ChainDir,
    [ValidateSet('Ping', 'Stop')][string]$Action = 'Ping',
    [int]$TimeoutSeconds = 4
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Get-ConfValue {
    param([string[]]$Lines, [string]$Key)
    $match = $Lines | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
    if ($null -eq $match) { return '' }
    return ($match -replace "^\s*$Key\s*=\s*", '').Trim()
}

# --- Work out where to connect, exactly as Write-RelayEnv.ps1 does ---------

$confPath = Join-Path $ChainDir 'multichain.conf'
if (-not (Test-Path $confPath)) {
    Write-Host "      Test-ChainRpc: $confPath not found - the chain has never been initialised."
    exit 2
}

$conf = Get-Content $confPath
$rpcUser = Get-ConfValue -Lines $conf -Key 'rpcuser'
$rpcPassword = Get-ConfValue -Lines $conf -Key 'rpcpassword'
$rpcPort = Get-ConfValue -Lines $conf -Key 'rpcport'

# The port usually lives in params.dat as 'default-rpc-port = 4365  # comment',
# so take the first number on the line rather than stripping all non-digits -
# otherwise the digits in the trailing comment get glued onto the port.
if ([string]::IsNullOrWhiteSpace($rpcPort)) {
    $paramsPath = Join-Path $ChainDir 'params.dat'
    if (Test-Path $paramsPath) {
        $line = Get-Content $paramsPath |
                Where-Object { $_ -match '^\s*default-rpc-port\s*=' } |
                Select-Object -First 1
        if ($line -match '=\s*(\d+)') { $rpcPort = $Matches[1] }
    }
}

if ([string]::IsNullOrWhiteSpace($rpcUser)) { $rpcUser = 'multichainrpc' }
if ([string]::IsNullOrWhiteSpace($rpcPort)) { $rpcPort = '4365' }

$uri = "http://127.0.0.1:$rpcPort"
$pair = "{0}:{1}" -f $rpcUser, $rpcPassword
$headers = @{
    Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
}

# --- One JSON-RPC call ------------------------------------------------------

function Invoke-Rpc {
    param([string]$Method)

    $body = @{ method = $Method; params = @(); id = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
    return Invoke-RestMethod -Uri $uri -Method Post -Headers $headers `
                             -ContentType 'application/json' -Body $body `
                             -TimeoutSec $TimeoutSeconds
}

function Get-HttpStatus {
    param($ErrorRecord)
    try {
        $response = $ErrorRecord.Exception.Response
        if ($null -ne $response) { return [int]$response.StatusCode }
    } catch { }
    return 0
}

# --- Ping -------------------------------------------------------------------

try {
    $info = Invoke-Rpc -Method 'getinfo'
    $result = $info.result
    if ($null -ne $result) {
        Write-Host ("      Test-ChainRpc: node answering on {0} (version {1}, {2} blocks)." -f `
                    $uri, $result.version, $result.blocks)
    } else {
        Write-Host "      Test-ChainRpc: node answering on $uri."
    }
} catch {
    $status = Get-HttpStatus -ErrorRecord $_
    if ($status -eq 401) {
        Write-Host "      Test-ChainRpc: node is up on $uri but rejected rpcuser '$rpcUser'."
        Write-Host "      Test-ChainRpc: the credentials in multichain.conf do not match the running node."
        exit 3
    }
    Write-Host "      Test-ChainRpc: no answer from $uri - $($_.Exception.Message)"
    exit 1
}

if ($Action -eq 'Ping') { exit 0 }

# --- Stop -------------------------------------------------------------------

try {
    Invoke-Rpc -Method 'stop' | Out-Null
} catch {
    # The node often drops the connection while answering 'stop', which surfaces
    # as a transport error rather than a response. That is not a failure, so fall
    # through to the wait below and judge by whether it actually stopped.
    Write-Host "      Test-ChainRpc: stop request returned $($_.Exception.Message) - verifying."
}

Write-Host '      Test-ChainRpc: waiting for the node to flush and exit...'
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-Rpc -Method 'getinfo' | Out-Null
    } catch {
        if ((Get-HttpStatus -ErrorRecord $_) -ne 401) {
            Write-Host '      Test-ChainRpc: node has shut down.'
            exit 0
        }
    }
}

Write-Host '      Test-ChainRpc: node is still answering after 15s.'
exit 4
