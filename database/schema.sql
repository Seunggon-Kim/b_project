-- KBO 야구 데이터베이스 스키마

-- 팀 정보
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    team_name TEXT NOT NULL,
    team_name_en TEXT,
    city TEXT,
    founded_year INTEGER,
    stadium TEXT
);

-- 경기 정보
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    game_date DATE NOT NULL,
    season INTEGER NOT NULL,
    game_type TEXT CHECK(game_type IN ('정규시즌', '포스트시즌')) DEFAULT '정규시즌',
    home_team_id TEXT NOT NULL,
    away_team_id TEXT NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    stadium TEXT,
    attendance INTEGER,
    game_time_minutes INTEGER,
    weather TEXT,
    temperature REAL,
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);

-- 선수 정보
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    player_name TEXT NOT NULL,
    team_id TEXT,
    position TEXT,
    birth_date DATE,
    height_cm INTEGER,
    weight_kg INTEGER,
    bats TEXT CHECK(bats IN ('우', '좌', '양')),
    throws TEXT CHECK(throws IN ('우', '좌')),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Play-by-Play 문자중계 데이터
CREATE TABLE IF NOT EXISTS play_by_play (
    pbp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pitch_type TEXT,
    pitcher TEXT,
    batter TEXT,
    pitcher_ID TEXT,
    batter_ID TEXT,
    speed REAL,
    pitch_result TEXT,
    pa_result TEXT,
    pa_result_detail TEXT,
    description TEXT,
    balls INTEGER,
    strikes INTEGER,
    outs INTEGER,
    inning INTEGER,
    inning_topbot TEXT,
    score_away INTEGER,
    score_home INTEGER,
    outs_on_play INTEGER,
    runs_scored INTEGER,
    stands TEXT,
    throws TEXT,
    on_1b TEXT,
    on_2b TEXT,
    on_3b TEXT,
    pos_1 TEXT,
    pos_2 TEXT,
    pos_3 TEXT,
    pos_4 TEXT,
    pos_5 TEXT,
    pos_6 TEXT,
    pos_7 TEXT,
    pos_8 TEXT,
    pos_9 TEXT,
    on_1b_id TEXT,
    on_2b_id TEXT,
    on_3b_id TEXT,
    pos_1_id TEXT,
    pos_2_id TEXT,
    pos_3_id TEXT,
    pos_4_id TEXT,
    pos_5_id TEXT,
    pos_6_id TEXT,
    pos_7_id TEXT,
    pos_8_id TEXT,
    pos_9_id TEXT,
    px REAL,
    pz REAL,
    pfx_x REAL,
    pfx_z REAL,
    pfx_x_raw REAL,
    pfx_z_raw REAL,
    x0 REAL,
    z0 REAL,
    sz_top REAL,
    sz_bot REAL,
    y0 REAL,
    vx0 REAL,
    vy0 REAL,
    vz0 REAL,
    ax REAL,
    ay REAL,
    az REAL,
    game_date DATE,
    home TEXT,
    away TEXT,
    home_alias TEXT,
    away_alias TEXT,
    stadium TEXT,
    referee TEXT,
    pa_number INTEGER,
    pitch_number INTEGER,
    pitchID TEXT,
    gameID TEXT
);

-- 경기별 팀 통계
CREATE TABLE IF NOT EXISTS game_team_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    runs INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    left_on_base INTEGER DEFAULT 0,
    doubles INTEGER DEFAULT 0,
    triples INTEGER DEFAULT 0,
    home_runs INTEGER DEFAULT 0,
    walks INTEGER DEFAULT 0,
    strikeouts INTEGER DEFAULT 0,
    stolen_bases INTEGER DEFAULT 0,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE(game_id, team_id)
);

-- 인덱스 생성 (조회 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_pbp_game ON play_by_play(gameID);
CREATE INDEX IF NOT EXISTS idx_pbp_batter ON play_by_play(batter_ID);
CREATE INDEX IF NOT EXISTS idx_pbp_pitcher ON play_by_play(pitcher_ID);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_game_stats_team ON game_team_stats(team_id);

-- 샘플 팀 데이터 삽입
INSERT OR IGNORE INTO teams (team_id, team_name, team_name_en, city, stadium) VALUES
('LG', 'LG 트윈스', 'LG Twins', '서울', '잠실야구장'),
('KT', 'KT 위즈', 'KT Wiz', '수원', '수원 KT 위즈 파크'),
('SSG', 'SSG 랜더스', 'SSG Landers', '인천', 'SSG 랜더스필드'),
('NC', 'NC 다이노스', 'NC Dinos', '창원', '창원NC파크'),
('두산', '두산 베어스', 'Doosan Bears', '서울', '잠실야구장'),
('KIA', 'KIA 타이거즈', 'KIA Tigers', '광주', '광주-기아 챔피언스 필드'),
('롯데', '롯데 자이언츠', 'Lotte Giants', '부산', '사직야구장'),
('삼성', '삼성 라이온즈', 'Samsung Lions', '대구', '대구 삼성 라이온즈 파크'),
('한화', '한화 이글스', 'Hanwha Eagles', '대전', '한화생명 이글스파크'),
('키움', '키움 히어로즈', 'Kiwoom Heroes', '서울', '고척 스카이돔');
