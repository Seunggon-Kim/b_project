import { json } from '../lib/respond.js';

/**
 * 팀 로고입니다. 원본 api/main.py:1374-1388.
 *
 * `team_logos` 표에 이미지가 BLOB 으로 들어 있고 `mime` 컬럼이 형식을
 * 알려 줍니다(png·svg 둘 다 있습니다). D1 은 BLOB 을 ArrayBuffer 로 주므로
 * 그대로 Response 본문에 넣습니다.
 *
 * **정답지가 SHA-256 으로 대조합니다.** 바이트가 하나라도 달라지면
 * 불일치입니다. 다시 인코딩하거나 문자열로 거치지 마십시오.
 */
export async function logo(request, env, ctx, params) {
  const code = String(params.code || '').toUpperCase();

  const row = await env.DB
    .prepare('SELECT mime, image FROM team_logos WHERE code = ?')
    .bind(code)
    .first();

  if (!row) {
    // 원본은 HTTPException(404, "logo not found") 를 던집니다.
    return json({ detail: 'logo not found' }, 404);
  }

  return new Response(toBytes(row.image), {
    headers: {
      'content-type': row.mime,
      'cache-control': 'public, max-age=86400',
      'access-control-allow-origin': '*',
    },
  });
}

/**
 * D1 이 돌려준 BLOB 을 Response 에 넣을 수 있는 형태로 바꿉니다.
 *
 * D1 의 JS 바인딩은 BLOB 을 **숫자 배열**(`number[]`)로 줍니다.
 * ArrayBuffer 가 아닙니다. 그대로 `new Response(...)` 에 넘기면 본문이
 * 0바이트가 됩니다. 그것을 모르고 넘겼다가 로고가 빈 채로 나갔습니다.
 *
 * 형태가 바뀔 수 있으니 세 경우를 다 받습니다.
 */
function toBytes(value) {
  if (value instanceof ArrayBuffer) return value;
  if (ArrayBuffer.isView(value)) return value;
  if (Array.isArray(value)) return new Uint8Array(value);
  return value;
}
