// HTML 엔티티 디코드와 태그 제거.
//
// 원본 api/main.py 는 `html.unescape` 와 `re.sub(r'<[^>]+>', '', c)` 를 씁니다.
// 동작을 같게 맞추는 것이 목적이라, 더 똑똑한 파서를 쓰지 않습니다.
// Workers 의 HTMLRewriter 는 스트리밍 변환용이라 문자열 추출에는 맞지 않습니다.

const NAMED = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
  nbsp: ' ', ensp: ' ', emsp: ' ', thinsp: ' ',
};

export function decodeEntities(text) {
  return String(text).replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (whole, body) => {
    if (body[0] === '#') {
      const hex = body[1] === 'x' || body[1] === 'X';
      const code = Number.parseInt(hex ? body.slice(2) : body.slice(1),
                                   hex ? 16 : 10);
      return Number.isNaN(code) ? whole : String.fromCodePoint(code);
    }
    const v = NAMED[body.toLowerCase()];
    return v === undefined ? whole : v;
  });
}

export function stripTags(html) {
  return decodeEntities(String(html).replace(/<[^>]+>/g, ''));
}
