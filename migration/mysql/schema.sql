CREATE TABLE `franchises` (
  `franchise_id` VARCHAR(16) NOT NULL,
  `current_name` VARCHAR(16),
  `first_season` INT NOT NULL,
  `last_season` INT,
  `note` VARCHAR(128),
  PRIMARY KEY (`franchise_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `futures_games` (
  `game_id` VARCHAR(32) NOT NULL,
  `game_date` DATE NOT NULL,
  `game_time` VARCHAR(16),
  `season` INT NOT NULL,
  `series_id` INT DEFAULT 0,
  `away_code` VARCHAR(16) NOT NULL,
  `home_code` VARCHAR(16) NOT NULL,
  `away_name` VARCHAR(16) NOT NULL,
  `home_name` VARCHAR(16) NOT NULL,
  `away_score` INT,
  `home_score` INT,
  `stadium` VARCHAR(16),
  `status` VARCHAR(32),
  `updated_at` VARCHAR(64),
  PRIMARY KEY (`game_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `futures_season_stats` (
  `player_id` INT UNSIGNED NOT NULL,
  `season` INT NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  `player_name` VARCHAR(16),
  `team` VARCHAR(16),
  `AVG` VARCHAR(16),
  `G` VARCHAR(16),
  `PA` VARCHAR(16),
  `AB` VARCHAR(16),
  `R` VARCHAR(16),
  `H` VARCHAR(16),
  `double_hit` VARCHAR(16),
  `triple_hit` VARCHAR(16),
  `HR` VARCHAR(16),
  `RBI` VARCHAR(16),
  `SB` VARCHAR(16),
  `BB` VARCHAR(16),
  `HBP` VARCHAR(16),
  `SO` VARCHAR(16),
  `SLG` VARCHAR(16),
  `OBP` VARCHAR(16),
  `ERA` VARCHAR(16),
  `W` VARCHAR(16),
  `L` VARCHAR(16),
  `SV` VARCHAR(16),
  `HLD` VARCHAR(16),
  `WPCT` VARCHAR(16),
  `IP` VARCHAR(16),
  `ER` VARCHAR(16),
  PRIMARY KEY (`player_id`, `season`, `kind`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `futures_teams` (
  `code` VARCHAR(16) NOT NULL,
  `kbo_name` VARCHAR(16) NOT NULL,
  `display_name` VARCHAR(16) NOT NULL,
  `emblem_code` VARCHAR(16),
  `division` VARCHAR(16),
  `team_type` VARCHAR(32),
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `games` (
  `game_id` VARCHAR(64) NOT NULL,
  `game_date` INT NOT NULL,
  `season` INT NOT NULL,
  `game_type` VARCHAR(16) DEFAULT '정규시즌',
  `home_team_id` VARCHAR(16) NOT NULL,
  `away_team_id` VARCHAR(16) NOT NULL,
  `home_score` INT,
  `away_score` INT,
  `stadium` VARCHAR(16),
  `attendance` INT,
  `game_time_minutes` INT,
  `weather` VARCHAR(16),
  `temperature` DOUBLE,
  PRIMARY KEY (`game_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_official_batter_stats` (
  `player_id` INT UNSIGNED NOT NULL,
  `season` INT NOT NULL,
  `player_name` VARCHAR(16),
  `player_team` VARCHAR(16),
  `batting_average` DOUBLE,
  `games` INT,
  `plate_appearance` INT,
  `at_bat` INT,
  `run` INT,
  `single` INT,
  `double` INT,
  `triple` INT,
  `home_run` INT,
  `total_bases` INT,
  `run_batted_in` INT,
  `sacrifice_bunts` INT,
  `sacrifice_fly` INT,
  `base_on_balls` INT,
  `intentional_base_on_balls` INT,
  `hit_by_pitch` INT,
  `strikeout` INT,
  `ground_into_double_play` INT,
  `slugging_percentage` DOUBLE,
  `on_base_percentage` DOUBLE,
  `on_base_plus_slugging` DOUBLE,
  `multi_hits` INT,
  `runners_in_scoring_position` DOUBLE,
  `pinch_hit_batting_average` DOUBLE,
  `extra_base_hits` INT,
  `ground_outs` INT,
  `air_outs` INT,
  `go_ao` VARCHAR(16),
  `gw_rbi` INT,
  `strikeout_per_pa` DOUBLE,
  `base_on_balls_per_pa` DOUBLE,
  `bb_k` VARCHAR(16),
  `p_pa` DOUBLE,
  `isop` DOUBLE,
  `extended_runs` DOUBLE,
  `gross_production_average` DOUBLE,
  `created_at` DATETIME,
  `updated_at` DATETIME,
  PRIMARY KEY (`player_id`, `season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_official_pitcher_stats` (
  `player_id` INT UNSIGNED NOT NULL,
  `season` INT NOT NULL,
  `player_name` VARCHAR(16),
  `player_team` VARCHAR(16),
  `earned_run_average` DOUBLE,
  `games` INT,
  `wins` INT,
  `losses` INT,
  `save` INT,
  `hold` INT,
  `winning_percentage` DOUBLE,
  `innings_pitched` VARCHAR(16),
  `hits` INT,
  `home_run` INT,
  `base_on_balls` INT,
  `hit_by_pitch` INT,
  `strikeout` INT,
  `run` INT,
  `earned_run` INT,
  `walks_plus_hits_per_inning_pitched` DOUBLE,
  `complete_game` INT,
  `shutout` INT,
  `quality_start` INT,
  `blown_save` INT,
  `total_batters_faced` INT,
  `number_of_pitchers` INT,
  `batting_average` DOUBLE,
  `double` INT,
  `triple` INT,
  `sacrifice_bunts` INT,
  `sacrifice_fly` INT,
  `intentional_base_on_balls` INT,
  `wild_pitch` INT,
  `balk` INT,
  `games_started` INT,
  `wins_game_started` INT,
  `wins_game_relieved` INT,
  `games_finished` INT,
  `save_opportunity` INT,
  `total_saves` INT,
  `ground_into_double_play` INT,
  `ground_outs` INT,
  `air_outs` INT,
  `go_ao` VARCHAR(16),
  `batting_average_on_balls_in_play` DOUBLE,
  `p_g` DOUBLE,
  `p_ip` DOUBLE,
  `k_9` DOUBLE,
  `bb_9` DOUBLE,
  `strikeout_per_pa` DOUBLE,
  `base_on_balls_per_pa` DOUBLE,
  `k_bb` VARCHAR(16),
  `on_base_percentage` DOUBLE,
  `slugging_percentage` DOUBLE,
  `on_base_plus_slugging` DOUBLE,
  `created_at` DATETIME,
  `updated_at` DATETIME,
  PRIMARY KEY (`player_id`, `season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_roster` (
  `team` VARCHAR(16) NOT NULL,
  `name` VARCHAR(16) NOT NULL,
  `back_number` VARCHAR(16) NOT NULL,
  `role` VARCHAR(16) NOT NULL,
  `player_id` INT UNSIGNED,
  `as_of` DATE NOT NULL,
  `league` VARCHAR(16) NOT NULL DEFAULT '1군',
  PRIMARY KEY (`team`, `name`, `back_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_roster_moves` (
  `move_date` DATE NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  `team` VARCHAR(16) NOT NULL,
  `name` VARCHAR(16) NOT NULL,
  `position` VARCHAR(16),
  `player_id` INT UNSIGNED,
  PRIMARY KEY (`move_date`, `kind`, `team`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_run_values_by_season` (
  `season` INT NOT NULL,
  `event_type` VARCHAR(32) NOT NULL,
  `rv_mean` DOUBLE,
  `n_obs` INT,
  PRIMARY KEY (`season`, `event_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `kbo_woba_weights_by_season` (
  `season` INT NOT NULL AUTO_INCREMENT,
  `PA` DOUBLE,
  `AB` DOUBLE,
  `H` DOUBLE,
  `BB` DOUBLE,
  `HBP` DOUBLE,
  `SF` DOUBLE,
  `OBP` DOUBLE,
  `raw_RV_1B` DOUBLE,
  `raw_RV_2B` DOUBLE,
  `raw_RV_3B` DOUBLE,
  `raw_RV_HR` DOUBLE,
  `raw_RV_uBB` DOUBLE,
  `raw_RV_HBP` DOUBLE,
  `avg_out_RV` DOUBLE,
  `raw_lg_wOBA` DOUBLE,
  `wOBA_scale` DOUBLE,
  `fg_w1B` DOUBLE,
  `fg_w2B` DOUBLE,
  `fg_w3B` DOUBLE,
  `fg_wHR` DOUBLE,
  `fg_wBB` DOUBLE,
  `fg_wHBP` DOUBLE,
  PRIMARY KEY (`season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `korean_series_champion` (
  `season` INT NOT NULL AUTO_INCREMENT,
  `team_name` VARCHAR(16) NOT NULL,
  `note` VARCHAR(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `meta_backfill` (
  `name` VARCHAR(32) NOT NULL,
  `last_date` INT NOT NULL,
  `rows_loaded` INT NOT NULL DEFAULT 0,
  `updated_at` DATETIME,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `meta_job_runs` (
  `job` VARCHAR(32) NOT NULL,
  `last_run_at` VARCHAR(32) NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `note` VARCHAR(128),
  `duration_sec` INT,
  PRIMARY KEY (`job`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `meta_table_counts` (
  `name` VARCHAR(64) NOT NULL,
  `n` INT NOT NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `play_by_play` (
  `pbp_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `pitch_type` VARCHAR(16),
  `pitcher` VARCHAR(16),
  `batter` VARCHAR(16),
  `pitcher_ID` INT UNSIGNED,
  `batter_ID` INT,
  `speed` DOUBLE,
  `pitch_result` VARCHAR(32),
  `pa_result` VARCHAR(32),
  `pa_result_detail` VARCHAR(32),
  `description` VARCHAR(1024),
  `balls` INT,
  `strikes` INT,
  `outs` INT,
  `inning` INT,
  `inning_topbot` VARCHAR(16),
  `score_away` INT,
  `score_home` INT,
  `outs_on_play` INT,
  `runs_scored` INT,
  `stands` VARCHAR(16),
  `throws` VARCHAR(16),
  `on_1b` VARCHAR(16),
  `on_2b` VARCHAR(16),
  `on_3b` VARCHAR(16),
  `pos_1` VARCHAR(16),
  `pos_2` VARCHAR(16),
  `pos_3` VARCHAR(16),
  `pos_4` VARCHAR(16),
  `pos_5` VARCHAR(16),
  `pos_6` VARCHAR(16),
  `pos_7` VARCHAR(16),
  `pos_8` VARCHAR(16),
  `pos_9` VARCHAR(16),
  `on_1b_id` INT UNSIGNED,
  `on_2b_id` INT UNSIGNED,
  `on_3b_id` INT UNSIGNED,
  `pos_1_id` INT UNSIGNED,
  `pos_2_id` INT UNSIGNED,
  `pos_3_id` INT UNSIGNED,
  `pos_4_id` INT UNSIGNED,
  `pos_5_id` INT UNSIGNED,
  `pos_6_id` INT UNSIGNED,
  `pos_7_id` INT UNSIGNED,
  `pos_8_id` INT UNSIGNED,
  `pos_9_id` INT UNSIGNED,
  `px` DOUBLE,
  `pz` DOUBLE,
  `pfx_x` DOUBLE,
  `pfx_z` DOUBLE,
  `pfx_x_raw` DOUBLE,
  `pfx_z_raw` DOUBLE,
  `x0` DOUBLE,
  `z0` DOUBLE,
  `sz_top` DOUBLE,
  `sz_bot` DOUBLE,
  `y0` DOUBLE,
  `vx0` DOUBLE,
  `vy0` DOUBLE,
  `vz0` DOUBLE,
  `ax` DOUBLE,
  `ay` DOUBLE,
  `az` DOUBLE,
  `game_date` INT,
  `home` VARCHAR(16),
  `away` VARCHAR(16),
  `home_alias` VARCHAR(16),
  `away_alias` VARCHAR(16),
  `stadium` VARCHAR(16),
  `referee` VARCHAR(16),
  `pa_number` INT,
  `pitch_number` INT,
  `pitchID` VARCHAR(32),
  `gameID` VARCHAR(64),
  PRIMARY KEY (`pbp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `players` (
  `player_id` INT UNSIGNED NOT NULL,
  `player_name` VARCHAR(16) NOT NULL,
  `team_id` VARCHAR(16),
  `back_number` INT,
  `position` VARCHAR(16),
  `throw` VARCHAR(16),
  `bat` VARCHAR(16),
  `birthday` INT,
  `height` INT,
  `weight` INT,
  `career` VARCHAR(128),
  `draft_year` VARCHAR(16),
  `draft_order` VARCHAR(64),
  `signing_bonus` INT,
  `salary` BIGINT,
  `image_url` VARCHAR(255),
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`player_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `re24_matrix_by_season` (
  `season` INT NOT NULL,
  `outs_before` INT NOT NULL,
  `base_state` INT NOT NULL,
  `re_value` DOUBLE,
  `n_obs` INT,
  PRIMARY KEY (`season`, `outs_before`, `base_state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `self_park_factor` (
  `season` INT NOT NULL,
  `stadium` VARCHAR(32) NOT NULL,
  `games` INT,
  `run_pf` INT,
  `single_pf` INT,
  `double_pf` INT,
  `triple_pf` INT,
  `hr_pf` INT,
  `slg_pf` INT,
  `source` VARCHAR(32) DEFAULT 'self_pbp_3y',
  `captured_at` DATETIME,
  `yrs` INT,
  `window` VARCHAR(32),
  PRIMARY KEY (`season`, `stadium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `stadium_dim` (
  `stadium_id` INT NOT NULL AUTO_INCREMENT,
  `full_name` VARCHAR(32) NOT NULL,
  `primary_team` VARCHAR(16),
  `active_from` INT,
  `active_to` INT,
  `is_temporary` INT DEFAULT 0,
  `note` VARCHAR(64),
  PRIMARY KEY (`stadium_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `statiz_park_factor` (
  `season` INT NOT NULL,
  `stadium` VARCHAR(32) NOT NULL,
  `games` INT,
  `run_pf` INT,
  `single_pf` INT,
  `double_pf` INT,
  `triple_pf` INT,
  `hr_pf` INT,
  `slg_pf` INT,
  `source` VARCHAR(16) DEFAULT 'Statiz',
  `captured_at` DATETIME,
  PRIMARY KEY (`season`, `stadium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `statiz_yearly_constants` (
  `season` INT NOT NULL AUTO_INCREMENT,
  `woba` DOUBLE,
  `woba_scale` DOUBLE,
  `ebb` DOUBLE,
  `single_w` DOUBLE,
  `double_w` DOUBLE,
  `triple_w` DOUBLE,
  `hr_w` DOUBLE,
  `sb2` DOUBLE,
  `sb3` DOUBLE,
  `cs2` DOUBLE,
  `cs3` DOUBLE,
  `r_per_epa` DOUBLE,
  `rpw` DOUBLE,
  `cfip` DOUBLE,
  `source` VARCHAR(16) DEFAULT 'Statiz',
  `captured_at` DATETIME,
  PRIMARY KEY (`season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `team_logos` (
  `code` VARCHAR(16) NOT NULL,
  `name` VARCHAR(16),
  `league` VARCHAR(16) DEFAULT 'futures',
  `mime` VARCHAR(32) NOT NULL,
  `source` VARCHAR(32),
  `image` MEDIUMBLOB NOT NULL,
  `byte_size` INT,
  `updated_at` VARCHAR(64),
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `team_season_rank` (
  `franchise_id` VARCHAR(16),
  `season` INT NOT NULL,
  `team_name` VARCHAR(16) NOT NULL,
  `league` VARCHAR(16) NOT NULL DEFAULT '',
  `rank` INT,
  `games` INT,
  `wins` INT,
  `losses` INT,
  `draws` INT,
  `pct` VARCHAR(16),
  `gb` VARCHAR(16),
  PRIMARY KEY (`season`, `team_name`, `league`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `team_seasons` (
  `franchise_id` VARCHAR(16) NOT NULL,
  `season` INT NOT NULL,
  `team_name` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`franchise_id`, `season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `team_stadium_by_season` (
  `player_team` VARCHAR(16),
  `season` INT,
  `stadium` VARCHAR(32)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `teams` (
  `team_id` VARCHAR(16) NOT NULL,
  `team_name` VARCHAR(16) NOT NULL,
  `team_name_en` VARCHAR(32),
  `city` VARCHAR(16),
  `founded_year` INT,
  `stadium` VARCHAR(32),
  PRIMARY KEY (`team_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `weighted_pf_by_batter_season` (
  `batter_ID` INT UNSIGNED,
  `season` INT,
  `n_PA` INT,
  `wpf_run` DOUBLE,
  `wpf_hr` DOUBLE,
  `wpf_slg` DOUBLE,
  `home_stadium` VARCHAR(32),
  `home_pa_n` INT,
  `home_run_pf` DOUBLE,
  `home_hr_pf` DOUBLE,
  `home_slg_pf` DOUBLE,
  `home_share` DOUBLE,
  `run_pf_diff` DOUBLE,
  `run_pf_diff_pct` DOUBLE,
  `hr_pf_diff_pct` DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `wrc_plus_comparison` (
  `batter_ID` INT UNSIGNED,
  `season` INT,
  `PA` INT,
  `OBP_denom` INT,
  `wOBA` DOUBLE,
  `lg_wOBA` DOUBLE,
  `wOBA_scale` DOUBLE,
  `wRAA_FG` DOUBLE,
  `home_run_pf` DOUBLE,
  `wpf_run` DOUBLE,
  `pf_home` DOUBLE,
  `pf_half` DOUBLE,
  `pf_weighted` DOUBLE,
  `wRC_home` DOUBLE,
  `wRC_half` DOUBLE,
  `wRC_weighted` DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `run_expectancy` (
  `season` SMALLINT NOT NULL,
  `bases` TINYINT NOT NULL,
  `outs` TINYINT NOT NULL,
  `balls` TINYINT NOT NULL,
  `strikes` TINYINT NOT NULL,
  `re` DOUBLE NOT NULL,
  `n` INT NOT NULL,
  PRIMARY KEY (`season`, `bases`, `outs`, `balls`, `strikes`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `pitch_run_value` (
  `season` SMALLINT NOT NULL,
  `pitcher_ID` INT NOT NULL,
  `pitch_type` VARCHAR(20) NOT NULL,
  `stands` CHAR(1) NOT NULL,
  `n` INT NOT NULL,
  `rv` DOUBLE NOT NULL,
  PRIMARY KEY (`season`, `pitcher_ID`, `pitch_type`, `stands`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `pitch_run_value_zone` (
  `season` SMALLINT NOT NULL,
  `pitcher_ID` INT NOT NULL,
  `zone` VARCHAR(8) NOT NULL,
  `n` INT NOT NULL,
  `rv` DOUBLE NOT NULL,
  PRIMARY KEY (`season`, `pitcher_ID`, `zone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `plate_discipline_league` (
  `season` SMALLINT NOT NULL,
  `n` INT NOT NULL,
  `pd_n` INT NOT NULL,
  `sw` INT NOT NULL,
  `wh` INT NOT NULL,
  `ct` INT NOT NULL,
  `cs` INT NOT NULL,
  `z_n` INT NOT NULL,
  `o_n` INT NOT NULL,
  `z_sw` INT NOT NULL,
  `o_sw` INT NOT NULL,
  `z_ct` INT NOT NULL,
  `o_ct` INT NOT NULL,
  `edge_n` INT NOT NULL,
  `fp_n` INT NOT NULL,
  `fp_str` INT NOT NULL,
  `mb_n` INT NOT NULL,
  `mb_sw` INT NOT NULL,
  PRIMARY KEY (`season`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
