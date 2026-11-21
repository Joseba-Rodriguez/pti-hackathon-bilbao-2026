@echo off
rem Doble clic: abre la web de la demo (celda caliente) con el panel de control.
rem Todo lo demas (camara, robot, parar) se hace desde el boton "CONTROL" de la web.
cd /d E:\HACKATONLeRobot\lerobot
set HF_HOME=E:\HACKATONLeRobot\hf_cache
set PATH=E:\miniforge3\envs\ffmpeg8\Library\bin;%PATH%
echo Web de la demo: http://127.0.0.1:8765/   (no cierres esta ventana)
.venv\Scripts\python.exe ..\herramientas\gemelo.py
pause
