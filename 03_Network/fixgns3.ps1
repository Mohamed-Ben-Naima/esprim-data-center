<#
.SYNOPSIS
    Repairs a GNS3 VM (VMware) that GNS3 cannot reach ("Cannot connect to host unknown:80"),
    fixes the VM's Docker setup, and optionally re-targets a project to run on the GNS3 VM.

.DESCRIPTION
    Everything is auto-discovered on the PC it runs on (nothing is hard-coded to one machine):
      1. Reads the GNS3 config (%APPDATA%\GNS3\<ver>) and finds the GNS3 VM .vmx and vmrun.exe.
      2. Maps each VM NIC to its host VMware network (VMnet1 host-only, VMnet8 NAT, ...) and checks
         whether host DHCP is enabled there.
      3. Inside the VM (through VMware Tools / vmrun, no SSH needed) writes a netplan file that matches
         the host networks: DHCP where the host offers DHCP, otherwise a static IP in the host subnet
         (default .128) with the NAT gateway as default route. Stale static configs are backed up.
      4. Fixes Docker: restarts dockerd so it picks up the new DNS, then pulls every Docker image used
         by your GNS3 templates and projects.
      5. Uses the GNS3 controller API to enable the GNS3 VM with the full settings and re-detect its IP
         (this power-cycles the VM). Falls back to editing gns3_controller.ini if GNS3 is not running.
      6. Optional -ProjectFile: moves nodes from compute "local" to "vm", fills empty qemu_path and
         reports disk images the VM does not have.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\fixgns3.ps1 -DryRun
    powershell -ExecutionPolicy Bypass -File .\fixgns3.ps1
    powershell -ExecutionPolicy Bypass -File .\fixgns3.ps1 -ProjectFile "C:\path\MyLab.gns3"
    powershell -ExecutionPolicy Bypass -File .\fixgns3.ps1 -VmxPath "H:\GNS3 VM\GNS3 VM.vmx" -GuestPassword gns3
#>
[CmdletBinding()]
param(
    [string]   $VmxPath,                       # auto-detected from GNS3 settings + VMware inventory
    [string]   $GuestUser     = "gns3",
    [string]   $GuestPassword = "gns3",
    [int]      $HostOctet     = 128,           # host part used for static IPs (x.x.x.128)
    [string[]] $ProjectFile   = @(),           # .gns3 files to re-target to the GNS3 VM
    [string[]] $ExtraImages   = @(),           # extra docker images to pull
    [switch]   $SkipDocker,
    [switch]   $SkipApiRestart,
    [switch]   $DryRun                         # discover + diagnose only, change nothing
)

$ErrorActionPreference = "Stop"
$ts      = Get-Date -Format "yyyyMMdd-HHmmss"
$workDir = Join-Path $env:TEMP "fixgns3-$ts"
New-Item -ItemType Directory -Force $workDir | Out-Null
Start-Transcript -Path (Join-Path $workDir "fixgns3.log") | Out-Null

function Step($m) { Write-Host "`n=== $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Info($m) { Write-Host "  $m" }
function Die($m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }

function IpToUInt([string]$ip) { $b = ([Net.IPAddress]$ip).GetAddressBytes(); [Array]::Reverse($b); [BitConverter]::ToUInt32($b, 0) }
function UIntToIp([uint32]$n)  { $b = [BitConverter]::GetBytes($n); [Array]::Reverse($b); ([Net.IPAddress]$b).ToString() }
function PrefixToMask([int]$p) { if ($p -eq 0) { return [uint32]0 }; [uint32]([math]::Pow(2, 32) - [math]::Pow(2, 32 - $p)) }
function MaskToPrefix([string]$m) { $n = IpToUInt $m; $c = 0; for ($i = 0; $i -lt 32; $i++) { if ($n -band ([uint32]1 -shl $i)) { $c++ } }; $c }
function WriteLf([string]$path, [string]$text) { [IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false))) }
function WriteJson([string]$path, $obj) { [IO.File]::WriteAllText($path, (ConvertTo-Json -InputObject $obj -Depth 100), (New-Object Text.UTF8Encoding($false))) }

