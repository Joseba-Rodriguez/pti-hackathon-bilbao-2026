#!/bin/bash
# Esperanza: graba 50 demostraciones por habilidad, entrena las 2 ACT y las evalua.
# Uso (Git Bash, desde e:\HACKATONLeRobot\lerobot):  bash examples/so101_mujoco/esperanza_entrenar.sh
# Registros en examples/so101_mujoco/outputs/logs/. Tarda unas 4-5 horas en la RTX 2060.
cd /e/HACKATONLeRobot/lerobot
export PYTHONIOENCODING=utf-8
O=examples/so101_mujoco/outputs
mkdir -p $O/logs
echo "=== $(date +%H:%M) grabando demostraciones"
.venv/Scripts/python.exe examples/so101_mujoco/esperanza_record.py --episodios 50 --seed 0 > $O/logs/record.log 2>&1
echo "=== $(date +%H:%M) grabacion terminada (codigo $?)"
grep "^FIN" $O/logs/record.log
for s in entregar recoger; do
  echo "=== $(date +%H:%M) entrenando $s"
  rm -rf "$O/train/esperanza/${s:?}"
  .venv/Scripts/python.exe examples/so101_mujoco/auto_train.py --policy.type=act --policy.push_to_hub=false \
    --policy.device=cuda --policy.use_amp=true --dataset.repo_id=local/esperanza_$s \
    --dataset.root=$O/datasets/esperanza/$s --dataset.video_backend=pyav --output_dir=$O/train/esperanza/$s \
    --steps=30000 --batch_size=8 --log_freq=500 --save_freq=10000 --num_workers=4 > $O/logs/train_$s.log 2>&1
  echo "=== $(date +%H:%M) $s terminado (codigo $?)"
done
echo "=== $(date +%H:%M) evaluando"
.venv/Scripts/python.exe examples/so101_mujoco/esperanza_eval.py --intentos 10 > $O/logs/eval.log 2>&1
grep -A3 RESUMEN $O/logs/eval.log
echo "=== $(date +%H:%M) FIN"
