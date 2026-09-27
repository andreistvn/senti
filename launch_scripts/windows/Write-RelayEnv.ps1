<#
.SYNOPSIS
    Generates admin-backend\.env from a live MultiChain node's RPC credentials.

.DESCRIPTION
    Called by launch_scripts\start_relay_node.bat. This lives in its own .ps1
    rather than being embedded in the .bat because cmd.exe's rules for escaping
    pipes and quotes inside a multi-line `powershell -Command` block are
    error-prone: whether `|` needs a caret depends on quote state, and getting it
    wrong fails at runtime on the teammate's machine rather than here.

    Reads rpcuser/rpcpassword from multichain.conf and the RPC port from either
    multichain.conf (rpcport) or params.dat (default-rpc-port), then rewrites the
    relevant keys in .env, preserving everything else in the file.

    Also writes admin-dashboard\.env.local, because the dashboard's API calls
    resolve in the viewer's browser: left pointing at localhost, opening it from
    another machine would make that browser call its own localhost and fail.

.PARAMETER ChainDir
    The chain's data directory, e.g. $env:APPDATA\MultiChain\sentinet

.PARAMETER RepoRoot
    Repository root containing admin-backend\ and admin-dashboard\

.PARAMETER BindHost
    Address the relay API binds to. 0.0.0.0 so agent machines can connect.

.PARAMETER MultiChainEnabled
    "true" or "false" - written to MULTICHAIN_ENABLED.

.PARAMETER LanIpOutFile
    File to write the detected LAN IP into, for the calling .bat to read back.
#>
param(
    [Parameter(Mandatory = $true)][string]$ChainDir,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [string]$BindHost = '0.0.0.0',
    [string]$MultiChainEnabled = 'true',
    [string]$LanIpOutFile = ''
)

$ErrorActionPreference = 'Stop'

function Get-ConfValue {
    param([string[]]$Lines, [string]$Key)
    $match = $Lines | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
    if ($null -eq $match) { return '' }
    return ($match -replace "^\s*$Key\s*=\s*", '').Trim()
}

# --- Read the node's credentials ------------------------------------------

$rpcUser = 'multichainrpc'
$rpcPassword = 'unused-no-node'
$rpcPort = '4365'

if ($MultiChainEnabled -eq 'true') {
    $confPath = Join-Path $ChainDir 'multichain.conf'
    if (-not (Test-Path $confPath)) {
        Write-Host "ERROR: $confPath not found - is the chain initialised?"
        exit 1
    }

    $conf = Get-Content $confPath
    $rpcUser = Get-ConfValue -Lines $conf -Key 'rpcuser'
    $rpcPassword = Get-ConfValue -Lines $conf -Key 'rpcpassword'
    $rpcPort = Get-ConfValue -Lines $conf -Key 'rpcport'

    # The port usually lives in params.dat as 'default-rpc-port = 4365  # comment'
    if ([string]::IsNullOrWhiteSpace($rpcPort)) {
        $paramsPath = Join-Path $ChainDir 'params.dat'
        if (Test-Path $paramsPath) {
            $line = Get-Content $paramsPath |
                    Where-Object { $_ -match '^\s*default-rpc-port\s*=' } |
                    Select-Object -First 1
            if ($line -match '(\d+)') { $rpcPort = $Matches[1] }
        }
    }

    if ([string]::IsNullOrWhiteSpace($rpcUser)) { $rpcUser = 'multichainrpc' }
    if ([string]::IsNullOrWhiteSpace($rpcPort)) { $rpcPort = '4365' }

    if ([string]::IsNullOrWhiteSpace($rpcPassword)) {
        Write-Host "ERROR: could not read rpcpassword from $confPath"
        exit 1
    }

    Write-Host "      rpcuser=$rpcUser  rpcport=$rpcPort  rpcpassword=<hidden>"
}

# --- Detect this machine's LAN address ------------------------------------

# Ask the OS which source address it would actually use to reach the internet,
# i.e. the interface holding the default route. Taking the first entry from
# Get-NetIPAddress instead returns roughly interface-index order, which on a
# machine with VirtualBox/VMware/Hyper-V/WSL routinely picks a virtual adapter
# (192.168.56.1 and friends) that no other device can reach — the agents then
# get an address that can never work.
$lan = '127.0.0.1'
try {
    $route = Find-NetRoute -RemoteIPAddress '8.8.8.8' -ErrorAction Stop |
             Where-Object { $_.IPAddress -and $_.IPAddress -ne '127.0.0.1' } |
             Select-Object -First 1
    if ($route -and $route.IPAddress) { $lan = $route.IPAddress }
} catch { }

