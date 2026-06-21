#!/usr/bin/env bash
# deploy.sh — bstats(KBO) 프로덕션 안전 배포
#
# 사용법:
#   ./deploy.sh            origin/main 으로 배포 (리셋 → 재시작 → 헬스체크 → 실패 시 자동 롤백)
#   ./deploy.sh --check    무엇이 바뀌는지만 출력 (실제 변경 없음)
#   FORCE=1 ./deploy.sh    프로덕션에 커밋 안 된 변경이 있어도 버리고 강제 배포
#
# 원칙: 프로덕션을 직접 수정하지 마세요. 변경은 git(main)에 커밋한 뒤 이 스크립트로만 배포합니다.
set -uo pipefail

REPO="$HOME/b_project"
SERVICE="kbo-api"
API="http://localhost:8000"
REMOTE_BRANCH="origin/main"
# reset --hard 가 절대 지우면 안 되는 라이브 데이터(추적되지 않아야 정상)
GUARD_PATHS=("database/kbo_stats.db" "dashboard_js/assets/player_photos")

cd "$REPO" || { echo "[치명] $REPO 디렉터리를 찾을 수 없습니다"; exit 1; }
log(){ printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*"; }

# / 가 200 될 때까지 최대 20초 대기 후 핵심 엔드포인트 점검 (0=정상)
health(){
  local ok=0 i code
  for i in $(seq 1 20); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$API/" 2>/dev/null)" = "200" ] && { ok=1; break; }
    sleep 1
  done
  [ "$ok" = "1" ] || { log "[헬스] API가 응답하지 않습니다(20초)"; return 1; }
  local fail=0
  for e in "/" "/dashboard/stats" "/teams"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$API$e" 2>/dev/null)
    log "[헬스] GET $e -> $code"
    [ "$code" = "200" ] || fail=1
  done
  return $fail
}

git fetch origin --prune -q || { log "[치명] git fetch 실패"; exit 1; }
TARGET=$(git rev-parse "$REMOTE_BRANCH")
CURRENT=$(git rev-parse HEAD)
log "현재 HEAD=${CURRENT:0:8}  →  대상 $REMOTE_BRANCH=${TARGET:0:8}  ($(git log -1 --format=%s "$REMOTE_BRANCH"))"

# 보호 데이터가 실수로 git 추적되고 있지 않은지(=reset 대상에 들어가 삭제 위험) 확인
for g in "${GUARD_PATHS[@]}"; do
  if git ls-files --error-unmatch "$g" >/dev/null 2>&1; then
    log "[중단] 보호경로 '$g' 가 git에 추적 중입니다(예상과 다름). 수동 점검이 필요합니다."; exit 3
  fi
done

# ── 미리보기 모드 ──────────────────────────────────────────────
if [ "${1:-}" = "--check" ]; then
  log "[--check] 적용 시 변경될 추적 파일 (현재 → 대상):"
  if [ "$CURRENT" = "$TARGET" ]; then echo "    (커밋 차이 없음)"; else
    git diff --name-status HEAD "$TARGET" | sed 's/^/    /' | head -80
  fi
  if ! git diff --quiet || ! git diff --cached --quiet; then
    log "[--check] 주의: 커밋되지 않은 추적 변경이 있어 배포 시 사라집니다:"
    git status --short | grep -E '^[ MARCD][MD]|^[MARC]' | sed 's/^/    /'
  fi
  log "[--check] player_photos/ · logs/ 등 untracked 데이터는 보존됩니다. 실제 변경 없이 종료."
  exit 0
fi
# ──────────────────────────────────────────────────────────────

# 커밋 안 된 추적 변경 가드 (프로덕션 직접 수정 → 소실 방지)
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "[경고] 커밋되지 않은 추적 변경이 있습니다(프로덕션 직접 수정으로 보입니다):"
  git status --short | grep -E '^[ MARCD][MD]|^[MARC]' | sed 's/^/    /'
  if [ "${FORCE:-0}" != "1" ]; then
    log "[중단] 이 변경은 reset --hard 로 사라집니다. git(main)에 반영 후 다시 실행하거나, 버려도 되면 FORCE=1 로 실행하세요."
    exit 2
  fi
  log "[FORCE] 변경을 버리고 진행합니다."
fi

if [ "$CURRENT" = "$TARGET" ]; then
  log "이미 최신 커밋입니다. API만 재시작합니다."
fi

ROLLBACK="$CURRENT"
log "배포 시작 (문제 시 롤백 기준 ${ROLLBACK:0:8})"
git reset --hard "$TARGET" || { log "[치명] reset 실패"; exit 1; }

# 라이브 데이터 생존 확인
for g in "${GUARD_PATHS[@]}"; do
  [ -e "$g" ] || { log "[치명] 보호경로 '$g' 가 사라졌습니다! 즉시 롤백합니다."; git reset --hard "$ROLLBACK"; sudo -n systemctl restart "$SERVICE"; exit 4; }
done

log "API($SERVICE) 재시작..."
sudo -n systemctl restart "$SERVICE" || { log "[치명] 재시작 실패. sudo 권한/서비스 확인 필요."; exit 1; }

if health; then
  log "[성공] 배포 완료 — ${TARGET:0:8} 라이브, 헬스체크 통과."
  exit 0
else
  log "[실패] 헬스체크 실패 → 자동 롤백 ${ROLLBACK:0:8}"
  git reset --hard "$ROLLBACK"
  sudo -n systemctl restart "$SERVICE"
  if health; then
    log "[롤백완료] 이전 상태로 복구되었습니다. 배포 내용을 점검하세요."
  else
    log "[위험] 롤백 후에도 비정상입니다. 수동 점검: sudo journalctl -u $SERVICE -n 50"
  fi
  exit 1
fi