# ------------------------------------------------------------------ 1. GNS3 + VMware discovery
Step "Discovering GNS3 and VMware"

$cfgDir = Get-ChildItem (Join-Path $env:APPDATA "GNS3") -Directory -ErrorAction SilentlyContinue |
          Where-Object { Test-Path (Join-Path $_.FullName "gns3_controller.ini") } |
          Sort-Object { try { [version]($_.Name + ".0") } catch { [version]"0.0" } } | Select-Object -Last 1
if (-not $cfgDir) { Die "GNS3 config not found under $env:APPDATA\GNS3 (run GNS3 once first)." }
$controllerIni = Join-Path $cfgDir.FullName "gns3_controller.ini"
$serverIni     = Join-Path $cfgDir.FullName "gns3_server.ini"
$guiIni        = Join-Path $cfgDir.FullName "gns3_gui.ini"
Ok "GNS3 config: $($cfgDir.FullName)"

$controller = Get-Content $controllerIni -Raw | ConvertFrom-Json
$vmSettings = $controller.gns3vm
$vmName     = if ($vmSettings -and $vmSettings.vmname) { $vmSettings.vmname } else { "GNS3 VM" }

$server = @{}
if (Test-Path $serverIni) {
    foreach ($l in Get-Content $serverIni) { if ($l -match '^\s*([^#;=\s][^=]*?)\s*=\s*(.*?)\s*$') { $server[$Matches[1]] = $Matches[2] } }
}
$apiHost = if ($server["host"] -and $server["host"] -ne "0.0.0.0") { $server["host"] } else { "127.0.0.1" }
$apiPort = if ($server["port"]) { $server["port"] } else { "3080" }
$api     = "http://${apiHost}:$apiPort/v2"
$headers = @{}
if ($server["auth"] -eq "True" -and $server["user"]) {
    $headers["Authorization"] = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($server['user']):$($server['password'])"))
}

$hostType = "ws"
if (Test-Path $guiIni) { $m = Select-String $guiIni -Pattern '"host_type":\s*"(\w+)"' | Select-Object -First 1; if ($m) { $hostType = $m.Matches[0].Groups[1].Value } }

$vmrun = $null
foreach ($k in "HKLM:\SOFTWARE\WOW6432Node\VMware, Inc.\VMware Workstation", "HKLM:\SOFTWARE\VMware, Inc.\VMware Workstation",
               "HKLM:\SOFTWARE\WOW6432Node\VMware, Inc.\VMware Player",      "HKLM:\SOFTWARE\VMware, Inc.\VMware Player") {
    $p = (Get-ItemProperty $k -ErrorAction SilentlyContinue).InstallPath
    if ($p -and (Test-Path (Join-Path $p "vmrun.exe"))) { $vmrun = Join-Path $p "vmrun.exe"; break }
}
if (-not $vmrun) { foreach ($p in "C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe", "C:\Program Files\VMware\VMware Workstation\vmrun.exe", "C:\Program Files (x86)\VMware\VMware VIX\vmrun.exe") { if (Test-Path $p) { $vmrun = $p; break } } }
if (-not $vmrun) { Die "vmrun.exe not found. Is VMware Workstation installed?" }
Ok "vmrun: $vmrun (-T $hostType)"

if (-not $VmxPath) {
    $inv = Join-Path $env:APPDATA "VMware\inventory.vmls"
    if (Test-Path $inv) {
        $cfg = @{}; $disp = @{}
        foreach ($l in Get-Content $inv) {
            if ($l -match '^(vmlist\d+)\.config\s*=\s*"(.*)"')      { $cfg[$Matches[1]]  = $Matches[2] }
            if ($l -match '^(vmlist\d+)\.DisplayName\s*=\s*"(.*)"') { $disp[$Matches[1]] = $Matches[2] }
        }
        foreach ($k in $cfg.Keys) { if ($disp[$k] -eq $vmName -and (Test-Path $cfg[$k])) { $VmxPath = $cfg[$k]; break } }
        if (-not $VmxPath) { foreach ($k in $cfg.Keys) { if ($cfg[$k] -like "*GNS3*VM*.vmx" -and (Test-Path $cfg[$k])) { $VmxPath = $cfg[$k]; break } } }
    }
}
if (-not $VmxPath -or -not (Test-Path $VmxPath)) { Die "GNS3 VM .vmx not found. Re-run with -VmxPath ""X:\...\GNS3 VM.vmx""" }
$VmxPath = (Resolve-Path $VmxPath).Path
Ok "GNS3 VM: $VmxPath"

