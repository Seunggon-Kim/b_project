# -*- coding: utf-8 -*-
"""백필을 샤드별로 나눠 돌립니다.

## 왜 나누나

2008~2014 는 D1 두 개에 나뉘어 들어갑니다.

    kbo-pbp-2008-2011   2008 2009 2010 2011
    kbo-pbp-2012-2014   2012 2013 2014

지금은 커서 하나로 2008부터 순서대로만 갑니다. D1 하루 쓰기 한도가
**DB 단위**라면 두 샤드를 같은 날 동시에 채울 수 있어 걸리는 날이
절반이 됩니다. 계정 단위라면 둘째 작업이 한도에 걸려 멈출 뿐이고,
그때까지 넣은 것은 그대로 남습니다.

한도 범위는 Cloudflare 문서에 안 적혀 있어 실측해야 합니다.

## 커서 이름

작업마다 커서가 따로 있어야 서로의 진행을 덮지 않습니다. 기본값은
`pbp_2008_2014` 그대로입니다. **이미 진행 중인 커서라 이름을 바꾸면
지금까지 넣은 위치를 잃습니다.**
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from migration.shard_backfill import cursor_name, shard_for  # noqa: E402


class TestCursorName:
    def test_기본은_기존_이름을_지킵니다(self):
        # 이 이름이 바뀌면 지금까지의 진행 위치를 잃습니다.
        assert cursor_name(None, 2008, 2014) == 'pbp_2008_2014'

    def test_범위를_주면_범위로_이름을_만듭니다(self):
        assert cursor_name(None, 2012, 2014) == 'pbp_2012_2014'
        assert cursor_name(None, 2008, 2011) == 'pbp_2008_2011'

    def test_직접_준_이름이_가장_셉니다(self):
        assert cursor_name('pbp_test', 2012, 2014) == 'pbp_test'


class TestShardFor:
    def test_시즌마다_갈_D1_이_정해져_있습니다(self):
        assert shard_for(2008) == 'kbo-pbp-2008-2011'
        assert shard_for(2011) == 'kbo-pbp-2008-2011'
        assert shard_for(2012) == 'kbo-pbp-2012-2014'
        assert shard_for(2014) == 'kbo-pbp-2012-2014'

    def test_배정표에_없으면_None_입니다(self):
        assert shard_for(1999) is None
