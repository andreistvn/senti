<#
.SYNOPSIS
    Writes this machine's primary LAN IPv4 address to a file.

.DESCRIPTION
    Used by the Windows launch scripts so a .bat can read the address back with
    `set /p`.

    This used to take the first entry from Get-NetIPAddress, which is roughly
    interface-index order and NOT sorted by usefulness — on a machine with
    VirtualBox, VMware, Hyper-V or WSL installed it frequently returned a
    virtual adapter (e.g. 192.168.56.1) that no other device on the network can
    reach. The agents were then handed an address that could never work.

    It now asks the OS which source address it would actually use to reach the
    internet, which is the interface holding the default route — the same
    semantics as the Mac/Linux path, which connects a UDP socket to 8.8.8.8 and
    reads back the local endpoint.

    Every candidate address is also reported, so a wrong pick is visible rather
    than silently written into .env.
#>
param(
    [Parameter(Mandatory = $true)][string]$OutFile
)

function Get-PrimaryIPv4 {
    # 1. The address the OS would use to reach a public host. Most reliable.
    try {
        $route = Find-NetRoute -RemoteIPAddress '8.8.8.8' -ErrorAction Stop |
                 Where-Object { $_.IPAddress -and $_.IPAddress -ne '127.0.0.1' } |
                 Select-Object -First 1
        if ($route -and $route.IPAddress) { return $route.IPAddress }
    } catch { }

    # 2. Failing that, the lowest-metric default route's interface.
    try {
        $idx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
                Sort-Object RouteMetric |
                Select-Object -First 1).InterfaceIndex
        if ($idx) {
            $ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $idx -ErrorAction Stop |
                   Where-Object { $_.IPAddress -ne '127.0.0.1' } |
                   Select-Object -First 1).IPAddress
            if ($ip) { return $ip }
        }
    } catch { }

    # 3. Old behaviour, kept only so this never returns nothing at all.
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
               Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' } |
               Select-Object -First 1).IPAddress
        if ($ip) { return $ip }
    } catch { }

    # 4. Very old Windows without the Net cmdlets.
    try {
        $ips = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
               Where-Object { $_.AddressFamily -eq 'InterNetwork' -and $_.IPAddressToString -ne '127.0.0.1' }
        if ($ips) { return $ips[0].IPAddressToString }
    } catch { }

    return '127.0.0.1'
}

$lan = Get-PrimaryIPv4

# Report the alternatives. A machine has one address per interface and DHCP
# leases move, so "the IP" is genuinely ambiguous — showing the others turns a
# wrong pick into something you can see instead of debug.
try {
    $others = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
              Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -ne $lan } |
              ForEach-Object {
                  $alias = $_.InterfaceAlias
                  "$($_.IPAddress) ($alias)"
              }
    if ($others) {
        Write-Host "      Other addresses on this machine: $($others -join ', ')"
        Write-Host '      Agents must use an address on THEIR subnet.'
    }
} catch { }

Set-Content -Path $OutFile -Value $lan -Encoding ASCII
Write-Output $lan
