# Prueba un modelo en el robot VIENDO LA CAMARA EN DIRECTO (ventana de Rerun).
# Uso:
#   powershell -ExecutionPolicy Bypass -File ..\herramientas\probar.ps1 -Modelo outputs/train/coger_v7/checkpoints/last/pretrained_model
# Camaras top (2) + wrist (1), como pti_coger_v7. (coger_v2 era solo top: no vale este script.)
# Opcionales: -Tarea "pick up the cup from the holder"  -Segundos 30  -SinSuavizar
# Siempre con el filtro de laser (igual que al grabar). MUEVE EL BRAZO.

param(
    [Parameter(Mandatory = $true)][string]$Modelo,
    [string]$Tarea = "pick up the cup from the holder",
    [int]$Segundos = 30,
    [switch]$SinSuavizar,
    [int]$Bloque = 0,    # >0: sin suavizado, re-planifica cada N pasos (p.ej. 10 = mas reactivo para seguir el laser)
    [string]$Coef = "",  # suavizado con este coeficiente: 0.01 = suave (por defecto); -0.05 = suave pero reacciona antes
    [switch]$SinAsync    # SIEMPRE 30 Hz: el suavizado va con la red en un hilo aparte. Esto lo desactiva (8-14 Hz)
)

Set-Location E:\HACKATONLeRobot\lerobot
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
if (-not $SinAsync) { $env:PTI_ENSEMBLE_ASYNC = "1" } else { Remove-Item Env:PTI_ENSEMBLE_ASYNC -ErrorAction SilentlyContinue }
$env:PATH = "E:\miniforge3\envs\ffmpeg8\Library\bin;" + $env:PATH

$puertos = & .\.venv\Scripts\python.exe ..\herramientas\puertos.py
$follower = ($puertos | Select-String "follower: (COM\d+)").Matches.Groups[1].Value
if (-not $follower) { Write-Host "No encuentro el follower:"; $puertos; exit 1 }
Write-Host "Follower en $follower  |  modelo: $Modelo"

$r = Read-Host "Hay una persona mirando el brazo con la mano en la alimentacion? (s/n)"
if ($r -ne "s") { Write-Host "Cancelado"; exit 0 }

$args = @(
    "..\herramientas\lerobot_laser.py", "rollout", "--strategy.type=base",
    "--policy.path=$Modelo",
    "--robot.type=so101_follower", "--robot.port=$follower", "--robot.id=follower_puesto",
    "--robot.cameras={ top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30} }",
    "--fps=30", "--task=$Tarea", "--duration=$Segundos", "--display_data=true"
)
if ($Coef) { $args += @("--policy.n_action_steps=1", "--policy.temporal_ensemble_coeff=$Coef") }
elseif ($Bloque -gt 0) { $args += @("--policy.n_action_steps=$Bloque") }
elseif (-not $SinSuavizar) { $args += @("--policy.n_action_steps=1", "--policy.temporal_ensemble_coeff=0.01") }
& .\.venv\Scripts\python.exe @args
