# Teleoperacion: el follower imita al leader.
# ANTES: una persona mirando el follower con la mano cerca de su fuente de 12 V.
# Uso:  powershell -ExecutionPolicy Bypass -File herramientas\teleoperar.ps1
# Parar: Ctrl+C (el follower suelta el par al desconectar).
$ErrorActionPreference = "Stop"
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:PYTHONIOENCODING = "utf-8"
. "E:\HACKATONLeRobot\lerobot\.venv\Scripts\Activate.ps1"

$F = python E:\HACKATONLeRobot\herramientas\puertos.py follower
$L = python E:\HACKATONLeRobot\herramientas\puertos.py leader
if ($F -eq "NO_DETECTADO" -or $L -eq "NO_DETECTADO") { Write-Host "Falta un brazo."; Read-Host "Enter para salir"; exit 1 }
Write-Host "Follower $F  /  Leader $L"
Write-Host "Pon el leader en una postura parecida a la del follower antes de seguir (evita un salto brusco)."
Read-Host "Enter para empezar (Ctrl+C para parar)"

# Sin limite de salto por paso (probado con max_relative_target=10 el 20-nov y fue bien).
lerobot-teleoperate `
  --robot.type=so101_follower --robot.port=$F --robot.id=follower_puesto `
  --teleop.type=so101_leader --teleop.port=$L --teleop.id=leader_puesto
