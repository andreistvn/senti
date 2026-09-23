<#
.SYNOPSIS
    Writes this machine's primary LAN IPv4 address to a file.

.DESCRIPTION
    Used by the Windows launch scripts so a .bat can read the address back with
    `set /p`. Falls back to a DNS lookup on Windows builds that lack the
    Get-NetIPAddress cmdlet, and to 127.0.0.1 if nothing usable is found.
#>
param(
    [Parameter(Mandatory = $true)][string]$OutFile
)

$lan = '127.0.0.1'

try {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 |
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

Set-Content -Path $OutFile -Value $lan -Encoding ASCII
Write-Output $lan