function VmRun { param([Parameter(ValueFromRemainingArguments = $true)] $a) & $vmrun -T $hostType @a 2>&1 | ForEach-Object { "$_" } }
function Guest { param([Parameter(ValueFromRemainingArguments = $true)] $a) & $vmrun -T $hostType -gu $GuestUser -gp $GuestPassword @a 2>&1 | ForEach-Object { "$_" } }

# ------------------------------------------------------------------ 2. NIC -> host network mapping
Step "Mapping VM network adapters to host VMware networks"

$vmx = @{}
foreach ($l in Get-Content $VmxPath) { if ($l -match '^\s*([^=]+?)\s*=\s*"(.*)"') { $vmx[$Matches[1].ToLower()] = $Matches[2] } }
$dhcpConf = Join-Path $env:ProgramData "VMware\vmnetdhcp.conf"
$natConf  = Join-Path $env:ProgramData "VMware\vmnetnat.conf"
$dhcpText = if (Test-Path $dhcpConf) { Get-Content $dhcpConf -Raw } else { "" }
$natText  = if (Test-Path $natConf)  { Get-Content $natConf -Raw }  else { "" }
$dhcpSvc  = (Get-Service VMnetDHCP -ErrorAction SilentlyContinue).Status -eq "Running"

$currentIp = (VmRun getGuestIPAddress $VmxPath | Select-Object -First 1)
$nics = @()
for ($i = 0; $i -lt 10; $i++) {
    if ($vmx["ethernet$i.present"] -ne "TRUE") { continue }
    $ct = $vmx["ethernet$i.connectiontype"]; if (-not $ct) { $ct = "bridged" }
    $nic = [ordered]@{ Name = "eth$i"; Type = $ct; VmNet = $null; Mode = "dhcp"; Address = $null; Prefix = 24; Gateway = $null; Nat = $false }
    switch ($ct) {
        "hostonly" { $nic.VmNet = 1 }
        "nat"      { $nic.VmNet = 8 }
        "custom"   { if ($vmx["ethernet$i.vnet"] -match '(\d+)$') { $nic.VmNet = [int]$Matches[1] } }
    }
    if ($null -ne $nic.VmNet) {
        $n = $nic.VmNet
        $hostIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                  Where-Object { $_.InterfaceAlias -match "VMnet$n$" } | Select-Object -First 1
        $reg = Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\VMware, Inc.\VMnetLib\VMnetConfig\vmnet$n" -ErrorAction SilentlyContinue
        if ($hostIp) { $net = UIntToIp ([uint32]((IpToUInt $hostIp.IPAddress) -band (PrefixToMask $hostIp.PrefixLength))); $nic.Prefix = $hostIp.PrefixLength }
        elseif ($reg -and $reg.IPSubnetAddress) { $net = $reg.IPSubnetAddress; if ($reg.IPSubnetMask) { $nic.Prefix = MaskToPrefix $reg.IPSubnetMask } }
        else { Warn "eth${i}: cannot determine subnet of VMnet$n, leaving it on DHCP"; $nics += $nic; continue }

        if ($natText -match "(?ms)^\[host\](.*?)(?=^\[|\z)") {
            $sec = $Matches[1]
            if ($sec -match "(?im)^\s*device\s*=\s*vmnet$n\s*$" -and $sec -match "(?im)^\s*ip\s*=\s*([\d.]+)") { $nic.Nat = $true; $nic.Gateway = $Matches[1] }
        }
        if ($n -eq 8 -and -not $nic.Gateway) { $nic.Nat = $true; $nic.Gateway = UIntToIp ((IpToUInt $net) + 2) }

        $hasDhcp = $dhcpSvc -and ($dhcpText -match "subnet\s+$([regex]::Escape($net))\s+netmask")
        if ($hasDhcp) { $nic.Mode = "dhcp" }
        else {
            $nic.Mode = "static"
            $cand = (IpToUInt $net) + $HostOctet
            $myMac = ("" + $vmx["ethernet$i.address"] + $vmx["ethernet$i.generatedaddress"]).Replace(":", "-").ToLower()
            for ($t = 0; $t -lt 30; $t++) {
                $ip = UIntToIp ([uint32]($cand + $t))
                if ($ip -eq $currentIp -or -not (Test-Connection $ip -Count 1 -Quiet -ErrorAction SilentlyContinue)) { $nic.Address = $ip; break }
                # answering already? fine if it is this very NIC (re-run of the script)
                $nb = Get-NetNeighbor -IPAddress $ip -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($nb -and $myMac -and $myMac.Contains($nb.LinkLayerAddress.ToLower())) { $nic.Address = $ip; break }
            }
        }
        $hostDesc = if ($hostIp) { $hostIp.IPAddress } else { "n/a" }
        Info ("eth{0}: {1,-8} VMnet{2,-3} net {3}/{4}  host {5}  hostDHCP={6}  NAT={7}" -f $i, $ct, $n, $net, $nic.Prefix, $hostDesc, $hasDhcp, $nic.Nat)
    } else {
        Info "eth${i}: $ct -> DHCP"
    }
    $nics += $nic
}
if ($nics.Count -eq 0) { Die "No network adapters found in $VmxPath" }
foreach ($nic in $nics) { Ok ("{0} -> {1} {2}" -f $nic.Name, $nic.Mode, $(if ($nic.Address) { "$($nic.Address)/$($nic.Prefix)" + $(if ($nic.Nat) { " gw $($nic.Gateway)" } else { "" }) } else { "" })) }
$mgmtIp = $nics[0].Address
$dnsGw  = ($nics | Where-Object { $_.Nat -and $_.Gateway } | Select-Object -First 1).Gateway

