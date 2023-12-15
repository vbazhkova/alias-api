import ydb
import json 
import time
import datetime
import random

pool = None
session = None

def handler(event, context):
    global pool
    global session
    iam_token = context.token['access_token']
    
    is_connected = check_connection(pool)
    
    if not is_connected:
        pool = connect_DB(iam_token)
    
    response_body = {
        'message' : 'Empty result'
    }
    
    headers = {
        'Content-Type' : 'application/json',
        'Access-Control-Allow-Origin' : '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

    method = event['httpMethod']
    current_url = event['url']
    current_params = event['params']

    if method == 'GET' :
        if '/team?' in current_url:
            response_body = handle_GET_team(pool, current_params)
        if '/cards' in current_url:
            response_body = handle_GET_cards(pool, current_params)
        if '/topic' in current_url:
            response_body = handle_GET_topics(pool)
        if '/game' in current_url:
            response_body = handle_GET_game(pool, current_params)
    elif method == 'DELETE':
        if '/team?' in current_url:
            response_body = handle_DELETE_team(pool, current_params)
    elif method == 'PATCH':
        if '/team?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_PATCH_team(pool, current_params, body)
        if '/game/start?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_PATCH_game_start(pool, current_params, body)
        if '/game/round?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_PATCH_game_round(pool, current_params, body)
        if '/game/answer?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_PATCH_answer(pool, current_params, body)
    elif method == 'POST':
        if '/team?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_POST_team(pool, current_params, body)
        if 'game/configure' in current_url:
            body = json.loads(event['body'])
            response_body = handle_POST_game_configure(pool, body)
        if '/game/next/round?' in current_url:
            body = json.loads(event['body'])
            response_body = handle_POST_next_team_round(pool, current_params, body)
    else:
        return
           
    # pool.release(session)
            
    return {
        'statusCode': 200,
        'headers' : headers,
        'body': response_body
    }
    # return {
    #     'statusCode': 200,
    #     'body': event,
    # }

## MARK: - HTTP Handlers
def handle_GET_team(pool, current_params):
    team_id = current_params['team_id']
    response_body = {
        'team' : get_team_by_id(pool, team_id)[0].rows[0]
    }
    return response_body

def handle_DELETE_team(pool, current_params):
    team_id = current_params['team_id']
    delete_team_by_id(pool, team_id)
    response_body = {
        'message' : 'Team deleted'
    }
    return response_body

def handle_PATCH_team(pool, current_params, body):
    team_id = current_params['team_id']
    team_name = body['team_name']
    update_team_name(pool, team_id, team_name)
    response_body = {
        'message' : 'Name successfully changed'
    }
    return response_body

def handle_POST_team(pool, current_params, body):
    user_id = current_params['user_id']
    team_name = body['team_name']
    team_id = last_team_id(pool)[0].rows[0]['team_id'] + 1
    save_new_team(pool, user_id, team_name, team_id)
    response_body = {
        'message' : 'Team successfully added!'
    }
    return response_body

def handle_GET_cards(pool, current_params):
    topic_id = current_params['topic_id']
    cards = get_cards(pool, topic_id)[0].rows
    response_body = {
        'cards' : cards
    }
    return response_body

def handle_GET_topics(pool):
    topics = get_topics(pool)[0].rows
    response_body = {
        'topics' : topics
    }
    return response_body

def handle_GET_game(pool, current_params):
    game_id = int(current_params['game_id'])
    game = get_game(pool, game_id)[0].rows[0]
    topic_id =  game['topic_id']
    points_to_win = game['points_to_win']
    round_time = game['round_time']
    teams_ids = game['team_ids'].decode()
    teams_ids_list = teams_ids.split(', ')
    new_game_id = last_game_id(pool)[0].rows[0]['game_id'] + 1
    first_team = get_team_by_id(pool, int(teams_ids_list[0]))[0].rows
    
    save_new_game(pool, new_game_id, topic_id, points_to_win, round_time, teams_ids)
    
    for team_id in teams_ids_list:
        update_last_team_game(pool, team_id, new_game_id)
    
    response_body = {
        'game_id' : new_game_id,
        'first_team' : {
            'team_name' : first_team[0]['team_name'].decode(),
            'team_id' : first_team[0]['team_id']
        }
    }
    return response_body

def handle_POST_game_configure(pool, body):
    topic_id = body['topic_id']
    points_to_win = body['points_to_win']
    round_time = body['round_time']
    teams_cnt = int(body['teams_count'])
    teams = get_teams(pool)[0].rows
    teams = teams[0:teams_cnt]
    teams_ids_list = [team['team_id'] for team in teams]
    teams_ids = ', '.join(map(str, teams_ids_list))
    game_id = last_game_id(pool)[0].rows[0]['game_id'] + 1

    save_new_game(pool, game_id, topic_id, points_to_win, round_time, teams_ids)
    
    for team_id in teams_ids_list:
        update_last_team_game(pool, team_id, game_id)
    
    response_body = {
        'game_id' : game_id,
        'first_team' : {
            'team_name' : teams[0]['team_name'].decode(),
            'team_id' : teams[0]['team_id']
        }
    }
    return response_body

def handle_PATCH_game_start(pool, current_params, body):
    game_id = current_params['game_id']
    team_id = body['team_id']
    time_start = time.time()
    time_stamp = datetime.datetime.utcfromtimestamp(time_start).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    start_new_game(pool, game_id, time_stamp)
    game = get_game(pool, game_id)[0].rows[0]
    round_time = game['round_time']
    cards = get_cards(pool, game['topic_id'])[0].rows
    first_card = random.choice(cards)
    round_id = last_round_id(pool)[0].rows[0]['round_id'] + 1
    create_round(pool, round_id, game_id, team_id, time_stamp)
    
    response_body = {
        'game_id' : game_id,
        'round_time' : round_time,
        'team_id' : team_id,
        'question' : {
            'round_id' : round_id,
            'question' : {
                'card_id' : first_card['card_id'],
                'question' : first_card['question'].decode(),
                'topic_id' : first_card['topic_id']
            }
        }
    }
    return response_body

def handle_PATCH_game_round(pool, current_params, body):
    game_id = current_params['game_id']
    team_id = body['team_id']
    round_id = body['round_id']
    time_finish = time.time()
    time_stamp_f = datetime.datetime.utcfromtimestamp(time_finish).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    finish_round(pool, round_id, time_stamp_f)
    
    next_team_time_start = time.time()
    time_stamp_s = datetime.datetime.utcfromtimestamp(next_team_time_start).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    current_game = get_game(pool, game_id)[0].rows
    teams_ids = current_game[0]['team_ids'].decode().split(', ')
    next_team_id = 1
    for index, team in enumerate(teams_ids):
        if str(team_id) == str(team):
            if index + 1 < len(teams_ids):
                next_team_id = teams_ids[index + 1]
            else:
                next_team_id = teams_ids[0]
    next_team = get_team_by_id(pool, int(next_team_id))[0].rows[0]
    
    next_round_id = last_round_id(pool)[0].rows[0]['round_id'] + 1
    create_round(pool, next_round_id, game_id, next_team_id, time_stamp_s)
    
    response_body = {
        'game_id' : game_id,
        'next_round': next_round_id,
        'next_team' : {
            'team_name' : next_team['team_name'].decode(),
            'team_id' : next_team['team_id']
        }
    }
    return response_body

def handle_PATCH_answer(pool, current_params, body):
    game_id = current_params['game_id']
    is_answered = body['is_answered']
    card_id = body['card_id']
    round_id = int(body['round_id'])
    round = get_round(pool, round_id)[0].rows[0]
    team_id = round['team_id']
    game = get_game(pool, game_id)[0].rows[0]
    topic_id = game['topic_id']
    cards = get_cards(pool, topic_id)[0].rows
    used_card_ids = game['used_cards_ids']
    used_card_ids_list = []
    if used_card_ids != None:
        used_card_ids_list = used_card_ids.decode().split(',')
    
    not_used_cards = []
    for card in cards:
        if str(card['card_id']) not in used_card_ids_list:
            not_used_cards.append(card)

    random.shuffle(not_used_cards)
    next_card = random.choice(not_used_cards)
    
    used_card_ids_string = ''
    if used_card_ids_list == []:
        used_card_ids_string = str(card_id)
    else:
        used_card_ids_string = used_card_ids.decode() + f',{card_id}'
    update_game_cards_ids(pool, game_id, used_card_ids_string)
    
    answers_stats = round['count_answers']
    skips_stats = round['count_skips']
    total_stats = 0
    if answers_stats == None:
        answers_stats = 0
    if skips_stats == None:
        skips_stats = 0
    if is_answered:
        answers_stats += 1
        total_stats += 1
    else:
        skips_stats += 1
    
    rounds = get_rounds_by_game_id(pool, game_id)[0].rows
    for round in rounds:
        if int(round['team_id']) == int(team_id) and round['count_answers'] != None:
            total_stats += int(round['count_answers'])

            
    update_round_stats(pool, round_id, answers_stats, skips_stats, total_stats)
    
    if total_stats == int(game['points_to_win']):
        time_finish = time.time()
        time_stamp_f = datetime.datetime.utcfromtimestamp(time_finish).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        finish_round(pool, round_id, time_stamp_f)
        
        team = get_team_by_id(pool, team_id)[0].rows[0]
        rounds = get_rounds_by_game_id(pool, game_id)[0].rows
        
        points_stats = []
        times_stats = []
        rounds_by_teams = [[],[],[],[],[],[],[]]
        for round in rounds:
            id = int(round['team_id']) - 1
            rounds_by_teams[id].append(round)
        
        for tr in rounds_by_teams:
            if tr != []:
                points_skipped = 0
                points_answered = 0
                points_total = 0
                time_start = None
                time_finish = None
                minutes = 0
                seconds = 0
                team_id = 0
                for index, round in enumerate(tr):
                    team_id = int(round['team_id'])
                    if index == len(tr) - 1:
                        if int(round['count_total']) != None:
                            points_answered = int(round['count_total'])
                        time_finish = round['time_finish']
                    if index == 0:
                        time_start = round['time_start']
                    if int(round['count_skips']) != None:
                        points_skipped += int(round['count_skips'])
                if time_finish != None:
                    time_difference = time_finish - time_start
                    minutes = int(time_difference / 60000000)
                    seconds = int((time_difference % 60000000) / 1000000)
                    points_total = points_skipped + points_answered
                    team_name = get_team_by_id(pool, team_id)[0].rows[0]['team_name'].decode()
                    points_stats.append(
                        {
                            'team_id' : team_id,
                            'team_name' : team_name,
                            'points' : f'{points_answered}/{points_total}'
                        }
                    )
                    times_stats.append(
                        {
                            'team_id' : team_id,
                            'team_name' : team_name,
                            'times' : f'{minutes} мин {seconds} сек'
                        }
                    )

        response_body = {
            'game_id' : game_id,
            'winner_name' : team['team_name'].decode(),
            'stats' : {
                'points' : points_stats,
                'times' : times_stats
            }
        }
        return response_body
    
    response_body = {
        'next_card' : {
            'card_id' : next_card['card_id'],
            'question' : next_card['question'].decode(),
            'topic_id' : next_card['topic_id']
        }
    }
    return response_body

def handle_POST_next_team_round(pool, current_params, body):
    game_id = current_params['game_id']
    round_id = body['round_id']
    team_id = body['team_id']
    game = get_game(pool, game_id)[0].rows[0]
    round_time = game['round_time']
    cards = get_cards(pool, game['topic_id'])[0].rows
    used_card_ids = game['used_cards_ids']
    used_card_ids_list = []
    if used_card_ids != None:
        used_card_ids_list = used_card_ids.decode().split(',')
    
    not_used_cards = []
    for card in cards:
        if str(card['card_id']) not in used_card_ids_list:
            not_used_cards.append(card)

    random.shuffle(not_used_cards)
    next_card = random.choice(not_used_cards)
    
    response_body = {
        'game_id' : game_id,
        'round_time' : round_time,
        'team_id' : team_id,
        'question' : {
            'round_id' : round_id,
            'question' : {
                'card_id' : next_card['card_id'],
                'question' : next_card['question'].decode(),
                'topic_id' : next_card['topic_id']
            }
        }
    }
    return response_body

## MARK: - YDB handlers
## MARK: - TEAMS
def get_teams(pool):
    text = f"""
        SELECT * FROM team;
    """
    return ydb_request(pool, text)

def get_team_by_id(pool, team_id):
    text = f"""
        SELECT * FROM team WHERE team_id == {team_id};
    """
    return ydb_request(pool, text) 

def save_new_team(pool, user_id, team_name, team_id):
    text = f"""
        UPSERT INTO team ( user_id, team_name, team_id )
        VALUES ( {user_id}, "{team_name}", {team_id} );
    """
    return ydb_request(pool, text)

def delete_team_by_id(pool, team_id):
    text = f"""
        DELETE FROM team WHERE team_id = {team_id};
    """
    return ydb_request(pool, text)

def update_team_name(pool, team_id, team_name):
    text = f"""
        UPDATE team SET team_name = "{team_name}" WHERE team_id = {team_id};
    """
    return ydb_request(pool, text)

def last_team_id(pool):
    text = f"""
        SELECT team_id FROM team WHERE team_id IN (SELECT MAX(team_id) FROM team);
    """
    return ydb_request(pool, text)

def update_last_team_game(pool, team_id, game_id):
    text = f"""
        UPDATE team SET last_game_id = {game_id} WHERE team_id = {team_id};
    """
    return ydb_request(pool, text)

## MARK: - CARDS
def get_cards(pool, topic_id):
    text = f"""
        SELECT * FROM cards WHERE topic_id == {topic_id};
    """
    return ydb_request(pool, text)

## MARK: - Rounds
def create_round(pool, round_id, game_id, team_id, time_start):
    text = f"""
        UPSERT INTO rounds ( round_id, game_id, team_id, time_start )
        VALUES ( {round_id}, {game_id}, {team_id}, TIMESTAMP('{time_start}'));
    """
    return ydb_request(pool, text)

def update_game_cards_ids(pool, game_id, used_cards_ids):
    text = f"""
        UPDATE games SET used_cards_ids = "{used_cards_ids}" WHERE game_id = {game_id};
    """
    return ydb_request(pool, text)

def finish_round(pool, round_id, time_finish):
    text = f"""
        UPDATE rounds SET time_finish = TIMESTAMP('{time_finish}') WHERE round_id = {round_id};
    """
    return ydb_request(pool, text)

def last_round_id(pool):
    text = f"""
        SELECT round_id FROM rounds WHERE round_id IN (SELECT MAX(round_id) FROM rounds);
    """
    return ydb_request(pool, text)

def get_round(pool, round_id):
    text = f"""
        SELECT * FROM rounds WHERE round_id == {round_id};
    """
    return ydb_request(pool, text)

def update_round_stats(pool, round_id, answers, skips, total):
    text = f"""
        UPDATE rounds 
        SET count_answers = {answers}, count_skips = {skips}, count_total = {total} 
        WHERE round_id = {round_id};
    """
    return ydb_request(pool, text)

def get_rounds_by_game_id(pool, game_id):
    text = f"""
        SELECT * FROM rounds WHERE game_id == {game_id};
    """
    return ydb_request(pool, text)

## MARK: - TOPICS
def get_topics(pool):
    text = f"""
        SELECT * FROM topic;
    """
    return ydb_request(pool, text)

## MARK: - GAME
def last_game_id(pool):
    text = f"""
        SELECT game_id FROM games WHERE game_id IN (SELECT MAX(game_id) FROM games);
    """
    return ydb_request(pool, text)

def save_new_game(pool, game_id, topic_id, points_to_win, round_time, teams_ids):
    text = f"""
        UPSERT INTO games ( game_id, topic_id, points_to_win, round_time, team_ids )
        VALUES ( {game_id}, {topic_id}, {points_to_win}, {round_time}, "{teams_ids}");
    """
    return ydb_request(pool, text)

def start_new_game(pool, game_id, time_start):
    text = f"""
        UPDATE games SET time_start = TIMESTAMP('{time_start}') WHERE game_id = {game_id};
    """
    return ydb_request(pool, text)

def get_game(pool, game_id):
    text = f"""
        SELECT * FROM games WHERE game_id == {game_id} ;
    """
    return ydb_request(pool, text)

## MARK: - YDB BASE
def connect_DB(iam_token):
    driver_config = ydb.DriverConfig(
    'grpcs://ydb.serverless.yandexcloud.net:2135', '/ru-central1/b1gd9chcn9avh3nko03c/etnjne2r4pmefmr39et1',
    credentials=ydb.AccessTokenCredentials(iam_token))
    
    driver = ydb.Driver(driver_config)
    driver.wait(fail_fast=True, timeout=10)
    pool = ydb.SessionPool(driver, workers_threads_count=5, size=10)
    
    return pool

def ydb_request(pool, text):
    retries = 3
    session = pool.acquire()
    for i in range(retries):
        try:
            return pool.retry_operation_sync(lambda s: s.transaction().execute(
                text,
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(10).with_operation_timeout(10)
            ))
        except Exception as e:
            if i < retries - 1:
                time.sleep(2) 
            else:
                raise 
        finally:
            pool.release(session)
            
def check_connection(pool):
    if pool != None:
        try:
            print('have connection')
            return True
        except:
            print('no connection')
            return False
        # finally:
        #     if session:
        #         session.release()