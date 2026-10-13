# Matbaa günlük görevi: her gün 10:30'da (bilgisayar kapalıysa açıldığında) `uv run matbaa gunluk`.
# Kurulum:   powershell -ExecutionPolicy Bypass -File scripts\gorev_kur.ps1
# Kaldırma:  Unregister-ScheduledTask -TaskName "Matbaa-Gunluk" -Confirm:$false
$ErrorActionPreference = "Stop"
$kok = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv).Source
$log = Join-Path $kok "calisma\gunluk"
New-Item -ItemType Directory -Force $log | Out-Null
# cmd yönlendirmesi baytları olduğu gibi yazar (PowerShell *>> UTF-8 çıktıyı yeniden kodlayıp Türkçeyi bozuyordu).
$cmd = "set `"PYTHONUTF8=1`"&& `"$uv`" run matbaa gunluk >> `"$log\gunluk.log`" 2>&1"
$eylem = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmd" -WorkingDirectory $kok
$tetik = New-ScheduledTaskTrigger -Daily -At 10:30
$ayar = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "Matbaa-Gunluk" -Action $eylem -Trigger $tetik -Settings $ayar -Description "Matbaa: üretim → ilan metni → yayın → sipariş izleme" -Force | Out-Null
Get-ScheduledTask -TaskName "Matbaa-Gunluk" | Select-Object TaskName, State
