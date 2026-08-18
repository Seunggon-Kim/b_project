import { test } from 'node:test';
import assert from 'node:assert/strict';

import { jobsStatus } from '../src/routes/jobs.js';
import { cacheControlFor } from '../src/lib/cachepolicy.js';

function fakeEnv(results) {
  return { DB: { prepare: () => ({ all: async () => ({ results }) }) } };
}

test('화면이 쓰는 jobs 맵을 만듭니다', async () => {
  // 원래 cron_status.json 이 { jobs: { 이름: "시각" } } 였습니다.
  // 화면 코드가 그 모양을 그대로 읽으므로 형태를 지킵니다.
  const res = await jobsStatus({}, fakeEnv([
    { job: 'pbp', last_run_at: '2026-08-18 03:40', status: 'ok', note: '3경기', duration_sec: 62 },
    { job: 'news', last_run_at: '2026-08-18 04:10', status: 'fail', note: null, duration_sec: null },
  ]));
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.deepEqual(body.jobs, {
    pbp: '2026-08-18 03:40',
    news: '2026-08-18 04:10',
  });
});

test('상태와 메모는 details 로 따로 줍니다', async () => {
  // 시각만 보면 실패한 실행도 성공처럼 보입니다.
  const res = await jobsStatus({}, fakeEnv([
    { job: 'news', last_run_at: '2026-08-18 04:10', status: 'fail', note: '절반 미만', duration_sec: 9 },
  ]));
  const body = await res.json();
  assert.equal(body.details.news.status, 'fail');
  assert.equal(body.details.news.note, '절반 미만');
  assert.equal(body.details.news.duration_sec, 9);
});

test('기록이 없어도 빈 객체를 줍니다', async () => {
  // 화면이 여기서 터지면 데이터 탐색기 전체가 안 뜹니다.
  const res = await jobsStatus({}, fakeEnv([]));
  const body = await res.json();
  assert.deepEqual(body.jobs, {});
  assert.deepEqual(body.details, {});
});

test('results 가 없어도 터지지 않습니다', async () => {
  const env = { DB: { prepare: () => ({ all: async () => ({}) }) } };
  const res = await jobsStatus({}, env);
  assert.equal((await res.json()).jobs.pbp, undefined);
});

test('수집 주기보다 짧게 캐시합니다', async () => {
  // 하루 한 번 도는 값이지만, 오늘 돌았는지 확인하려고 보는 화면입니다.
  // 한 시간이나 굳으면 "돌았나?"를 바로 확인할 수 없습니다.
  const v = cacheControlFor('/jobs/status');
  assert.match(v, /max-age=(60|120|300)\b/);
});
