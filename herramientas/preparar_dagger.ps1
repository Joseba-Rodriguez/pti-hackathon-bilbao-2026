# Junta las correcciones de una sesion DAgger con el dataset base y lo sube al Hub (privado),
# listo para entrenar con entrenar_nube.ps1. No mueve el robot.
#
# Uso (tras la sesion DAgger, que deja las correcciones en hf_cache\lerobot\Josebarv01\rollout_dagger_v1):
#   powershell -ExecutionPolicy Bypass -File E:\HACKATONLeRobot\herramientas\preparar_dagger.ps1
# Opcionales: -Correcciones rollout_dagger_v1  -Base pti_todo_v2  -Salida pti_todo_v3_dagger  -SinSubir
#
# Pasos:
#   1. Quita la columna "intervention" de las correcciones (el dataset base no la tiene y merge exige
#      las mismas columnas).
#   2. Fusiona Base + correcciones en Salida. La Base va primero: sus episodios conservan la numeracion
#      (los reservados 58, 70, 84, 99, 106, 117 siguen siendo los mismos); las correcciones van detras.
#   3. Sube Salida al Hub como PRIVADO.
#   4. Imprime los pasos para 1 y 2 vueltas y el comando de entrenamiento sugerido.

param(
    [string]$Correcciones = "rollout_dagger_v1",
    [string]$Base = "pti_todo_v2",
    [string]$Salida = "pti_todo_v3_dagger",
    [string]$RaizCorrecciones = "",
    [string]$RaizSalida = "",
    [string]$Quitar = "",      # correcciones malas a descartar, p.ej. "[0]" o "[0,7]" (numeradas desde 0)
    [switch]$SinSubir
)

$ErrorActionPreference = "Stop"
Set-Location E:\HACKATONLeRobot\lerobot
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:PATH = "E:\miniforge3\envs\ffmpeg8\Library\bin;" + $env:PATH
$hub = "E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01"
$py = ".\.venv\Scripts\python.exe"
$edit = ".\.venv\Scripts\lerobot-edit-dataset.exe"

$rCorr = if ($RaizCorrecciones) { $RaizCorrecciones } else { "$hub\$Correcciones" }
$rBase = "$hub\$Base"
$rSin = "$rCorr" + "_sin_intervention"
$rSal = if ($RaizSalida) { $RaizSalida } else { "$hub\$Salida" }

foreach ($r in @($rCorr, $rBase)) {
    if (-not (Test-Path "$r\meta\info.json")) { Write-Host "No encuentro el dataset en $r"; exit 1 }
}
if (Test-Path $rSal) { Write-Host "Ya existe $rSal. Borralo o usa otro -Salida."; exit 1 }

$info = Get-Content "$rCorr\meta\info.json" -Raw | ConvertFrom-Json
Write-Host "Correcciones: $($info.total_episodes) episodios, $($info.total_frames) fotogramas"

# 1. Quitar "intervention" (si esta)
$origen = $rCorr
if ($info.features.PSObject.Properties.Name -contains "intervention") {
    if (Test-Path $rSin) { Remove-Item -Recurse -Force $rSin -Confirm:$false }
    & $edit --repo_id=Josebarv01/$Correcciones --root=$rCorr --new_repo_id=Josebarv01/$Correcciones`_sin_intervention --new_root=$rSin --operation.type=remove_feature "--operation.feature_names=['intervention']"
    if ($LASTEXITCODE -ne 0) { Write-Host "Fallo al quitar 'intervention'"; exit 1 }
    $origen = $rSin
} else {
    Write-Host "Las correcciones no tienen 'intervention': se fusionan tal cual"
}

# 1b. Descartar correcciones malas
if ($Quitar) {
    $rLimpio = "$rCorr" + "_limpio"
    if (Test-Path $rLimpio) { Remove-Item -Recurse -Force $rLimpio -Confirm:$false }
    & $edit --repo_id=Josebarv01/$Correcciones --root=$origen --new_repo_id=Josebarv01/$Correcciones`_limpio --new_root=$rLimpio --operation.type=delete_episodes "--operation.episode_indices=$($Quitar -replace ' ', '')"
    if ($LASTEXITCODE -ne 0) { Write-Host "Fallo al descartar $Quitar"; exit 1 }
    $origen = $rLimpio
    $n = (Get-Content "$rLimpio\meta\info.json" -Raw | ConvertFrom-Json).total_episodes
    Write-Host "Descartadas $Quitar : quedan $n correcciones"
}

# 2. Fusionar (Base primero)
& $edit --new_repo_id=Josebarv01/$Salida --new_root=$rSal --operation.type=merge "--operation.repo_ids=['Josebarv01/$Base','Josebarv01/$Correcciones']" "--operation.roots=['$($rBase -replace '\\','/')','$($origen -replace '\\','/')']"
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo al fusionar"; exit 1 }

$out = Get-Content "$rSal\meta\info.json" -Raw | ConvertFrom-Json
$fr = [int]$out.total_frames
Write-Host ""
Write-Host "$Salida : $($out.total_episodes) episodios, $fr fotogramas en $rSal"

# 3. Subir (privado)
if (-not $SinSubir) {
    & $py -c "from lerobot.datasets.lerobot_dataset import LeRobotDataset as D; D('Josebarv01/$Salida', root=r'$rSal').push_to_hub(private=True)"
    if ($LASTEXITCODE -ne 0) { Write-Host "Fallo al subir al Hub"; exit 1 }
    Write-Host "Subido (privado): https://huggingface.co/datasets/Josebarv01/$Salida"
}

# 4. Pasos sugeridos (batch 8). Reservados: los 6 de siempre.
$p1 = [math]::Round($fr / 8); $p2 = [math]::Round($fr * 2 / 8)
Write-Host ""
Write-Host "1 vuelta = $p1 pasos (~$([math]::Round($p1 / 6.25 / 60)) min)   2 vueltas = $p2 pasos (~$([math]::Round($p2 / 6.25 / 60)) min)"
Write-Host "Ejemplo (afinar v3 con las correcciones, 1,5 vueltas):"
Write-Host "  powershell -ExecutionPolicy Bypass -File E:\HACKATONLeRobot\herramientas\entrenar_nube.ps1 -Nombre v3_dagger -Dataset $Salida -Desde Josebarv01/act_pti_todo_v3 -Pasos $([math]::Round($fr * 1.5 / 8)) -Tope 2h -CadaCheckpoint $p1 -SubirCheckpoints"
