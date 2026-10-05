-- 구종 가치(설계 docs/superpowers/specs/2026-10-04-pitch-run-value-design.md).
-- MySQL 에만 둡니다. schema_types.json 에 넣지 않습니다(D1 대조 대상 아님).
-- 만들기는 migrator 계정으로 한 번(evan 허락). 쓰기는 bstats_loader, 읽기는 bstats_api.
CREATE TABLE IF NOT EXISTS `run_expectancy` (
  `season` SMALLINT NOT NULL,
  `bases` TINYINT NOT NULL,
  `outs` TINYINT NOT NULL,
  `balls` TINYINT NOT NULL,
  `strikes` TINYINT NOT NULL,
  `re` DOUBLE NOT NULL,
  `n` INT NOT NULL,
  PRIMARY KEY (`season`, `bases`, `outs`, `balls`, `strikes`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `pitch_run_value` (
  `season` SMALLINT NOT NULL,
  `pitcher_ID` INT NOT NULL,
  `pitch_type` VARCHAR(20) NOT NULL,
  `stands` CHAR(1) NOT NULL,
  `n` INT NOT NULL,
  `rv` DOUBLE NOT NULL,
  PRIMARY KEY (`season`, `pitcher_ID`, `pitch_type`, `stands`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 공격 존(heart·shadow·chase·waste)별 투수 가치(2026-10-06). 위치 없는 공은 넣지 않습니다.
CREATE TABLE IF NOT EXISTS `pitch_run_value_zone` (
  `season` SMALLINT NOT NULL,
  `pitcher_ID` INT NOT NULL,
  `zone` VARCHAR(8) NOT NULL,
  `n` INT NOT NULL,
  `rv` DOUBLE NOT NULL,
  PRIMARY KEY (`season`, `pitcher_ID`, `zone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 리그 선구(Plate Discipline) 시즌 합계(2026-10-06). pitch_trend 와 같은 분류.
CREATE TABLE IF NOT EXISTS `plate_discipline_league` (
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
