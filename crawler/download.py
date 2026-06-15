import pandas as pd
import sys, time, requests, json, datetime, pathlib, warnings
import numpy as np
from dateutil.relativedelta import relativedelta
from tqdm import tqdm, trange
from bs4 import BeautifulSoup

from game_parse import game_status

# 경기 fetch 사이 대기(초). 대량 백필 시 Naver rate-limit 완화용.
# 일별 단일 경기 경로에서는 사실상 영향 없음.
FETCH_SLEEP_SEC = 0.4

regular_start = {
    '3333': '0101', # semi-playoff
    '4444': '0101', # wildcard
    '5555': '0101', # playoff
    '6666': '0101', # tie-breaker
    '7777': '0101', # playoff
    '8888': '0101', # event
    '9999': '0101', # all-star
    '2008': '0329',
    '2009': '0404',
    '2010': '0327',
    '2011': '0402',
    '2012': '0407',
    '2013': '0330',
    '2014': '0329',
    '2015': '0328',
    '2016': '0401',
    '2017': '0331',
    '2018': '0324',
    '2019': '0323',
    '2020': '0505',
    '2021': '0403',
    '2022': '0402',
    '2023': '0401',
    '2024': '0323',
    '2025': '0322',
    '2026': '0322',
}

playoff_start = {
    '3333': '1231', # semi-playoff
    '4444': '1231', # wildcard
    '5555': '1231', # playoff
    '6666': '1231', # tie-breaker
    '7777': '1231', # playoff
    '8888': '1231', # event
    '9999': '1231', # all-star
    '2008': '1008',
    '2009': '0920',
    '2010': '1005',
    '2011': '1008',
    '2012': '1008',
    '2013': '1008',
    '2014': '1019',
    '2015': '1010',
    '2016': '1021',
    '2017': '1010',
    '2018': '1015',
    '2019': '1003',
    '2020': '1101',
    '2021': '1101',
    '2022': '1013',
    '2023': '1019',
    '2024': '1002',
    '2025': '1005',
    '2026': '1231',
}


def get_game_ids(start_date, end_date, playoff=False):
    """
    KBO 경기 ID를 가져온다.

    Parameters
    -----------
    start_date, end_date : datetime.date
        ID를 가져올 경기 기간의 시작일과 종료일.
        start_date <= Game Date of Games <= end_date

    playoff : bool, default False
        True일 경우 플레이오프(포스트시즌) 경기 ID도 받는다.
    """

    calendar_api = 'https://api-gw.sports.naver.com/schedule/calendar?'\
                   'upperCategoryId=kbaseball&categoryIds=kbo&date='

    mon1 = start_date.replace(day=1)
    r = []
    while mon1 <= end_date:
        r.append(mon1)
        mon1 += relativedelta(months=1)

    game_ids = []

    for d in r:
        month = d.month
        year = d.year

        year_regular_start = regular_start[str(year)]
        year_playoff_start = playoff_start[str(year)]
        year_regular_start_date = datetime.date(year,
                                                int(year_regular_start[:2]),
                                                int(year_regular_start[2:]))
        year_playoff_start_date = datetime.date(year,
                                                int(year_playoff_start[:2]),
                                                int(year_playoff_start[2:]))
        year_last_date = datetime.date(year, 12, 31)

        cal_url = calendar_api + f"{d.strftime('%Y-%m-%d')}"
        try:
            req = requests.get(cal_url)
            if req.status_code != 200:
                print(f'status code exception occured, status_code = {req.status_code}')
                req.close()
                continue
            js = req.json()
            req.close()
        except AttributeError:
            print('AttributeError exception occured')
            exit(1)
        js = req.json()
        result = js.get('result')
        dates = result.get('dates')

        for date in dates:
            gameInfos = date.get('gameInfos')
            if gameInfos is None:
                continue
            else:
                for elem in gameInfos:
                    gid = elem.get('gameId')
                    gStatusCode = elem.get('statusCode')
                    if gStatusCode in ['RESULT', 'ENDED']:
                        gid_date = datetime.date(year, int(gid[4:6]), int(gid[6:8]))
                        if start_date <= gid_date <= end_date:
                            if playoff == False:
                                if year_regular_start_date <= gid_date < year_playoff_start_date:
                                    game_ids.append(gid)
                            else:
                                if year_regular_start_date <= gid_date < year_last_date:
                                    game_ids.append(gid)

    return game_ids