# netplan (90_* overrides the GNS3 VM default 80_* file)
$y = @("# Written by fixgns3.ps1 on $ts - matched to the host VMware networks", "network:", "  version: 2", "  renderer: networkd", "  ethernets:")
$defaultSet = $false
foreach ($nic in $nics) {
    $y += "    $($nic.Name):"
    if ($nic.Mode -eq "static" -and $nic.Address) {
        $y += "      dhcp4: no"
        $y += "      addresses: [$($nic.Address)/$($nic.Prefix)]"
        if ($nic.Nat -and -not $defaultSet) {
            $y += "      routes:", "        - to: 0.0.0.0/0", "          via: $($nic.Gateway)"
            $y += "      nameservers:", "        addresses: [$($nic.Gateway), 8.8.8.8, 1.1.1.1]"
            $defaultSet = $true
        }
    } else {
        $y += "      dhcp4: yes", "      dhcp-identifier: mac"
        if ($nic.Name -ne "eth0") { $y += "      optional: true" }
    }
}
$netplan = ($y -join "`n") + "`n"
Info "netplan to apply:"; $netplan -split "`n" | ForEach-Object { Info "    $_" }

# ------------------------------------------------------------------ 3. docker images to pull
$images = New-Object System.Collections.Generic.List[string]
foreach ($t in $controller.templates) { if ($t.template_type -eq "docker" -and $t.image) { $images.Add($t.image) } }
$projFiles = @($ProjectFile)
if ($server["projects_path"] -and (Test-Path $server["projects_path"])) { $projFiles += (Get-ChildItem $server["projects_path"] -Recurse -Filter *.gns3 -ErrorAction SilentlyContinue).FullName }
foreach ($pf in $projFiles | Where-Object { $_ } | Select-Object -Unique) {
    try { foreach ($n in (Get-Content $pf -Raw | ConvertFrom-Json).topology.nodes) { if ($n.node_type -eq "docker" -and $n.properties.image) { $images.Add($n.properties.image) } } } catch { Warn "Cannot read $pf" }
}
$ExtraImages | Where-Object { $_ } | ForEach-Object { $images.Add($_) }
$images = @($images | Where-Object { $_ -match '^[A-Za-z0-9./:_@-]+$' } | Select-Object -Unique)
if (-not $SkipDocker) { Info "docker images to ensure: $($images -join ', ')" }

