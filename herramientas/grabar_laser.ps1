# Graba UN tipo de movimiento del plan docs/PLAN_LASER.md en SU PROPIO dataset.
# Uso (desde cualquier sitio):
#   powershell -ExecutionPolicy Bypass -File E:\HACKATONLeRobot\herramientas\grabar_laser.ps1 -Tipo A
# Si se corta, relanza EL MISMO comando: continua donde lo dejo (--resume) y graba solo los que faltan.
# Opcional: -Episodios N para cambiar cuantos grabar en total de ese tipo.
# MUEVE EL BRAZO (teleoperado con el leader).

param(
    [Parameter(Mandatory = $true)][ValidateSet("A", "B", "C", "D", "E", "F", "G", "H")][string]$Tipo,
    [int]$Episodios = 0
)

$tipos = @{
    "A" = @("recta_corta", 10); "B" = @("recta_larga", 10); "C" = @("curva", 8); "D" = @("paradas", 8)
    "E" = @("cambio_sentido", 6); "F" = @("salto", 4); "G" = @("quieto", 4); "H" = @("centro", 30)
}
$nombre = "pti_laser_" + $Tipo + "_" + $tipos[$Tipo][0]
$total = if ($Episodios -gt 0) { $Episodios } else { $tipos[$Tipo][1] }
$repo = "Josebarv01/$nombre"
$root = "E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01\$nombre"

Set-Location E:\HACKATONLeRobot\lerobot
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:PATH = "E:\miniforge3\envs\ffmpeg8\Library\bin;" + $env:PATH

$puertos = & .\.venv\Scripts\python.exe ..\herramientas\puertos.py
$follower = ($puertos | Select-String "follower: (COM\d+)").Matches.Groups[1].Value
$leader = ($puertos | Select-String "leader: (COM\d+)").Matches.Groups[1].Value
if (-not $follower -or -not $leader) { Write-Host "No encuentro los brazos:"; $puertos; exit 1 }

$hechos = 0
$extra = @()
if (Test-Path "$root\meta\info.json") {
    $hechos = (Get-Content "$root\meta\info.json" -Raw | ConvertFrom-Json).total_episodes
    if ($hechos -eq 0) {
        $aparte = "$root" + "_vacio_" + (Get-Date -Format "HHmmss")
        Move-Item $root $aparte
        Write-Host "Habia una carpeta vacia de un intento fallido: apartada en $aparte"
    } else {
        $extra = @("--resume=true", "--dataset.root=$root")
    }
}
$faltan = $total - $hechos
if ($faltan -le 0) { Write-Host "$nombre ya tiene $hechos de $total episodios. Nada que grabar."; exit 0 }

Write-Host ""
Write-Host "=== Tipo $Tipo ($($tipos[$Tipo][0])) -> $repo ==="
Write-Host "Hechos: $hechos   Faltan: $faltan   (leader $leader, follower $follower)"
Write-Host "Teclas:  ->  fin del episodio / empezar el siguiente   <-  repetir   Esc  parar y guardar"
Write-Host "Recuerda: marca roja del bote tapada, laser APAGADO al empezar, solo casillas 4-9."
Write-Host ""

$cmd = @(
    "..\herramientas\lerobot_laser.py", "record",
    "--robot.type=so101_follower", "--robot.port=$follower", "--robot.id=follower_puesto",
    "--robot.cameras={ top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30} }",
    "--teleop.type=so101_leader", "--teleop.port=$leader", "--teleop.id=leader_puesto",
    "--dataset.repo_id=$repo", "--dataset.no_stamp=true",
    "--dataset.single_task=pick up the cup, follow the laser and place it where the laser turns off",
    "--dataset.num_episodes=$faltan", "--dataset.episode_time_s=60", "--dataset.reset_time_s=300",
    "--dataset.streaming_encoding=true", "--display_data=true"
) + $extra
& .\.venv\Scripts\python.exe @cmd

if (Test-Path "$root\meta\info.json") {
    $n = (Get-Content "$root\meta\info.json" -Raw | ConvertFrom-Json).total_episodes
    Write-Host ""
    Write-Host "$nombre : $n de $total episodios guardados en $root"
}