def get_game_data(game_id):
    """
    KBO 경기 PBP 데이터를 가져온다.

    Parameters
    -----------
    game_id : str
        가져올 게임 ID.
    """

    relay_url = 'http://m.sports.naver.com/ajax/baseball/'\
            'gamecenter/kbo/relayText.nhn'
    record_url = 'http://m.sports.naver.com/ajax/baseball/'\
                'gamecenter/kbo/record.nhn'
    params = {'gameId': game_id, 'half': '1'}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/59.0.3071.115 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Host': 'm.sports.naver.com',
        'Referer': 'http://m.sports.naver.com/baseball'\
                   '/gamecenter/kbo/index.nhn?&gameId='
                   + game_id
                   + '&tab=relay'
    }

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        #####################################
        # 1. pitch by pitch 데이터 가져오기 #
        #####################################
        relay_response = requests.get(relay_url,
                                      params=params,
                                      headers=headers)
        if relay_response.status_code > 200:
            relay_response.close()
            return [None, None, 'response error\n']

        relay_json = relay_response.json()
        js = None
        try:
            js = json.loads(relay_json)
            relay_response.close()
        except json.JSONDecodeError:
            relay_response.close()
            return [None, None, 'got no valid data\n']

        if js.get('gameId') is None:
            return [None, None, 'invalid game ID\n']

        last_inning = js['currentInning']

        if last_inning is None:
            return [None, None, 'no last inning\n']

        game_data_set = {}
        game_data_set['relayList'] = []
        for x in js['relayList']:
            game_data_set['relayList'].append(x)

        # 라인업에 대한 기초 정보가 담겨 있음
        game_data_set['homeTeamLineUp'] = js['homeTeamLineUp']
        game_data_set['awayTeamLineUp'] = js['awayTeamLineUp']

        game_data_set['stadium'] = js['schedule']['stadium']

        for inn in range(2, last_inning + 1):
            params = {
                'gameId': game_id,
                'half': str(inn)
            }

            relay_inn_response = requests.get(relay_url, params=params, headers=headers)
            if relay_inn_response.status_code > 200:
                relay_inn_response.close()
                return [None, None, 'response error\n']

            relay_json = relay_inn_response.json()
            try:
                js = json.loads(relay_json)
                relay_response.close()
            except json.JSONDecodeError:
                relay_inn_response.close()
                return [None, None, 'got no valid data\n']

            for x in js['relayList']:
                game_data_set['relayList'].append(x)

        #########################
        # 2. 가져온 정보 다듬기 #
        #########################
        relay_list = game_data_set['relayList']
        text_keys = ['seqno', 'text', 'type', 'stuff',
                     'ptsPitchId', 'speed', 'playerChange']
        pitch_keys = ['crossPlateX', 'topSz',
                      'pitchId', 'vy0', 'vz0', 'vx0',
                      'z0', 'ax', 'x0', 'ay', 'az',
                      'bottomSz']

        # pitch by pitch 텍스트 데이터 취합
        text_set = []
        stadium = game_data_set['stadium']
        for k in range(len(relay_list)):
            for j in range(len(relay_list[k].get('textOptionList'))):
                text_row = relay_list[k].get('textOptionList')[j]

                text_row_dict = {}
                text_row_dict['textOrder'] = relay_list[k].get('no')
                for key in text_keys:
                    if key == 'playerChange':
                        if text_row.get(key) is not None:
                            for x in ['outPlayer', 'inPlayer', 'shiftPlayer']:
                                if x in text_row.get(key).keys():
                                    text_row_dict[x] = text_row.get(key).get(x).get('playerId')
                    else:
                        text_row_dict[key] = None if key not in text_row.keys() else text_row.get(key)
                # text_row_dict['referee'] = referee
                text_row_dict['stadium'] = stadium
                text_set.append(text_row_dict)
        text_set_df = pd.DataFrame(text_set)
        text_set_df = text_set_df.rename(index=str, columns={'ptsPitchId': 'pitchId'})
        text_set_df.seqno = pd.to_numeric(text_set_df.seqno)

        # pitch by pitch 트래킹 데이터 취합
        pitch_data_set = []
        pitch_data_df = None
        for k in range(len(relay_list)):
            if relay_list[k].get('ptsOptionList') is not None:
                for j in range(len(relay_list[k].get('ptsOptionList'))):
                    pitch_data = relay_list[k].get('ptsOptionList')[j]

                    pitch_data_dict = {}
                    pitch_data_dict['textOrder'] = relay_list[k].get('no')
                    for key in pitch_keys:
                        pitch_data_dict[key] = None if key not in pitch_data.keys() else pitch_data.get(key)
                    pitch_data_set.append(pitch_data_dict)

        # 텍스트(중계) 데이터, 트래킹 데이터 취합
        if len(pitch_data_set) > 0:
            pitch_data_df = pd.DataFrame(pitch_data_set)
            relay_df = pd.merge(text_set_df, pitch_data_df, how='outer').sort_values(['textOrder', 'seqno'])
        else:
            relay_df = text_set_df.sort_values(['textOrder', 'seqno'])

        ##################################################
        # 3. 선발 라인업, 포지션, 레퍼리 데이터 가져오기 #
        ##################################################
        lineup_url = 'https://sports.news.naver.com/gameCenter'\
                     '/gameRecord.nhn?category=kbo&gameId='
        lineup_response = requests.get(lineup_url + game_id)

        if lineup_response.status_code > 200:
            lineup_response.close()
            return [None, None, 'response error\n']

        lineup_soup = BeautifulSoup(lineup_response.text, 'lxml')
        lineup_response.close()

        scripts = lineup_soup.find_all('script')
        if scripts[10].contents[0].find('잘못된') > 0:
            return [None, None, 'false script page\n']

        team_names = lineup_soup.find_all('span', attrs={'class': 't_name_txt'})
        away_team_name = team_names[0].contents[0].split(' ')[0]
        home_team_name = team_names[1].contents[0].split(' ')[0]

        for tag in scripts:
            if len(tag.contents) > 0:
                if tag.contents[0].find('DataClass = ') > 0:
                    contents = tag.contents[0]
                    start = contents.find('DataClass = ') + 36
                    end = contents.find('_homeTeam')
                    oldjs = contents[start:end].strip()
                    while oldjs[-1] != '}':
                        oldjs = oldjs[:-1]
                    while oldjs[0] != '{':
                        oldjs = oldjs[1:]
                    try:
                        cont = json.loads(oldjs)
                    except json.JSONDecodeError:
                        return [None, None, f'JSONDecodeError - gameID {game_id}\n']
                    break

        # 구심 정보 가져와서 취합
        referee = cont.get('etcRecords')[-1]['result'].split(' ')[0]
        relay_df = relay_df.assign(referee = referee)

        # 경기 끝나고 나오는 박스스코어, 홈/어웨이 라인업
        boxscore = cont.get('battersBoxscore')
        away_lineup = boxscore.get('away')
        home_lineup = boxscore.get('home')

        pos_dict = {'중': '중견수', '좌': '좌익수', '우': '우익수',
                    '유': '유격수', '포': '포수', '지': '지명타자',
                    '一': '1루수', '二': '2루수', '三': '3루수'}

        home_players = []
        away_players = []

        for i in range(len(home_lineup)):
            player = home_lineup[i]
            name = player.get('name')
            pos = player.get('pos')[0]
            pCode = player.get('playerCode')
            home_players.append({'name': name, 'pos': pos, 'pCode': pCode})

        for i in range(len(away_lineup)):
            player = away_lineup[i]
            name = player.get('name')
            pos = player.get('pos')[0]
            pCode = player.get('playerCode')
            away_players.append({'name': name, 'pos': pos, 'pCode': pCode})


        ##############################
        # 4. 기존 라인업 정보와 취합 #
        ##############################
        hit_columns = ['name', 'pCode', 'posName',
                       'hitType', 'seqno', 'batOrder']
        pit_columns = ['name', 'pCode', 'hitType', 'seqno']

        atl = game_data_set.get('awayTeamLineUp')
        abat = atl.get('batter')
        apit = atl.get('pitcher')
        abats = pd.DataFrame(abat, columns=hit_columns).sort_values(['batOrder', 'seqno'])
        apits = pd.DataFrame(apit, columns=pit_columns).sort_values('seqno')

        htl = game_data_set.get('homeTeamLineUp')
        hbat = htl.get('batter')
        hpit = htl.get('pitcher')
        hbats = pd.DataFrame(hbat, columns=hit_columns).sort_values(['batOrder', 'seqno'])
        hpits = pd.DataFrame(hpit, columns=pit_columns).sort_values('seqno')

        #####################################
        # 5. 라인업 정보 보강               #
        #####################################
        record_response = requests.get(record_url,
                                      params=params,
                                      headers=headers)
        if record_response.status_code > 200:
            record_response.close()
            return [None, None, 'response error\n']

        record_json = record_response.json()
        record_response.close()

        apr = pd.DataFrame(record_json['awayPitcher'])
        hpr = pd.DataFrame(record_json['homePitcher'])
        abr = pd.DataFrame(record_json['awayBatter'])
        hbr = pd.DataFrame(record_json['homeBatter'])
        apr = apr.rename(index=str, columns={'pcode':'pCode'})
        hpr = hpr.rename(index=str, columns={'pcode':'pCode'})
        abr = abr.rename(index=str, columns={'pcode':'pCode'})
        hbr = hbr.rename(index=str, columns={'pcode':'pCode'})

        apr.loc[:, 'seqno'] = 10
        apr.loc[:, 'hitType'] = None
        hpr.loc[:, 'seqno'] = 10
        hpr.loc[:, 'hitType'] = None

        abr.loc[:, 'seqno'] = 10
        abr.loc[:, 'hitType'] = None
        abr.loc[:, 'posName'] = None
        hbr.loc[:, 'seqno'] = 10
        hbr.loc[:, 'hitType'] = None
        hbr.loc[:, 'posName'] = None

        for p in apr.pCode.unique():
            if p in apits.pCode.unique():
                apr.loc[(apr.pCode == p), 'seqno'] = int(apits.loc[apits.pCode == p].seqno.values[0])
                apr.loc[(apr.pCode == p), 'hitType'] = apits.loc[apits.pCode == p].hitType.values[0]
            else:
                apr.loc[(apr.pCode == p), 'seqno'] = 10
        for p in hpr.pCode.unique():
            if p in hpits.pCode.unique():
                hpr.loc[(hpr.pCode == p), 'seqno'] = int(hpits.loc[hpits.pCode == p].seqno.values[0])
                hpr.loc[(hpr.pCode == p), 'hitType'] = hpits.loc[hpits.pCode == p].hitType.values[0]
            else:
                hpr.loc[(hpr.pCode == p), 'seqno'] = 10
        for p in abats.pCode.unique():
            if p in abats.pCode.unique():
                abr.loc[(abr.pCode == p), 'seqno'] = int(abats.loc[abats.pCode == p].seqno.values[0])
                abr.loc[(abr.pCode == p), 'posName'] = abats.loc[abats.pCode == p].posName.values[0]
                abr.loc[(abr.pCode == p), 'hitType'] = abats.loc[abats.pCode == p].hitType.values[0]
            else:
                abr.loc[(abr.pCode == p), 'seqno'] = 10
        for p in hbats.pCode.unique():
            if p in hbats.pCode.unique():
                hbr.loc[(hbr.pCode == p), 'seqno'] = int(hbats.loc[hbats.pCode == p].seqno.values[0])
                hbr.loc[(hbr.pCode == p), 'posName'] = hbats.loc[hbats.pCode == p].posName.values[0]
                hbr.loc[(hbr.pCode == p), 'hitType'] = hbats.loc[hbats.pCode == p].hitType.values[0]
            else:
                hbr.loc[(hbr.pCode == p), 'seqno'] = 10

        apr = apr.astype({'seqno': int})
        hpr = hpr.astype({'seqno': int})
        abr = abr.astype({'seqno': int})
        hbr = hbr.astype({'seqno': int})

        apits = apr[pit_columns]
        hpits = hpr[pit_columns]
        abats = abr[hit_columns]
        hbats = hbr[hit_columns]

        # 선발 출장한 경우, 선수의 포지션을 경기 시작할 때 포지션으로 수정
        # (pitch by pitch 데이터에서 가져온 정보는 경기 종료 시의 포지션임)
        for player in away_players:
            # '교'로 적혀있는 교체 선수는 넘어간다
            if player.get('pos') == '교':
                continue
            abats.loc[(abats.name == player.get('name')) &
                      (abats.pCode == player.get('pCode')), 'posName'] = pos_dict.get(player.get('pos'))
            if len(player.get('name')) > 3:
                pname = player.get('name')
                for i in range(len(abats)):
                    if abats.iloc[i].values[0].find(pname) > -1:
                        pCode = abats.iloc[i].pCode
                        abats.loc[(abats.pCode == pCode), 'posName'] = pos_dict.get(player.get('pos'))
                        break

        for player in home_players:
            # '교'로 적혀있는 교체 선수는 넘어간다
            if player.get('pos') == '교':
                continue
            hbats.loc[(hbats.name == player.get('name')) &
                      (hbats.pCode == player.get('pCode')), 'posName'] = pos_dict.get(player.get('pos'))
            if len(player.get('name')) > 3:
                pname = player.get('name')
                for i in range(len(hbats)):
                    if hbats.iloc[i].values[0].find(pname) > -1:
                        pCode = hbats.iloc[i].pCode
                        hbats.loc[(hbats.pCode == pCode), 'posName'] = pos_dict.get(player.get('pos'))
                        break

        abats = abats.assign(homeaway = 'a', team_name = away_team_name)
        hbats = hbats.assign(homeaway = 'h', team_name = home_team_name)
        apits = apits.assign(homeaway = 'a', team_name = away_team_name)
        hpits = hpits.assign(homeaway = 'h', team_name = home_team_name)

        batting_df = pd.concat([abats, hbats])
        pitching_df = pd.concat([apits, hpits])
        batting_df.pCode = pd.to_numeric(batting_df.pCode)
        pitching_df.pCode = pd.to_numeric(pitching_df.pCode)

        return pitching_df, batting_df, relay_df