if ($lan -eq '127.0.0.1') {
    try {
        $idx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
                Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex
        if ($idx) {
            $ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $idx -ErrorAction Stop |
                   Where-Object { $_.IPAddress -ne '127.0.0.1' } |
                   Select-Object -First 1).IPAddress
            if ($ip) { $lan = $ip }
        }
    } catch { }
}

if ($lan -eq '127.0.0.1') {
    try {
        $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                     Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' } |
                     Select-Object -First 1
        if ($candidate -and $candidate.IPAddress) { $lan = $candidate.IPAddress }
    } catch {
        try {
            $ips = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
                   Where-Object { $_.AddressFamily -eq 'InterNetwork' -and $_.IPAddressToString -ne '127.0.0.1' }
            if ($ips) { $lan = $ips[0].IPAddressToString }
        } catch { }
    }
}

# Surface the alternatives so a wrong pick is visible on screen.
try {
    $others = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
              Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -ne $lan } |
              ForEach-Object { "$($_.IPAddress) ($($_.InterfaceAlias))" }
    if ($others) {
        Write-Host "      Other addresses on this machine: $($others -join ', ')"
        Write-Host '      Agents must use an address on THEIR subnet.'
    }
} catch { }

# --- Rewrite admin-backend\.env -------------------------------------------

$envFile = Join-Path $RepoRoot 'admin-backend\.env'
$envExample = Join-Path $RepoRoot 'admin-backend\.env.example'

if (-not (Test-Path $envExample)) {
    Write-Host "ERROR: $envExample not found."
    exit 1
}

if (Test-Path $envFile) {
    Copy-Item $envFile "$envFile.bak" -Force
    Write-Host '      Existing .env backed up to .env.bak'
}
Copy-Item $envExample $envFile -Force

$corsOrigins = @(
    'http://localhost:5175', 'http://127.0.0.1:5175',
    'http://localhost:5173', 'http://127.0.0.1:5173',
    "http://${lan}:5175", "http://${lan}:5173"
) -join ','

$updates = [ordered]@{
    'ADMIN_API_HOST'          = $BindHost
    'MULTICHAIN_ENABLED'      = $MultiChainEnabled
    'MULTICHAIN_RPC_URL'      = "http://127.0.0.1:$rpcPort"
    'MULTICHAIN_RPC_USER'     = $rpcUser
    'MULTICHAIN_RPC_PASSWORD' = $rpcPassword
    'ADMIN_CORS_ORIGINS'      = $corsOrigins
}

$lines = @(Get-Content $envFile)
$seen = @{}

for ($i = 0; $i -lt $lines.Count; $i++) {
    $trimmed = $lines[$i].Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
    if ($trimmed.StartsWith('#')) { continue }
    if (-not $trimmed.Contains('=')) { continue }

    $key = $trimmed.Split('=')[0].Trim()
    if ($updates.Contains($key)) {
        $lines[$i] = "$key=$($updates[$key])"
        $seen[$key] = $true
    }
}

$extra = @()
foreach ($key in $updates.Keys) {
    if (-not $seen.ContainsKey($key)) { $extra += "$key=$($updates[$key])" }
}
if ($extra.Count -gt 0) {
    $lines += ''
    $lines += '# Written by launch_scripts\start_relay_node.bat'
    $lines += $extra
}

Set-Content -Path $envFile -Value $lines -Encoding ASCII
Write-Host "      Wrote $envFile"

# --- Point the dashboard at this machine ----------------------------------

# The dashboard calls its own origin; Vite proxies the API paths through to the
# backend (see admin-dashboard/vite.config.ts). Pointing the browser straight at
# the API on another host makes the request cross-site, so the SameSite=Lax
# session cookie is dropped and login bounces back to the login screen.
$dashDir = Join-Path $RepoRoot 'admin-dashboard'
if (Test-Path $dashDir) {
    $dashEnv = Join-Path $dashDir '.env.local'
    Set-Content -Path $dashEnv -Value 'VITE_ADMIN_API_BASE_URL=' -Encoding ASCII
    Write-Host '      Dashboard API: same-origin (proxied by Vite to 127.0.0.1:8771)'
}

# --- Hand the LAN IP back to the caller -----------------------------------

if (-not [string]::IsNullOrWhiteSpace($LanIpOutFile)) {
    Set-Content -Path $LanIpOutFile -Value $lan -Encoding ASCII
}

exit 0
