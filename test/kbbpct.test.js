// K%·BB% 를 저장된 컬럼에 기대지 않게 지킵니다.
//
// `strikeout_per_pa` 와 `base_on_balls_per_pa` 는 **2025 에만 값이
// 있습니다.** 나머지 열한 시즌은 전부 NULL 입니다.
//
//   2026  284명 중 284명 NULL
//   2025  281명 중   0명 NULL
//   2024  291명 중 291명 NULL
//
// KBO 기록실이 이 값을 주지 않아 수집기가 채울 수 없습니다(셀레니움
// 때도 없었습니다). 2025 값만 옛 파이프라인이 남긴 것입니다. 그래서
// 홈 화면의 K%·BB%·K-BB% 순위와 기록실의 두 컬럼이 2025 말고는
// 전부 비어 있었습니다. 사용자가 화면에서 발견했습니다.
//
// 상대타자로 나누면 그대로 나옵니다. 2025 저장값과 대조해 맞췄습니다.
// 컬럼을 새로 채우지 않는 이유는 team_id·is_active 와 같습니다.
// 아무도 갱신하지 않는 컬럼은 곧 낡습니다.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

const FILES = ['src/routes/leaders.js', 'src/routes/stats.js'];

test('저장된 K%·BB% 컬럼을 그대로 읽지 않습니다', () => {
  const bad = [];
  for (const f of FILES) {
    readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
      if (line.trim().startsWith('//')) return;
      // `ps.strikeout_per_pa AS ...` 처럼 컬럼을 직접 읽는 모양입니다.
      if (/ps\.(strikeout_per_pa|base_on_balls_per_pa)\b/.test(line)) {
        bad.push(`${f}:${i + 1}  ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(bad, [],
    `2025 말고는 전부 NULL 인 컬럼입니다:\n${bad.join('\n')}`);
});

test('상대타자로 나눠 계산합니다', () => {
  for (const f of FILES) {
    const src = readFileSync(f, 'utf8');
    assert.ok(
      /ps\.strikeout \* 100\.0 \/ ps\.total_batters_faced/.test(src),
      `${f} 에 K% 계산이 없습니다`);
    assert.ok(
      /ps\.base_on_balls \* 100\.0 \/ ps\.total_batters_faced/.test(src),
      `${f} 에 BB% 계산이 없습니다`);
  }
});

test('상대타자가 0 이면 나누지 않습니다', () => {
  // 0 으로 나누면 SQLite 는 NULL 을 주지만, 의도를 드러내 둡니다.
  for (const f of FILES) {
    const src = readFileSync(f, 'utf8');
    assert.ok(/total_batters_faced > 0/.test(src),
      `${f} 에 0 나누기 방어가 없습니다`);
  }
});

test('기록실이 화면과 같은 이름으로 내보냅니다', () => {
  // player-stats.html 이 이 두 이름으로 읽습니다. 이름을 바꾸면
  // 화면 컬럼이 통째로 빕니다.
  const src = readFileSync('src/routes/stats.js', 'utf8');
  assert.ok(src.includes('AS strikeout_per_pa'));
  assert.ok(src.includes('AS base_on_balls_per_pa'));

  const html = readFileSync('dashboard_js/pages/player-stats.html', 'utf8');
  assert.ok(html.includes("key: 'strikeout_per_pa'"));
  assert.ok(html.includes("key: 'base_on_balls_per_pa'"));
});

test('K-BB% 는 둘 다 있을 때만 냅니다', () => {
  const src = readFileSync('src/routes/leaders.js', 'utf8');
  assert.match(src, /_kpct === null \|\| x\._bbpct === null \? null/,
    '한쪽만 있을 때 잘못된 값을 낼 수 있습니다');
});