def get_game_data_renewed(game_id):
    nav_api_header = 'https://api-gw.sports.naver.com/schedule/games/'
    get_boxscore_api = 'https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll'

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        #####################################
        # 0. 게임 메타 데이터 가져오기      #
        #####################################
        game_req = requests.get(nav_api_header + game_id)
        if game_req.status_code > 200:
            game_req.close()
            return [None, None, 'meta data request error\n']
        game_req_result = game_req.json()
        if game_req_result.get('code') > 200:
            game_req.close()
            return [None, None, 'meta data request error\n']
        game_req.close()

        game_meta_data = game_req_result.get('result').get('game')
        stadium = game_meta_data.get('stadium')
        homeTeamCode = game_meta_data.get('homeTeamCode')
        homeTeamName = game_meta_data.get('homeTeamName')
        awayTeamCode = game_meta_data.get('awayTeamCode')
        awayTeamName = game_meta_data.get('awayTeamName')

        # 취소 경기 가드: statusCode가 RESULT여도 statusInfo가 '경기취소'면
        # relay PBP(textRelayData)가 전무하다(과거 시즌 우천취소 등). 이 경우
        # 이후 relay 루프에서 NoneType.get AttributeError로 게임이 예외(failed)
        # 처리되므로, 데이터 없음(None)으로 우아하게 강등해 배치가 계속되게 한다.
        # 정상 경기(RESULT/ENDED, 진행 이닝 존재)는 이 분기를 타지 않아 무회귀.
        status_info = game_meta_data.get('statusInfo')
        if status_info is not None and ('취소' in status_info or '노게임' in status_info):
            return [None, None, f'game cancelled/no-game ({status_info})\n']

        box_score_req = requests.get(f'{nav_api_header}{game_id}/record')
        if box_score_req.status_code > 200:
            box_score_req.close()
            return [None, None, 'meta data(box score) request error\n']
        box_score_req_result = box_score_req.json()
        if box_score_req_result.get('code') > 200:
            box_score_req.close()
            return [None, None, 'meta data(box score) request error\n']
        box_score_req.close()

        box_score_data = box_score_req_result.get('result').get('recordData')
        if len(box_score_data.get('etcRecords')) > 0:
            referees = box_score_data.get('etcRecords')[-1].get('result').split(' ')
        else:
            print(game_id)
            referees = ['']

        currentInning = game_meta_data.get('currentInning')
        if (currentInning is not None) & (currentInning != ''):
            max_inning = int(game_meta_data.get('currentInning').split('회')[0])
        else:
            if game_meta_data.get('statusInfo') != '경기전':
                max_inning = int(game_meta_data.get('statusInfo').split('회')[0])
            else:
                max_inning = int(box_score_data.get('currentInning'))
        # 일부 과거 시즌(2008/2011)은 game_meta_data.currentInning이 '1회초'로 잘못
        # 들어와 max_inning이 1로 과소 산출됨 → 실제 진행 이닝 수를 담은 record
        # 엔드포인트(box_score_data.currentInning)를 fallback으로 두고 더 큰 값을 채택.
        # 2010+ 정상 시즌은 meta가 이미 실제 이닝과 같고 record 값이 이를 초과하지
        # 않으므로 결과가 동일(무회귀).
        record_current_inning = box_score_data.get('currentInning')
        if (record_current_inning is not None) & (record_current_inning != ''):
            try:
                max_inning = max(max_inning, int(record_current_inning))
            except (ValueError, TypeError):
                pass
        away_batting_order = box_score_data.get('battersBoxscore').get('away')
        home_batting_order = box_score_data.get('battersBoxscore').get('home')
        away_pitcher_boxscore = box_score_data.get('pitchersBoxscore').get('away')
        home_pitcher_boxscore = box_score_data.get('pitchersBoxscore').get('home')

        #####################################
        # 1. pitch by pitch 데이터 가져오기 #
        #####################################
        game_data_set = {}
        game_data_set['pitchTextList'] = []
        game_data_set['pitchTrackDataList'] = []

        # 일부 과거 시즌(2011 등)은 Naver awayLineup/homeLineup.pitcher와
        # pitchersBoxscore가 모두 비어 있어 투수 라인업을 만들 수 없다(IndexError).
        # 이때를 대비해 relay PBP의 currentGameState.pitcher(수비측 투수 pcode)를
        # 등장 순서대로, 그리고 투수 교체 텍스트(투수 A : 투수 B (으)로 교체)에서
        # 이름 체인을 수비측(a/h)별로 수집해 둔다. 정상 시즌에선 사용되지 않으므로
        # 무회귀(아래 4-pre 블록은 pitcher 라인업이 비어 있을 때만 동작).
        #   homeOrAway=='0'(초, 어웨이 공격) → 수비측 = home('h')
        #   homeOrAway=='1'(말, 홈 공격)     → 수비측 = away('a')
        recon_pcode_order = {'a': [], 'h': []}
        recon_sub_names = {'a': [], 'h': []}

        text_keys = ['seqno', 'text', 'type', 'stuff',
                     'ptsPitchId', 'speed', 'playerChange']
        pitch_keys = ['crossPlateX', 'topSz',
                      'pitchId', 'vy0', 'vz0', 'vx0',
                      'z0', 'ax', 'x0', 'ay', 'az',
                      'bottomSz']
        last_pbp_data = None  # 루프 후 라인업 추출용(마지막 유효 relay inning)
        for inning in range(1, max_inning+1):
            pbp_req = requests.get(f'{nav_api_header}{game_id}/relay?inning={inning}')
            if pbp_req.status_code > 200:
                pbp_req.close()
                print([None, None, 'pbp relay data request error\n'])
                assert False
            pbp_req_result = pbp_req.json()
            if pbp_req_result.get('code') > 200:
                pbp_req.close()
                print([None, None, 'pbp relay data request error\n'])
                assert False
            pbp_req.close()

            pbp_data = pbp_req_result.get('result').get('textRelayData')

            # 일부 (취소/중단) 경기는 textRelayData가 None이라 .get에서 예외.
            # 첫 이닝부터 None이면 데이터 없음으로 강등(None 반환), 이후 이닝에서
            # 비면 거기서 수집 종료(이미 받은 이닝까지로 진행). 정상 경기는 None이
            # 아니므로 무회귀. 루프 종료 후 라인업 추출에 쓰도록 마지막 유효 pbp_data 보존.
            if pbp_data is None:
                if inning == 1:
                    return [None, None, 'no relay data (textRelayData is None)\n']
                else:
                    break
            last_pbp_data = pbp_data

            for textSetList in pbp_data.get('textRelays')[::-1]:
                textRow = {}
                pitchTrackerRow = {}

                homeOrAway = textSetList.get('homeOrAway')
                textSet = textSetList.get('textOptions')
                textSetNo = textSetList.get('no')
                for pitchTextData in textSet:
                    textRow = {}
                    textRow['textOrder'] = textSetNo
                    for key in text_keys:
                        if key == 'playerChange':
                            if pitchTextData.get(key) is not None:
                                for x in ['outPlayer', 'inPlayer', 'shiftPlayer']:
                                    if x in pitchTextData.get(key).keys():
                                        textRow[x] = pitchTextData.get(key).get(x).get('playerId')
                        else:
                            if key not in pitchTextData.keys():
                                textRow[key] = None
                            else:
                                textRow[key] = pitchTextData.get(key)
                    textRow['referee'] = referees[0]
                    textRow['stadium'] = stadium
                    textRow['homeOrAway'] = homeOrAway
                    game_data_set['pitchTextList'].append(textRow)

                    # 투수 라인업 복구용 수집(정상 시즌엔 미사용). 수비측 기준.
                    def_side = 'h' if str(homeOrAway) == '0' else 'a'
                    cgs = pitchTextData.get('currentGameState')
                    if cgs is not None:
                        pc = cgs.get('pitcher')
                        if pc is not None and str(pc) != '':
                            pc = str(pc)
                            if pc not in recon_pcode_order[def_side]:
                                recon_pcode_order[def_side].append(pc)
                    p_txt = pitchTextData.get('text') or ''
                    if pitchTextData.get('type') == 2 and ('투수' in p_txt) and ('교체' in p_txt):
                        try:
                            before_nm = p_txt.split(':')[0].replace('투수', '').strip()
                            after_nm = p_txt.split(':')[1].split('(')[0].replace('투수', '').strip()
                            if not recon_sub_names[def_side]:
                                recon_sub_names[def_side].append(before_nm)
                            recon_sub_names[def_side].append(after_nm)
                        except (IndexError, AttributeError):
                            pass

                pitchTrackerSet = textSetList.get('ptsOptions')
                for pitchTrackData in pitchTrackerSet:
                    pitchTrackerRow = {}
                    pitchTrackerRow['textOrder'] = textSetNo

                    for key in pitch_keys:
                        if key not in pitchTrackData.keys():
                            pitchTrackerRow[key] = None
                        else:
                            pitchTrackerRow[key] = pitchTrackData.get(key)

                    game_data_set['pitchTrackDataList'].append(pitchTrackData)

        text_set_df = pd.DataFrame(game_data_set['pitchTextList'])
        text_set_df = text_set_df.rename(index=str, columns={'ptsPitchId': 'pitchId'})
        text_set_df.seqno = pd.to_numeric(text_set_df.seqno)

        # 텍스트(중계) 데이터, 트래킹 데이터 취합
        if len(game_data_set['pitchTrackDataList']) > 0:
            pitch_data_df = pd.DataFrame(game_data_set['pitchTrackDataList'])
            relay_df = pd.merge(text_set_df, pitch_data_df, how='outer').sort_values(['textOrder', 'seqno'])
        else:
            relay_df = text_set_df.sort_values(['textOrder', 'seqno'])

        ########################################
        # 2. 라인업 정리                       #
        ########################################
        # 라인업에 대한 기초 정보가 담겨 있음
        # 경기 끝나고나서 최종 정보 -> 포지션은 마지막 상황
        if last_pbp_data is None:
            return [None, None, 'no relay data (no innings parsed)\n']
        game_data_set['awayLineup'] = last_pbp_data.get('awayLineup')
        game_data_set['homeLineup'] = last_pbp_data.get('homeLineup')

        game_data_set['stadium'] = stadium

        pos_dict = {'중': '중견수', '좌': '좌익수', '우': '우익수',
            '유': '유격수', '포': '포수', '지': '지명타자',
            '一': '1루수', '二': '2루수', '三': '3루수'}

        home_players = []
        away_players = []

        for i in range(len(home_batting_order)):
            player = home_batting_order[i]
            name = player.get('name')
            pos = player.get('pos')[0]
            pcode = player.get('playerCode')
            ab = player.get('ab')
            run = player.get('run')
            hit = player.get('hit')
            rbi = player.get('rbi')
            hr = player.get('hr')
            bb = player.get('bb')
            k = player.get('kk')
            home_players.append({'name': name, 'pos': pos, 'pcode': pcode,
                                 'ab': ab, 'run': run, 'hit': hit,
                                 'rbi': rbi, 'hr': hr, 'bb': bb, 'k': k})

        for i in range(len(away_batting_order)):
            player = away_batting_order[i]
            name = player.get('name')
            pos = player.get('pos')[0]
            pcode = player.get('playerCode')
            ab = player.get('ab')
            run = player.get('run')
            hit = player.get('hit')
            rbi = player.get('rbi')
            hr = player.get('hr')
            bb = player.get('bb')
            k = player.get('kk')
            away_players.append({'name': name, 'pos': pos, 'pcode': pcode,
                                 'ab': ab, 'run': run, 'hit': hit,
                                 'rbi': rbi, 'hr': hr, 'bb': bb, 'k': k})

        ############################################
        # 3. 메타 데이터에 있는 라인업 정보와 취합 #
        ############################################
        # 메타 데이터에는 경기 시작했을 때 포지션 정보가 있음
        hit_columns = ['name', 'pcode', 'posName',
                       'hitType', 'seqno', 'batOrder']
        pit_columns = ['name', 'pcode', 'hitType', 'seqno']

        away_lineup_meta_data = game_data_set.get('awayLineup')
        away_batters = away_lineup_meta_data.get('batter')
        away_pitchers = away_lineup_meta_data.get('pitcher')
        away_lineup_df = pd.DataFrame(away_batters, columns=hit_columns).sort_values(['batOrder', 'seqno'])
        away_pitcher_df = pd.DataFrame(away_pitchers, columns=pit_columns).sort_values('seqno')

        home_lineup_meta_data = game_data_set.get('homeLineup')
        home_batters = home_lineup_meta_data.get('batter')
        home_pitchers = home_lineup_meta_data.get('pitcher')
        home_lineup_df = pd.DataFrame(home_batters, columns=hit_columns).sort_values(['batOrder', 'seqno'])
        home_pitcher_df = pd.DataFrame(home_pitchers, columns=pit_columns).sort_values('seqno')

        ##########################################################
        # 3-pre. 투수 라인업이 비어 있을 때 relay에서 복구       #
        ##########################################################
        # 2011 등 과거 시즌: Naver 라인업 메타와 pitchersBoxscore가 모두 비어
        # away/home_pitcher_df가 0행 → 이후 load()에서 IndexError로 게임 전체 실패.
        # relay에서 모은 수비측 투수 pcode 순서 + 교체 텍스트 이름 체인으로 복구한다.
        # 이름은 (1) 교체 텍스트 위치정렬, (2) pitchingResult(승/패/세/홀드 투수),
        # (3) pcode 문자열 순으로 fallback. 선발 투수가 첫 항목이 되어 load()의
        # 시작 투수로 쓰인다. 교체 투수 이름은 파싱 중 교체 텍스트로 덮어쓰므로,
        # df의 pcode '순서'가 정확하면 출력 품질이 유지된다.
        # 정상 시즌은 pitcher_df가 비어 있지 않아 이 블록을 건너뛴다(무회귀).
        if (len(away_pitcher_df) == 0) or (len(home_pitcher_df) == 0):
            pitching_result = box_score_data.get('pitchingResult') or []
            pcode2name = {}
            for pr in pitching_result:
                if pr.get('pCode') is not None:
                    pcode2name[str(pr.get('pCode'))] = pr.get('name')

            def _build_recon_pitcher_df(side):
                pcs = recon_pcode_order.get(side, [])
                nms = recon_sub_names.get(side, [])
                rows = []
                for i, pc in enumerate(pcs):
                    nm = nms[i] if i < len(nms) else None
                    if not nm:
                        nm = pcode2name.get(pc)
                    if not nm:
                        nm = pc
                    rows.append({'name': nm, 'pcode': pc,
                                 'hitType': None, 'seqno': i + 1})
                return pd.DataFrame(rows, columns=pit_columns)

            if len(away_pitcher_df) == 0:
                away_pitcher_df = _build_recon_pitcher_df('a').sort_values('seqno')
            if len(home_pitcher_df) == 0:
                home_pitcher_df = _build_recon_pitcher_df('h').sort_values('seqno')

        away_lineup_df = away_lineup_df.assign(pcode = pd.to_numeric(away_lineup_df.pcode))
        away_pitcher_df = away_pitcher_df.assign(pcode = pd.to_numeric(away_pitcher_df.pcode))
        home_lineup_df = home_lineup_df.assign(pcode = pd.to_numeric(home_lineup_df.pcode))
        home_pitcher_df = home_pitcher_df.assign(pcode = pd.to_numeric(home_pitcher_df.pcode))

        ap = pd.DataFrame(away_players)
        ap = ap.assign(pcode = pd.to_numeric(ap.pcode))

        hp = pd.DataFrame(home_players)
        hp = hp.assign(pcode = pd.to_numeric(hp.pcode))
        away_lineup_df = pd.merge(away_lineup_df, ap, on='pcode', how='outer')
        home_lineup_df = pd.merge(home_lineup_df, hp, on='pcode', how='outer')

        # 선발 출장한 경우, 선수의 포지션을 경기 시작할 때 포지션으로 수정
        # (pitch by pitch 데이터에서 가져온 정보는 경기 종료 시의 포지션임)
        away_lineup_df = away_lineup_df.assign(name = np.where(away_lineup_df.name_x.isnull(),
                                                               away_lineup_df.name_y,
                                                               away_lineup_df.name_x))
        home_lineup_df = home_lineup_df.assign(name = np.where(home_lineup_df.name_x.isnull(),
                                                               home_lineup_df.name_y,
                                                               home_lineup_df.name_x))
        lineup_df_columns = ['name', 'pcode', 'posName', 'hitType', 'seqno', 'batOrder',
                             'pos', 'ab', 'run', 'hit', 'rbi', 'hr', 'bb', 'k']
        away_lineup_df = away_lineup_df[lineup_df_columns]
        home_lineup_df = home_lineup_df[lineup_df_columns]

        away_lineup_df = away_lineup_df\
                        .assign(posName = np.where(away_lineup_df.pos != '교',
                                                   away_lineup_df.pos\
                                                       .apply(lambda x: pos_dict.get(x)),
                                                   away_lineup_df.posName))
        home_lineup_df = home_lineup_df\
                        .assign(posName = np.where(home_lineup_df.pos != '교',
                                                   home_lineup_df.pos\
                                                       .apply(lambda x: pos_dict.get(x)),
                                                   home_lineup_df.posName))

        away_lineup_df = away_lineup_df.assign(homeaway = 'a', team_name = awayTeamName)
        home_lineup_df = home_lineup_df.assign(homeaway = 'h', team_name = homeTeamName)
        away_pitcher_df = away_pitcher_df.assign(homeaway = 'a', team_name = awayTeamName)
        home_pitcher_df = home_pitcher_df.assign(homeaway = 'h', team_name = homeTeamName)

        batting_df = pd.concat([away_lineup_df, home_lineup_df])
        pitching_df = pd.concat([away_pitcher_df, home_pitcher_df])
        batting_df.pcode = pd.to_numeric(batting_df.pcode)
        pitching_df.pcode = pd.to_numeric(pitching_df.pcode)

        ######################
        # 4. 박스스코어 추가 #
        ######################
        if int(game_id[:4]) < 3000:
            if len(away_pitcher_boxscore) > 0:
                pitcher_boxscore = {}
                for x in (away_pitcher_boxscore + home_pitcher_boxscore):
                    pitcher_boxscore[int(x.get('pcode'))] = x.copy()
                for k in pitcher_boxscore.keys():
                    ip = pitcher_boxscore[k]['inn']
                    if ip.find('⅔') > 0:
                        ip = int(ip[0])+0.2
                    elif ip.find('⅓') > 0:
                        ip = int(ip[0])+0.1
                    elif ip.find('.') > 0:
                        ip = ip
                    else:
                        ip = int(ip)
                    pitcher_boxscore[k]['inn'] = ip
                    pitcher_boxscore[k]['pcode'] = k
                    pitcher_boxscore[k]['hbp'] = max(int(pitcher_boxscore[k]['bbhp']) - int(pitcher_boxscore[k]['bb']), 0)
                pitcher_boxscore_columns = ['pcode', 'wls', 'w', 'l', 's', 'inn', 'pa', 'bf', 'ab', 'hit', 'hr', 'bbhp', 'bb', 'hbp', 'kk', 'r', 'er', 'era']

                # 등판 결과 승 패 세 이닝 타자 투구수 타수 피안타 홈런 4사구 삼진 실점 자책 평자 game_date game_id
                pitcher_boxscore_df = pd.DataFrame(pitcher_boxscore).T
                pitcher_boxscore_df = pitcher_boxscore_df[pitcher_boxscore_columns]
                pitcher_boxscore_df = pitcher_boxscore_df.rename(index=int,
                                                                 columns={'wls': '결과',
                                                                          'w': '승',
                                                                          'l': '패',
                                                                          's': '세',
                                                                          'inn': '이닝',
                                                                          'bf': '투구수',
                                                                          'pa': '타자',
                                                                          'ab': '타수',
                                                                          'hit': '피안타',
                                                                          'hr': '홈런',
                                                                          'bbhp': '4사구',
                                                                          'bb': '볼넷',
                                                                          'hbp': '사구',
                                                                          'kk': '삼진',
                                                                          'r': '실점',
                                                                          'er': '자책',
                                                                          'era': '평균자책점'})
                pitching_df = pd.merge(pitching_df, pitcher_boxscore_df, on='pcode', how='outer')
                pitching_df = pitching_df.rename(index=int,
                                                 columns={'pcode_x': 'pcode'})
                pitching_df = pitching_df.assign(등판 = np.nan,
                                                 game_date = datetime.date(int(game_id[:4]),
                                                                           int(game_id[4:6]),
                                                                           int(game_id[6:8])),
                                                 game_id = game_id[:-4],
                                                 level='1군',
                                                 level_eng='KBO')
                pitching_df_columns = ['name', 'pcode', 'hitType', 'seqno', 'homeaway', 'team_name',
                                       '등판', '결과', '승', '패', '세', '이닝', '타자', '투구수',
                                       '타수', '피안타', '홈런', '4사구', '삼진', '실점', '자책',
                                       '평균자책점', '볼넷', '사구', 'game_date', 'game_id', 'level', 'level_eng']
                pitching_df = pitching_df[pitching_df_columns]
            else:
                params = {
                    'leId': 1,
                    'srId': 0,
                    'seasonId': int(game_id[:4]),
                    'gameId': game_id[:-4]
                }
                req = requests.post(get_boxscore_api, data=params)
                # KBO 공식 GetBoxScoreScroll fallback은 현재 전역적으로 죽어 있어
                # JSON 대신 HTML(text/html)을 돌려준다. req.json()이 JSONDecodeError를
                # 던지면 게임 전체가 실패하므로, 파싱 실패 시 빈 dict로 강등(graceful degrade)한다.
                # (Naver pitchersBoxscore가 비어 있는 경기: 2011 등)
                try:
                    req_js = req.json()
                except (ValueError, requests.exceptions.JSONDecodeError):
                    req_js = {}
                req.close()

                if req_js.get('msg') == '성공':
                    text = [req_js.get('arrPitcher')[0].get('table'), req_js.get('arrPitcher')[1].get('table')]
                    text = [x.replace('\\r', '').replace('\\n', '') for x in text]
                    text = [x.replace('\n', '').replace('\r', '').strip() for x in text]
                    text = [x.replace('\\', '') for x in text]
                    text = [x.replace('\"{', '{').replace('\ "}', '}') for x in text]
                    text = [x.replace('  ', '').replace('}\"', '}') for x in text]

                    away_pitchers_table = json.loads(text[0])
                    home_pitchers_table = json.loads(text[1])
                    away_pitchers_header = away_pitchers_table.get('headers')[0]
                    home_pitchers_header = home_pitchers_table.get('headers')[0]
                    headers = [x.get('Text') for x in home_pitchers_header.get('row')]

                    away_pitchers = []
                    home_pitchers = []

                    for pitcher in home_pitchers_table.get('rows'):
                        values = [x.get('Text') for x in pitcher.get('row')]
                        values = [x.replace('&nbsp;', '') for x in values]
                        name = values[0]
                        data = {k: v for k, v in zip(headers, values)}
                        home_pitchers.append(data)
                    for pitcher in away_pitchers_table.get('rows'):
                        values = [x.get('Text') for x in pitcher.get('row')]
                        values = [x.replace('&nbsp;', '') for x in values]
                        name = values[0]
                        data = {k: v for k, v in zip(headers, values)}
                        away_pitchers.append(data)
                    away_pitching_df = pd.concat([pitching_df[pitching_df.homeaway == 'a'],
                                                  pd.DataFrame(away_pitchers)], axis=1)
                    home_pitching_df = pd.concat([pitching_df[pitching_df.homeaway == 'h'],
                                                  pd.DataFrame(home_pitchers)], axis=1)
                    columns = home_pitching_df.columns.tolist()
                    columns.remove('선수명')
                    pitching_df = pd.concat([away_pitching_df, home_pitching_df])[columns]
                    # 없는 컬럼 볼넷, 사구 추가
                    pitching_df = pitching_df.assign(볼넷 = np.nan,
                                                     사구 = np.nan,
                                                     game_date = datetime.date(int(game_id[:4]),
                                                                               int(game_id[4:6]),
                                                                               int(game_id[6:8])),
                                                     game_id = game_id[:-4],
                                                     level='1군',
                                                     level_eng='KBO')
                    pitching_df = pitching_df.rename(index=int, columns={'평자': '평균자책점'})
                else:
                    # boxscore fallback이 비어 있거나(=죽은 endpoint) 실패한 경우.
                    # Naver PBP/relay/batting은 정상이므로 게임을 살리고, 보조적인
                    # 투수 박스스코어 파생 컬럼만 비워(NaN) 둔다.
                    # 첫 번째 분기(boxscore 존재, line 802~806)와 동일한 컬럼 셋을 유지해
                    # 다운스트림 parse/save가 변경 없이 동작하도록 한다.
                    # ('4사구'는 식별자가 아니라 kwargs로 못 넘기므로 dict unpacking 사용)
                    boxscore_derived_cols = ['등판', '결과', '승', '패', '세', '이닝',
                                             '타자', '투구수', '타수', '피안타', '홈런',
                                             '4사구', '삼진', '실점', '자책', '평균자책점',
                                             '볼넷', '사구']
                    pitching_df = pitching_df.assign(**{c: np.nan for c in boxscore_derived_cols})
                    pitching_df = pitching_df.assign(game_date = datetime.date(int(game_id[:4]),
                                                                               int(game_id[4:6]),
                                                                               int(game_id[6:8])),
                                                     game_id = game_id[:-4],
                                                     level='1군',
                                                     level_eng='KBO')
                    pitching_df_columns = ['name', 'pcode', 'hitType', 'seqno', 'homeaway', 'team_name',
                                           '등판', '결과', '승', '패', '세', '이닝', '타자', '투구수',
                                           '타수', '피안타', '홈런', '4사구', '삼진', '실점', '자책',
                                           '평균자책점', '볼넷', '사구', 'game_date', 'game_id', 'level', 'level_eng']
                    pitching_df = pitching_df[pitching_df_columns]
    batting_df = batting_df.rename(index=int,
                                   columns = {'ab': '타수',
                                              'run': '득점',
                                              'hit': '안타',
                                              'rbi': '타점',
                                              'hr': '홈런',
                                              'bb': '볼넷',
                                              'k': '삼진'})
    batting_df = batting_df.assign(level='1군', level_eng='KBO')
    batting_df = batting_df.sort_values(['batOrder', 'seqno'], ascending=True)
    
    rdf_cols = relay_df.columns.tolist()
    idx = rdf_cols.index('homeOrAway')
    rdf_cols.pop(idx)
    rdf_cols.append('homeOrAway')
    
    return pitching_df, batting_df, relay_df[rdf_cols]


