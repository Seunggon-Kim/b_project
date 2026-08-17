import { json } from '../lib/respond.js';

/**
 * 선수 뉴스입니다. 원본 api/main.py:150-212 를 옮겼으나 **출처가 다릅니다.**
 *
 * 원본은 요청을 받을 때마다 구글 뉴스 RSS 를 직접 불렀습니다. 그 방식은
 * Cloudflare 엣지에서 쓸 수 없습니다. 다섯 번에 한 번만 200 이 오고 나머지는
 * Google 의 `Sorry...` 봇 차단 페이지입니다. 엣지 IP 를 전 세계가 공유해
 * 이미 한도가 차 있기 때문입니다(설계 문서 §7 위험 2 판정).
 *
 * 같은 URL 을 GitHub Actions 러너에서 부르면 다섯 번 모두 정상 응답합니다.
 * 그래서 Actions 가 하루 한 번 모아 `player_news` 표에 넣고, 여기서는 그것만
 * 읽습니다. 외부 호출이 없어 응답도 빨라졌습니다.
 *
 * **이 엔드포인트는 골든 비교 대상이 아닙니다.** 정답지는 한국 IP 에서 구글을
 * 직접 불러 뜬 것이라 내용이 같을 수 없습니다. 응답의 모양(키 이름과 타입)은
 * 그대로 지켜 프론트엔드는 고치지 않습니다.
 */
export async function news(request, env, ctx, params) {
  const playerId = params.id;
  try {
    // 원본 robust 조회: 문자열로 먼저, 숫자면 정수로 한 번 더.
    // players.player_id 에 문자열과 정수가 섞여 있어 생긴 처리입니다.
    const sql = `
      SELECT p.player_name, t.team_name
      FROM players p
      LEFT JOIN teams t ON p.team_id = t.team_id
      WHERE p.player_id = ?`;
    let row = await env.DB.prepare(sql).bind(playerId).first();
    let key = playerId;
    if (!row && /^\d+$/.test(playerId)) {
      key = Number.parseInt(playerId, 10);
      row = await env.DB.prepare(sql).bind(key).first();
    }
    if (!row) {
      return json({
        player_name: 'Unknown',
        news: [],
        error: 'Player lookup failed',
      });
    }

    // player_news 는 Actions 가 채웁니다. 아직 한 번도 안 돌았거나 그 선수에
    // 대한 기사가 없으면 빈 배열입니다. 원본도 실패 시 빈 배열이라 화면
    // 동작은 같습니다.
    const { results } = await env.DB.prepare(
      'SELECT title, link, press FROM player_news '
      + 'WHERE player_id = ? ORDER BY rank LIMIT 5',
    ).bind(String(key)).all();

    // desc 와 thumb 은 원본이 늘 고정값으로 채웁니다. 화면이 그 키를 읽으므로
    // 빼지 않습니다.
    const newsItems = results.map((r) => ({
      title: r.title,
      link: r.link,
      press: r.press,
      desc: '',
      thumb: null,
    }));

    return json({ player_name: row.player_name, news: newsItems });
  } catch (err) {
    // 원본은 예외 시 player_name 을 "Error" 로 돌려줍니다. 그대로 맞춥니다.
    return json({
      player_name: 'Error',
      news: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
