# Takip panosunu oturum açılışında otomatik açar: Başlangıç klasörüne kısayol (yönetici izni gerekmez).
# Kurulum:   powershell -ExecutionPolicy Bypass -File scripts\pano_kur.ps1
# Kaldırma:  Remove-Item "$([Environment]::GetFolderPath('Startup'))\Matbaa Pano.lnk"
$ErrorActionPreference = "Stop"
$betik = Join-Path $PSScriptRoot "pano_baslat.ps1"
$hedef = Join-Path ([Environment]::GetFolderPath("Startup")) "Matbaa Pano.lnk"
$k = (New-Object -ComObject WScript.Shell).CreateShortcut($hedef)
$k.TargetPath = "powershell.exe"
$k.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$betik`""
$k.WorkingDirectory = Split-Path -Parent $PSScriptRoot
$k.WindowStyle = 7  # simge durumunda: açılışta pencere yanıp sönmesin
$k.Description = "Matbaa takip panosu (http://127.0.0.1:8766)"
$k.Save()
Write-Output "kısayol: $hedef"
