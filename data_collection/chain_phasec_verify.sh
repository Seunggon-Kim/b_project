#!/bin/bash
# 자동 체인: 2010~2014 백필 종료 대기 -> 성공 게이트 -> Phase C -> 최종 검증.
# nohup 로 띄워 로컬 PC/SSH 와 무관하게 EC2 에서 끝까지 완주한다.
# 게이트: PBP 인덱스 3개 + 2010~2014 각 연도 적재 + quick_check=ok 일 때만 Phase C 진행.
set -uo pipefail
cd ~/b_project
LOG=logs/auto_chain.log
VENV=venv/bin/python
log(){ echo "$(date -u '+%F %H:%M:%S') $*" | tee -a "$LOG"; }

log "===== auto-chain 시작: 백필 종료 대기 ====="
while pgrep -f "[b]ackfill_2010_2014" >/dev/null; do sleep 30; done
log "백필 프로세스 종료 감지. 성공 게이트 검사 시작(quick_check 포함, 수분 소요 가능)."

GATE=$($VENV data_collection/_chain_gate.py 2>&1)
log "게이트 결과:"
echo "$GATE" | tee -a "$LOG"
if ! echo "$GATE" | grep -q "GATE=PASS"; then
  log "게이트 FAIL -> Phase C 중단. 사람이 백필 로그(logs/backfill_2010_2014.log) 점검 필요."
  exit 1
fi
log "게이트 PASS -> Phase C 시작"

./data_collection/phase_c.sh >> logs/phase_c.log 2>&1
rc=$?
log "Phase C 종료 rc=$rc (상세: logs/phase_c.log)"

log "최종 검증 standalone 실행 -> logs/verify_full.log"
$VENV data_collection/verify_full_backfill.py > logs/verify_full.log 2>&1
log "검증 rc=$? (결과: logs/verify_full.log)"
log "===== auto-chain 완료 ====="
