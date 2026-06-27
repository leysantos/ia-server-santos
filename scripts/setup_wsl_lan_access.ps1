# Encaminha portas 3000 (frontend) e 8000 (API) do Windows para o WSL2.
# Execute no PowerShell como Administrador (uma vez por boot do Windows, ou agende na inicialização).
#
# Uso: .\scripts\setup_wsl_lan_access.ps1

$ErrorActionPreference = "Stop"

$wslIp = (wsl -e hostname -I).Trim().Split(" ")[0]
if (-not $wslIp) {
    Write-Error "Não foi possível obter o IP do WSL. Verifique se o WSL está rodando."
}

Write-Host "WSL IP: $wslIp"

function Set-PortProxy {
    param([int]$Port)
    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>$null | Out-Null
    netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=$wslIp
    Write-Host "Portproxy $Port -> ${wslIp}:$Port"
}

Set-PortProxy -Port 8000
Set-PortProxy -Port 3000

$rules = @(
    @{ Name = "IA Server Santos API"; Port = 8000 },
    @{ Name = "IA Server Santos Frontend"; Port = 3000 }
)
foreach ($r in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $r.Name -Direction Inbound -LocalPort $r.Port -Protocol TCP -Action Allow | Out-Null
        Write-Host "Firewall: $($r.Name)"
    }
}

Write-Host ""
Write-Host "Acesso na rede SEMINF (Ethernet 2):"
Write-Host "  Frontend: http://172.22.3.234:3000"
Write-Host "  API:      http://172.22.3.234:8000"
Write-Host ""
Write-Host "Wi-Fi alternativo: http://192.168.143.111:3000"
netsh interface portproxy show all
