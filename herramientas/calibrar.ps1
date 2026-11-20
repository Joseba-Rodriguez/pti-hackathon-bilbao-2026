# Calibra follower, leader o ambos (una sola vez en todo el evento).
# Uso:  powershell -ExecutionPolicy Bypass -File herramientas\calibrar.ps1              -> pregunta cual
#       powershell -ExecutionPolicy Bypass -File herramientas\calibrar.ps1 follower     -> solo follower
#       (valores: follower, leader, ambos)
# Durante la calibracion los motores van SIN par: el brazo no se mueve solo, lo mueves tu a mano.
param([ValidateSet("follower", "leader", "ambos", "")][string]$Brazo = "")
$ErrorActionPreference = "Stop"
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:PYTHONIOENCODING = "utf-8"
. "E:\HACKATONLeRobot\lerobot\.venv\Scripts\Activate.ps1"

if ($Brazo -eq "") {
    Write-Host "Que brazo quieres calibrar?"
    Write-Host "  1) follower"
    Write-Host "  2) leader"
    Write-Host "  3) ambos"
    switch (Read-Host "Elige 1, 2 o 3") {
        "1" { $Brazo = "follower" }
        "2" { $Brazo = "leader" }
        "3" { $Brazo = "ambos" }
        default { Write-Host "Opcion no valida."; Read-Host "Enter para salir"; exit 1 }
    }
}

python E:\HACKATONLeRobot\herramientas\puertos.py

Write-Host "`nRecuerda: cuando pregunte, escribe 'c' + Enter para recalibrar (solo Enter = usar la calibracion guardada)." -ForegroundColor Yellow
Write-Host "Paso A: postura media del dibujo (brazo vertical, antebrazo horizontal, muneca recta). Enter."
Write-Host "Paso B: cada articulacion (menos wrist_roll) de tope a tope, despacio, una a una. Enter al terminar."

if ($Brazo -in "follower", "ambos") {
    $F = python E:\HACKATONLeRobot\herramientas\puertos.py follower
    if ($F -eq "NO_DETECTADO") { Write-Host "Follower no detectado. Para aqui."; Read-Host "Enter para salir"; exit 1 }
    Write-Host "`n=== FOLLOWER ($F) ===" -ForegroundColor Cyan
    lerobot-calibrate --robot.type=so101_follower --robot.port=$F --robot.id=follower_puesto
}

if ($Brazo -in "leader", "ambos") {
    $L = python E:\HACKATONLeRobot\herramientas\puertos.py leader
    if ($L -eq "NO_DETECTADO") { Write-Host "Leader no detectado. Para aqui."; Read-Host "Enter para salir"; exit 1 }
    Write-Host "`n=== LEADER ($L) ===" -ForegroundColor Cyan
    lerobot-calibrate --teleop.type=so101_leader --teleop.port=$L --teleop.id=leader_puesto
}

Write-Host "`nCalibracion guardada en $env:HF_HOME\lerobot\calibration" -ForegroundColor Green
Read-Host "Enter para cerrar"
