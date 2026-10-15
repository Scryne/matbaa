# Matbaa takip panosu: sunucu kapalıysa gizli pencerede başlatır, ayağa kalktığını HTTP ile doğrular, tarayıcıda açar.
# Oturum açılınca Başlangıç klasöründeki kısayol bunu çalıştırır (kurulum: scripts\pano_kur.ps1). Elle de çalıştırılabilir.
# Durdurmak: Get-NetTCPConnection -LocalPort 8766 -State Listen | % { Stop-Process -Id $_.OwningProcess }
$ErrorActionPreference = "Stop"
$kok = Split-Path -Parent $PSScriptRoot
$adres = "http://127.0.0.1:8766/"

function Ayakta {
    try { (Invoke-WebRequest -Uri "${adres}api/pano" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false }
}

if (-not (Ayakta)) {
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
    $log = Join-Path $kok "calisma"
    New-Item -ItemType Directory -Force $log | Out-Null
    # cmd yönlendirmesi baytları olduğu gibi yazar (gorev_kur.ps1 ile aynı gerekçe: Türkçe çıktı bozulmasın).
    $cmd = "set `"PYTHONUTF8=1`"&& `"$uv`" run matbaa panel >> `"$log\panel.log`" 2>&1"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -WorkingDirectory $kok -WindowStyle Hidden
    $son = (Get-Date).AddSeconds(60)  # oturum açılışında disk meşgul: uv ilk açılışta yavaş olabilir
    while (-not (Ayakta) -and (Get-Date) -lt $son) { Start-Sleep -Milliseconds 700 }
}
if (Ayakta) { Start-Process $adres } else { Start-Process (Join-Path $kok "calisma\panel.log") }