def download_pbp_files(start_date, end_date, playoff=False,
                       save_path=None, debug_mode=False,
                       save_source=False):
    """
    KBO 피치 바이 피치(PBP) 파일을 다운로드.

    Parameters
    -----------
    start_date, end_date : datetime.date
        PBP 파일을 받을 경기 기간의 시작일과 종료일.
        start_date <= Game Date of Downloaded Files <= end_date

    playoff : bool, default False
        True일 경우 플레이오프(포스트시즌) 경기 파일도 받는다.

    save_path : pathlib.Path, default None
        PBP 파일을 저장할 경로.
        값이 없을 경우(None) 현재 경로에 저장.

    debug_mode : bool, default False
        True일 경우 sys.stdout을 통해 디버그 메시지와 수행 시간이 출력됨.

    save_source : bool, default False
        True일 경우 parsing 이전의 소스 데이터를 csv 형식으로 저장.
    """
    start_time = time.time()
    game_ids = get_game_ids(start_date, end_date, playoff)
    end_time = time.time()
    get_game_id_time = end_time - start_time

    enc = 'cp949' if sys.platform == 'win32' else 'utf-8'

    now = datetime.datetime.now()

    logfile = open('./log.txt', 'a', encoding=enc)
    logfile.write('\n\n')
    logfile.write('====================================\n')
    logfile.write(f"Current Time : {now.isoformat()}\n")
    logfile.write('====================================\n')

    skipped = 0
    broken = 0
    done = 0
    failed = 0  # fetch/parse 중 예외로 건너뛴 경기 수 (대량 백필 중 단일 경기 실패가 배치 전체를 중단시키지 않도록)
    start_time = time.time()
    get_data_time = 0
    gid = None

    years = []
    for gid in game_ids:
        if len(gid) > 13:
            years.append(gid[-4:])
        else:
            years.append(gid[:4])
    years = list(set(years))

    try:
        for y in years:
            y_path = save_path / y

            if not y_path.is_dir():
                try:
                    y_path.mkdir()
                except FileExistsError:
                    logfile.write(f'ERROR : path {y_path} exists, but not a directory')
                    logfile.write(f'\tclean path and try again')
                    print(f'ERROR : path {y_path} exists, but not a directory')
                    print(f'\tclean path and try again')
                    exit(1)

        for gid in tqdm(game_ids):
            now = datetime.datetime.now().date()
            gid_year = int(gid[:4])
            if gid_year > 3000:
                if gid_year > 8000:
                    continue
                try:
                    gid_year = int(gid[-4:])
                except ValueError:
                    # 13자 형식 등 시즌 suffix 누락 gameID skip (postseason edge case)
                    continue
            gid_for_save = f'{gid_year}{gid[4:]}'
            gid_to_date = datetime.date(gid_year,
                                        int(gid[4:6]),
                                        int(gid[6:8]))
            if gid_to_date > now:
                continue

            if (save_path / str(gid_year) / f'{gid_for_save}.csv').exists():
                skipped += 1
                continue

            ptime = time.time()
            source_path = save_path / str(gid_year) / 'source'
            # 단일 경기 fetch/parse 실패가 배치 전체를 죽이지 않도록 try로 감싸 로그 후 continue.
            # (이미 다운로드된 파일 SKIP은 위에서 처리되어 이 블록을 타지 않음 → resumable 유지)
            try:
                if (source_path / f'{gid_for_save}_pitching.csv').exists() &\
                    (source_path / f'{gid_for_save}_batting.csv').exists() &\
                    (source_path / f'{gid_for_save}_relay.csv').exists():
                    game_data_dfs = []
                    try:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_pitching.csv'), encoding='cp949'))
                    except:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_pitching.csv'), encoding='utf-8'))
                    try:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_batting.csv'), encoding='cp949'))
                    except:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_batting.csv'), encoding='utf-8'))
                    try:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_relay.csv'), encoding='cp949'))
                    except:
                        game_data_dfs.append(pd.read_csv(str(source_path / f'{gid_for_save}_relay.csv'), encoding='utf-8'))
                else:
                    game_data_dfs = get_game_data_renewed(gid)
                    # Naver rate-limit 완화용 폴라이트 throttle (네트워크 fetch 직후에만)
                    time.sleep(FETCH_SLEEP_SEC)

                # 데이터 없음(None): 과거/취소 경기 등. exit(1) 대신 skip+log+카운트 후 다음 경기로.
                if game_data_dfs[0] is None:
                    logfile.write(f'SKIP(no data) gameID {gid} : {game_data_dfs[-1]}')
                    if debug_mode == True:
                        print(f'SKIP(no data) gameID {gid} : {game_data_dfs[-1]}')
                    broken += 1
                    continue

                if save_source == True:
                    if not source_path.is_dir():
                        try:
                            source_path.mkdir()
                        except FileExistsError:
                            source_path = save_path / str(gid_year)
                            logfile.write(f'NOTE: {gid_year}/source exists but not a directory.')
                            logfile.write(f'source files will be saved in {gid_year} instead.')

                    enc = 'cp949'
                    if not (source_path / f'{gid_for_save}_pitching.csv').exists():
                        game_data_dfs[0].to_csv(str(source_path / f'{gid_for_save}_pitching.csv'),
                                                index=False, encoding=enc, errors='replace')
                    if not (source_path / f'{gid_for_save}_batting.csv').exists():
                        game_data_dfs[1].to_csv(str(source_path / f'{gid_for_save}_batting.csv'),
                                                index=False, encoding=enc, errors='replace')
                    if not (source_path / f'{gid_for_save}_relay.csv').exists():
                        game_data_dfs[2].to_csv(str(source_path / f'{gid_for_save}_relay.csv'),
                                                index=False, encoding=enc, errors='replace')

                get_data_time += time.time() - ptime
                if game_data_dfs is not None:
                    gs = game_status()
                    gs.load(gid, game_data_dfs[0], game_data_dfs[1], game_data_dfs[2], log_file=logfile)
                    parse = gs.parse_game(debug_mode)
                    gs.save_game(save_path / str(gid_year))
                    if parse == True:
                        done += 1
                    else:
                        broken += 1
                else:
                    broken += 1
                    continue
            except Exception as e:
                # 단일 경기 실패 로그 후 다음 경기로 진행(배치 중단 방지)
                failed += 1
                logfile.write(f'FAILED gameID {gid} : {repr(e)}\n')
                if debug_mode == True:
                    print(f'FAILED gameID {gid} : {repr(e)}')
                continue

        end_time = time.time()
        parse_time = end_time - start_time - get_data_time
        logfile.write('====================================\n')
        logfile.write(f'Start date : {start_date.strftime("%Y%m%d")}\n')
        logfile.write(f'End date : {end_date.strftime("%Y%m%d")}\n')
        logfile.write(f'Successfully downloaded games : {done}\n')
        logfile.write(f'Skipped games(already exists) : {skipped}\n')
        logfile.write(f'Broken games(bad data) : {broken}\n')
        logfile.write(f'Failed games(exception, skipped) : {failed}\n')
        logfile.write('====================================\n')
        if debug_mode == True:
            logfile.write(f'Elapsed {get_game_id_time:.2f} sec in get_game_ids\n')
            logfile.write(f'Elapsed {(get_data_time):.2f} sec in get_game_data\n')
            logfile.write(f'Elapsed {(parse_time):.2f} sec in parse_game\n')
        logfile.write(f'Total {(parse_time+get_game_id_time+get_data_time):.2f} sec elapsed with {len(game_ids)} games\n')

        # 콘솔 요약(대량 백필 모니터링용): 성공/스킵/불량/예외 카운트
        print(f'[download_pbp_files] done={done} skipped={skipped} '
              f'broken={broken} failed={failed} total={len(game_ids)}')

        if logfile.closed == False:
            logfile.close()
    except:
        logfile.write(f'=== gameID : {gid}\n')
        if logfile.closed == False:
            logfile.close()
        assert False

