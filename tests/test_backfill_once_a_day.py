# -*- coding: utf-8 -*-
"""하루에 한 번만 밀어 넣습니다.

## 왜 필요한가

D1 무료는 하루 10만 **계상 쓰기**입니다. `play_by_play` 는 인덱스가
셋이라 행 하나가 4로 계상됩니다. 백필 22,000행이면 88,000 이고,
daily 의 다른 적재까지 더하면 여유가 3,000 남짓입니다.

사람이 손으로 한 번 돌린 날 daily 가 또 돌면 176,000 이 됩니다.
한도를 넘으면 **백필만 실패하는 게 아니라 그날 경기 결과 적재까지
같이 막힙니다.** 그게 더 큰 손해입니다.

한도는 UTC 자정에 리셋되므로 UTC 날짜로 셉니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from migration.shard_backfill import already_ran_today  # noqa: E402


class TestAlreadyRanToday:
    def test_같은_UTC_날짜면_이미_돈_것입니다(self):
        assert already_ran_today('2026-08-29 11:16:11', '2026-08-29') is True

    def test_어제면_다시_돌립니다(self):
        assert already_ran_today('2026-08-28 11:16:11', '2026-08-29') is False

    def test_기록이_없으면_다시_돌립니다(self):
        assert already_ran_today(None, '2026-08-29') is False
        assert already_ran_today('', '2026-08-29') is False

    def test_자정_직후도_같은_날로_봅니다(self):
        # daily 크론은 18:33 UTC 입니다. 지연돼도 같은 UTC 날짜입니다.
        assert already_ran_today('2026-08-29 00:00:01', '2026-08-29') is True

    def test_날짜만_있어도_읽습니다(self):
        assert already_ran_today('2026-08-29', '2026-08-29') is True
