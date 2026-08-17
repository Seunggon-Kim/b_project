-- 매 쿼리마다 자동 인덱스를 빌드하던 것을 실인덱스로 대체합니다.
CREATE INDEX IF NOT EXISTS idx_wrc_season ON wrc_plus_comparison(season);
CREATE INDEX IF NOT EXISTS idx_wpf_batter_season ON weighted_pf_by_batter_season(batter_ID, season);
