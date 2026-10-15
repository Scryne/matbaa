# Yerel ComfyUI (giyilmiş ürün videosu, src/matbaa/giyim.py): kapalıysa gizli pencerede başlatır, ayağa kalktığını doğrular.
# Kurulum: C:\Users\scryn\ComfyUI (git clone + .venv, torch cu130; modeller models/ altında, bkz. docs/Final-Dokuman.md K-35).
# Durdurmak: Get-NetTCPConnection -LocalPort 8188 -State Listen | % { Stop-Process -Id $_.OwningProcess }
$ErrorActionPreference = "Stop"
$comfy = if ($env:MATBAA_COMFY) { $env:MATBAA_COMFY } else { Join-Path $env:USERPROFILE "ComfyUI" }
$adres = "http://127.0.0.1:8188/system_stats"
function Ayakta { try { (Invoke-WebRequest -Uri $adres -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false } }
if (-not (Ayakta)) {
    $py = Join-Path $comfy ".venv\Scripts\python.exe"
    $log = Join-Path $comfy "comfy.log"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"`"$py`" main.py --listen 127.0.0.1 --port 8188 >> `"$log`" 2>&1`"" -WorkingDirectory $comfy -WindowStyle Hidden
    $son = (Get-Date).AddSeconds(180)
    while (-not (Ayakta) -and (Get-Date) -lt $son) { Start-Sleep -Seconds 2 }
}
if (Ayakta) { "ComfyUI hazır: http://127.0.0.1:8188" } else { throw "ComfyUI açılmadı, bkz. $comfy\comfy.log" }
