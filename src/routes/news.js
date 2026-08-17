import { json } from '../lib/respond.js';
import { decodeEntities } from '../lib/html.js';

function tagText(block, tag) {
  const m = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`).exec(block);
  if (!m) return null;
  const cdata = /^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/.exec(m[1]);
  return decodeEntities(cdata ? cdata[1] : m[1]).trim();
}

/**
 * Google News RSS 에서 항목을 뽑습니다.
 *
 * Workers 에 XML 파서가 없어 정규식으로 처리합니다. 필요한 필드가
 * title / link / source 셋뿐이고 구조가 단순해 이 정도로 충분합니다.
 */
export function parseRssItems(xml) {
  const items = [];
  for (const m of String(xml).matchAll(/<item[^>]*>([\s\S]*?)<\/item>/g)) {
    const block = m[1];
    let title = tagText(block, 'title') || 'No Title';
    const link = tagText(block, 'link') || '#';
    const press = tagText(block, 'source') || 'Google News';

    // 원본: if " - " in title: title = title.rsplit(" - ", 1)[0]
    const cut = title.lastIndexOf(' - ');
    if (cut !== -1) title = title.slice(0, cut);

    items.push({ title, link, press });
  }
  return items;
}

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
    if (!row && /^\d+$/.test(playerId)) {
      row = await env.DB.prepare(sql).bind(Number.parseInt(playerId, 10)).first();
    }
    if (!row) {
      return json({
        player_name: 'Unknown',
        news: [],
        error: 'Player lookup failed',
      });
    }

    const playerName = row.player_name;
    const teamName = row.team_name || '';
    const query = `${teamName} ${playerName} 야구`;
    const url = 'https://news.google.com/rss/search'
      + `?q=${encodeURIComponent(query)}&hl=ko&gl=KR&ceid=KR:ko`;

    const res = await fetch(url);
    const xml = await res.text();

    // 원본은 앞 5건만 씁니다. desc 와 thumb 은 늘 고정값입니다.
    const newsItems = parseRssItems(xml).slice(0, 5).map((i) => ({
      title: i.title,
      link: i.link,
      press: i.press,
      desc: '',
      thumb: null,
    }));

    return json({ player_name: playerName, news: newsItems });
  } catch (err) {
    // 원본은 예외 시 player_name 을 "Error" 로 돌려줍니다. 그대로 맞춥니다.
    return json({
      player_name: 'Error',
      news: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
