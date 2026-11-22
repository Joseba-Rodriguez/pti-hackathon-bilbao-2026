# Entrena un ACT en la nube (Hugging Face Jobs) con LA MISMA version de LeRobot que el portatil.
#
# Por que no "lerobot-train --job.target=...": la imagen de HF solo existe como "latest" (LeRobot mas
# nuevo) y rechaza la config que escribe nuestra 0.6.2 (error en `ema`); ademas un modelo entrenado con
# otra version podria no cargar en el portatil. Aqui la maquina instala nuestro commit exacto.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File E:\HACKATONLeRobot\herramientas\entrenar_nube.ps1 -Nombre laser_v1 -Dataset pti_laser_todo -Pasos 10000
# Opcionales: -Desde Josebarv01/act_pti_coger_v7 (modelo de partida; "" = desde cero)
#             -Maquina a10g-large   -Tope 3h   -Batch 8
#             -Excluir "[0,1,2]"   episodios que NO se entrenan (--dataset.exclude_episodes)
#             -CadaCheckpoint 2500 -SubirCheckpoints   sube cada checkpoint al repo del modelo (si no, se pierden)
# El dataset tiene que estar en el Hub (Josebarv01/<Dataset>). El modelo queda en Josebarv01/act_pti_<Nombre>.
# Ver el progreso:  hf jobs logs <id>      Cancelar:  hf jobs cancel <id>

param(
    [Parameter(Mandatory = $true)][string]$Nombre,
    [Parameter(Mandatory = $true)][string]$Dataset,
    [int]$Pasos = 10000,
    [string]$Desde = "Josebarv01/act_pti_coger_v7",
    [string]$Maquina = "a10g-large",
    [string]$Tope = "3h",
    [int]$Batch = 8,
    [string]$Excluir = "",
    [int]$CadaCheckpoint = 2500,
    [switch]$SubirCheckpoints
)

$COMMIT = "git+https://github.com/Juxi-Technology/lerobot@3bb7b4a"   # = lerobot\ del portatil (0.6.2)
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:HF_TOKEN = (Get-Content "$env:HF_HOME\token" -Raw).Trim()        # se pasa como secreto, no se imprime

$politica = if ($Desde) { "--policy.path=$Desde" } else { "--policy.type=act" }
$train = "lerobot-train --dataset.repo_id=Josebarv01/$Dataset $politica " +
         "--policy.repo_id=Josebarv01/act_pti_$Nombre --policy.push_to_hub=true --policy.device=cuda " +
         "--output_dir=/tmp/out/$Nombre --job_name=$Nombre --steps=$Pasos --save_freq=$CadaCheckpoint " +
         "--batch_size=$Batch --num_workers=10 --job.target=local"
if ($Excluir) { $train += " --dataset.exclude_episodes=$($Excluir -replace ' ', '')" }
if ($SubirCheckpoints) { $train += " --save_checkpoint_to_hub=true" }
$pkg = "'lerobot[training] @ $COMMIT'"
$bash = "set -e; PY=`$(command -v python || command -v python3); echo usando `$PY; " +
        "(command -v uv >/dev/null && uv pip install -q --python `$PY $pkg) || `$PY -m pip install -q $pkg; " +
        "uv pip list --python `$PY 2>/dev/null | grep -i '^lerobot ' || true; $train"

Write-Host "Lanzando $Nombre en $Maquina (tope $Tope): $Dataset, $Pasos pasos, desde '$Desde'"
Write-Host "  $train"
& E:\HACKATONLeRobot\lerobot\.venv\Scripts\hf.exe jobs run --detach --flavor $Maquina --timeout $Tope --secrets HF_TOKEN huggingface/lerobot-gpu:latest bash -c $bash
Write-Host "Modelo al terminar: https://huggingface.co/Josebarv01/act_pti_$Nombre"
