# Dispara la corrida diaria en GitHub Actions, a la hora exacta.
#
# POR QUÉ: el horario propio de GitHub (schedule) es "best effort" en el plan
# gratis: en horas de carga llega con horas de atraso o no llega (el 08 y el
# 09/10/2026 no corrió a horario). La orden manual (workflow_dispatch), en
# cambio, arranca en segundos. Este script la manda; lo ejecuta el Programador
# de tareas de Windows de lunes a viernes a las 16:19. La corrida es la de
# siempre, en la nube de GitHub: la compu solo da la orden.
#
# Es seguro repetirlo: si el día ya salió, la corrida encuentra la fila y
# termina sin mandar nada; los feriados los saltea sola. Los horarios de
# GitHub quedan como respaldo para los días con la compu apagada.
#
# Usa la sesión de gh ya iniciada (gh auth login). Deja un renglón por
# disparo en %LOCALAPPDATA%\reporte_macro\disparos.log.

$repo = "mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing"
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$carpeta = Join-Path $env:LOCALAPPDATA "reporte_macro"
New-Item -ItemType Directory -Force $carpeta | Out-Null
$log = Join-Path $carpeta "disparos.log"

$salida = & $gh workflow run corrida-diaria.yml --repo $repo --ref main -f modo=real 2>&1
$estado = if ($LASTEXITCODE -eq 0) { "ok" } else { "FALLO" }
Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $estado $($salida -join ' ')" -Encoding utf8
exit $LASTEXITCODE