# ------------------------------------------------------------------ 4. make sure the VM is running
Step "Checking the GNS3 VM is running"
if (-not ((VmRun list) -contains $VmxPath)) {
    if ($DryRun) { Die "VM is powered off; start it (or run without -DryRun) to diagnose inside it." }
    Info "Starting VM..."; VmRun start $VmxPath | Out-Null
}
$deadline = (Get-Date).AddMinutes(5)
while ((VmRun checkToolsState $VmxPath | Select-Object -Last 1) -ne "running") {
    if ((Get-Date) -gt $deadline) { Die "VMware Tools did not come up in the VM." }
    Start-Sleep 5
}
Ok "VM running, VMware Tools ready (current guest IP: $currentIp)"

# ------------------------------------------------------------------ 5. fix inside the VM
Step $(if ($DryRun) { "Diagnosing inside the VM (dry run)" } else { "Configuring network + Docker inside the VM" })

$pwQ = "'" + $GuestPassword.Replace("'", "'""'""'") + "'"
$guestScript = @'
#!/bin/bash
exec > /tmp/fixgns3.out 2>&1
PW=__PW__
DRY=__DRY__
sud() { echo "$PW" | sudo -S -p '' "$@"; }
echo "### before"; ip -br -4 addr; ip route
for f in /etc/netplan/*.yaml; do echo "--- $f"; sud cat "$f"; done
if [ "$DRY" = "0" ]; then
  TS=$(date +%Y%m%d%H%M%S)
  for f in /etc/netplan/*.yaml; do sud cp "$f" "/root/$(basename "$f").bak.$TS"; done
  # any other netplan file pinning static addresses would merge with ours -> move it aside
  for f in /etc/netplan/*.yaml; do
    [ "$(basename "$f")" = "90_gns3vm_static_netcfg.yaml" ] && continue
    if sud grep -qE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+' "$f"; then sud mv "$f" "/root/$(basename "$f").disabled.$TS"; echo "disabled static netplan $f"; fi
  done
  sud install -m 600 -o root -g root /tmp/fixgns3_netplan.yaml /etc/netplan/90_gns3vm_static_netcfg.yaml
  sud netplan apply
  sleep 10
fi
echo "### after"; ip -br -4 addr; ip route
echo "### connectivity"
[ -n "__GW__" ] && ping -c2 -W2 __GW__
ping -c2 -W2 8.8.8.8
getent hosts registry-1.docker.io | head -2 || echo "DNS FAILED"
curl -s -m 10 -o /dev/null -w "dockerhub HTTP %{http_code} (401 = reachable)\n" https://registry-1.docker.io/v2/
echo "### docker"
if [ -f /etc/docker/daemon.json ] && ! python3 -m json.tool /etc/docker/daemon.json >/dev/null 2>&1; then echo "WARN: /etc/docker/daemon.json is not valid JSON"; fi
if [ "$DRY" = "0" ]; then
  sud systemctl enable docker >/dev/null 2>&1
  sud systemctl restart docker   # pick up new DNS / routes
  sleep 3
fi
echo "docker service: $(systemctl is-active docker)"
sud docker info 2>&1 | grep -E "Server Version|Docker Root Dir|Storage Driver|ERROR|WARNING"
df -h /opt | tail -1
if [ "$DRY" = "0" ] && [ "__SKIPDOCKER__" = "0" ]; then
  for i in __IMAGES__; do
    if sud docker image inspect "$i" >/dev/null 2>&1; then echo "present: $i"; else echo "pulling: $i"; timeout 900 sud docker pull -q "$i" || echo "PULL FAILED: $i"; fi
  done
fi
sud docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}'
echo "### qemu images"; ls -1 /opt/gns3/images/QEMU 2>/dev/null | grep -v '\.md5sum$'
echo "### gns3"; curl -s -m 5 http://127.0.0.1/v2/version | tr -d '\n '; echo
echo "### end"
'@
$guestScript = $guestScript.Replace("__PW__", $pwQ).Replace("__DRY__", $(if ($DryRun) { "1" } else { "0" })).
    Replace("__GW__", $(if ($dnsGw) { $dnsGw } else { "" })).Replace("__IMAGES__", ($images -join " ")).
    Replace("__SKIPDOCKER__", $(if ($SkipDocker) { "1" } else { "0" }))
WriteLf (Join-Path $workDir "fixgns3.sh") $guestScript
WriteLf (Join-Path $workDir "netplan.yaml") $netplan

Guest CopyFileFromHostToGuest $VmxPath (Join-Path $workDir "fixgns3.sh")  /tmp/fixgns3.sh | Out-Null
Guest CopyFileFromHostToGuest $VmxPath (Join-Path $workDir "netplan.yaml") /tmp/fixgns3_netplan.yaml | Out-Null
$r = Guest runProgramInGuest $VmxPath /bin/bash /tmp/fixgns3.sh
if ($LASTEXITCODE -ne 0) { Die "Could not run commands in the VM ($r). Check -GuestUser/-GuestPassword." }
Guest CopyFileFromGuestToHost $VmxPath /tmp/fixgns3.out (Join-Path $workDir "guest.out") | Out-Null
$guestOut = Get-Content (Join-Path $workDir "guest.out")
$guestOut | ForEach-Object { Info "  | $_" }
$vmQemuImages = @(); $inQ = $false
foreach ($l in $guestOut) { if ($l -eq "### qemu images") { $inQ = $true; continue }; if ($l -like "###*") { $inQ = $false }; if ($inQ -and $l) { $vmQemuImages += $l } }
if ($guestOut -match "PULL FAILED") { Warn "Some docker pulls failed (see above)." }

if ($mgmtIp -and -not $DryRun) {
    try { $v = Invoke-RestMethod "http://${mgmtIp}:80/v2/version" -TimeoutSec 10; Ok "GNS3 server in VM reachable from host: http://${mgmtIp}/v2 (version $($v.version))" }
    catch { Warn "Host cannot reach http://${mgmtIp}/v2/version yet: $($_.Exception.Message)" }
}

# ------------------------------------------------------------------ 6. GNS3 controller: enable VM + re-detect IP
Step "Updating GNS3 VM settings in the GNS3 controller"
$apiUp = $false
try { $lv = Invoke-RestMethod "$api/version" -Headers $headers -TimeoutSec 5; $apiUp = $true; Ok "Local GNS3 controller $api (version $($lv.version))" }
catch { Warn "Local GNS3 server not reachable at $api" }

$vmDisplay = $vmx["displayname"]; if (-not $vmDisplay) { $vmDisplay = $vmName }

if ($DryRun -or $SkipApiRestart) {
    Info "Skipped (dry run / -SkipApiRestart)."
} elseif ($apiUp) {
    $projects = @(Invoke-RestMethod "$api/projects" -Headers $headers)
    foreach ($p in $projects | Where-Object { $_.status -eq "opened" }) {
        Info "Closing opened project '$($p.name)' (the VM is about to restart)"
        Invoke-RestMethod -Method Post "$api/projects/$($p.project_id)/close" -Headers $headers -Body "{}" -ContentType "application/json" | Out-Null
    }
    # NOTE: always PUT the FULL settings dict - a partial PUT replaces the settings and breaks GNS3 (KeyError 'engine')
    $s = Invoke-RestMethod "$api/gns3vm" -Headers $headers
    $s.engine = "vmware"; $s.vmname = $vmDisplay; if (-not $s.port) { $s.port = 80 }
    $s.enable = $false
    Invoke-RestMethod -Method Put "$api/gns3vm" -Headers $headers -Body ($s | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 600 | Out-Null
    $s.enable = $true
    Invoke-RestMethod -Method Put "$api/gns3vm" -Headers $headers -Body ($s | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 900 | Out-Null
    Info "GNS3 VM re-enabled; waiting for the controller to connect..."
    $deadline = (Get-Date).AddMinutes(8); $c = $null
    do {
        Start-Sleep 10
        try { $c = Invoke-RestMethod "$api/computes/vm" -Headers $headers -TimeoutSec 10 } catch { $c = $null }
    } until (($c -and $c.connected) -or (Get-Date) -gt $deadline)
    if ($c -and $c.connected) { Ok "Compute 'vm' connected at $($c.host):$($c.port) (GNS3 $($c.capabilities.version))" }
    else { Warn "Compute 'vm' not connected yet (host: $(if ($c) { $c.host } else { '?' })). Check GNS3 > Help > Setup / Preferences > GNS3 VM." }
} elseif (Get-Process gns3server, gns3 -ErrorAction SilentlyContinue) {
    Warn "GNS3 is running but its API is not reachable; enable the GNS3 VM in Edit > Preferences > GNS3 VM manually."
} else {
    Copy-Item $controllerIni "$controllerIni.bak-$ts"
    if (-not $controller.gns3vm) { $controller | Add-Member gns3vm ([pscustomobject]@{}) }
    foreach ($kv in @{ enable = $true; engine = "vmware"; vmname = $vmDisplay; port = 80; when_exit = "stop"; headless = $false; allocate_vcpus_ram = $true }.GetEnumerator()) {
        if ($kv.Key -in "enable", "engine", "vmname" -or -not ($controller.gns3vm.PSObject.Properties.Name -contains $kv.Key)) {
            $controller.gns3vm | Add-Member -Force $kv.Key $kv.Value
        }
    }
    WriteJson $controllerIni $controller
    Ok "GNS3 not running: enabled the GNS3 VM in $controllerIni (backup .bak-$ts). Start GNS3 now."
}

# ------------------------------------------------------------------ 7. optional project re-target
if ($ProjectFile.Count -gt 0) {
    Step "Re-targeting projects to the GNS3 VM"
    $hostBound = "cloud", "nat", "vmware", "virtualbox", "vpcs", "traceng"
    foreach ($pf in $ProjectFile) {
        if (-not (Test-Path $pf)) { Warn "Not found: $pf"; continue }
        $d = Get-Content $pf -Raw | ConvertFrom-Json
        $moved = 0; $fixed = 0; $missing = @()
        foreach ($n in $d.topology.nodes) {
            if ($n.compute_id -eq "local" -and $hostBound -notcontains $n.node_type) { $n.compute_id = "vm"; $moved++ }
            if ($n.node_type -eq "qemu") {
                $pr = $n.properties
                if ($pr.PSObject.Properties.Name -contains "qemu_path" -and -not $pr.qemu_path) {
                    $plat = if ($pr.platform) { $pr.platform } else { "x86_64" }; $pr.qemu_path = "/usr/bin/qemu-system-$plat"; $fixed++
                }
                foreach ($k in "hda_disk_image", "hdb_disk_image", "hdc_disk_image", "hdd_disk_image", "cdrom_image") {
                    $img = $pr.$k
                    if ($img -and $vmQemuImages.Count -gt 0 -and $vmQemuImages -notcontains $img) { $missing += "$($n.name): $img" }
                }
            }
        }
        if ($DryRun) { Info "$pf : would move $moved node(s) to 'vm', fix $fixed qemu_path" }
        else {
            Copy-Item $pf "$pf.bak-$ts"; WriteJson $pf $d
            Ok "$pf : moved $moved node(s) to 'vm', fixed $fixed empty qemu_path (backup .bak-$ts)"
        }
        if ($missing.Count) {
            Warn "Disk images referenced by the project but not in the VM (/opt/gns3/images/QEMU):"
            $missing | Select-Object -Unique | ForEach-Object { Info "      $_" }
            Info "    -> upload them via GNS3 (Edit > Preferences > QEMU) or point the nodes at an image the VM has."
        }
    }
}

Step "Done"
Info "Log + guest output: $workDir"
Stop-Transcript | Out-Null
