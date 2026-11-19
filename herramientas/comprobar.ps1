# Comprobacion rapida del portatil (ejecutar al llegar al puesto y con todo enchufado):
#   powershell -ExecutionPolicy Bypass -File herramientas\comprobar.ps1
conda activate lerobot
$env:PYTHONIOENCODING = "utf-8"
Write-Host "=== LeRobot y GPU"
lerobot-info 2>&1 | Select-String -Pattern "LeRobot version|PyTorch version|CUDA support|Cuda version"
python -c "import torch; print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO HAY GPU')"
Write-Host "=== Datos en: $env:HF_HOME (debe ser E:\HACKATONLeRobot\hf_cache)"
Write-Host "=== Puertos serie (los brazos salen como COMx)"
python -c "import serial.tools.list_ports as lp; [print(' ', p.device, '-', p.description) for p in lp.comports()] or print('  ninguno')"
Write-Host "=== Camaras (las fotos quedan en outputs\captured_images)"
lerobot-find-cameras opencv 2>&1 | Select-String -Pattern "Found|Id:|Saved image" | Select-Object -First 8
Write-Host "=== Disco libre"
Get-PSDrive C, E | Format-Table Name, @{n="Libre (GB)"; e={[math]::Round($_.Free / 1GB, 1)}} -AutoSize
