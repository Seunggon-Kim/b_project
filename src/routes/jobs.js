// 수집 작업이 마지막으로 언제 돌았는지 알려줍니다.
//
// EC2 의 `cron_status.json` 을 대신합니다. 그 파일은 서버 cron 이 15분마다
// 다시 쓰던 정적 파일인데, 이제 서버가 없습니다. Pages 는 정적 호스팅이라
// 실행 중에 파일을 못 바꾸므로 D1 에 기록하고 여기서 읽습니다.
//
// 쓰는 쪽: data_collection/record_job_run.py (GitHub Actions 각 단계 끝)
// 읽는 쪽: dashboard_js/pages/database-explorer.html 의 자동 수집 스케줄 표

import { json } from '../lib/respond.js';

export async function jobsStatus(request, env) {
  const rows = await env.DB.prepare(
    'SELECT job, last_run_at, status, note, duration_sec FROM meta_job_runs',
  ).all();

  // 화면이 `data.jobs[이름]` 을 바로 텍스트로 씁니다. 원래 cron_status.json
  // 이 그 모양이었고, 화면 코드를 최소로 바꾸려고 형태를 맞춥니다.
  const jobs = {};
  const details = {};
  for (const r of rows.results || []) {
    jobs[r.job] = r.last_run_at;
    details[r.job] = {
      last_run_at: r.last_run_at,
      status: r.status,
      note: r.note,
      duration_sec: r.duration_sec,
    };
  }
  return json({ jobs, details });
}
