"""Windows bildirimi: günlük koşu hata ya da alarm bulursa Scryne'ın ekranına düşer (log dosyasını kimse okumaz).

Windows PowerShell 5.1'in WinRT toast API'si; ek modül yok. Uygulama kimliği olarak PowerShell'inki kullanılır (kayıtsız bir
kimlikle Windows bildirimi sessizce yutuyor). Metin ortam değişkeniyle geçer: tırnak/kaçış sorunu yok. Bildirim çıkmazsa
koşu düşmez; sonuç `calisma/gunluk/son.json`da ve panelde yine görünür.
"""

from __future__ import annotations

import os
import subprocess
import sys

UYGULAMA = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
BETIK = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$sablon = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$metin = $sablon.GetElementsByTagName("text")
$metin.Item(0).AppendChild($sablon.CreateTextNode($env:MATBAA_BASLIK)) | Out-Null
$metin.Item(1).AppendChild($sablon.CreateTextNode($env:MATBAA_METIN)) | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:MATBAA_UYGULAMA).Show(
  [Windows.UI.Notifications.ToastNotification]::new($sablon))
"""


def goster(baslik: str, metin: str, yazdir=print) -> bool:
    if sys.platform != "win32" or os.environ.get("MATBAA_BILDIRIM") == "0":
        return False
    ortam = os.environ | {"MATBAA_BASLIK": baslik, "MATBAA_METIN": metin, "MATBAA_UYGULAMA": UYGULAMA}
    try:
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", BETIK],
            env=ortam,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        yazdir(f"  bildirim gösterilemedi: {e}")
        return False
    if p.returncode != 0:
        yazdir(f"  bildirim gösterilemedi: {p.stderr.decode('utf-8', 'replace')[:200]}")
    return p.returncode == 0
