import boto3
from os import environ
from datetime import datetime

DDB_CLIENT = boto3.client('dynamodb')
GUESSES_TABLE = environ['GuessesTable']
GROUPSTATSGUESSES_TABLE = environ['GroupStatsGuessesTable']

def lambda_handler(event, context):
    debug_log(f'Evento: {event}')
    
    # Armazena os registros recebidos
    records = event.get('Records', [])

    # Loop nos registros de garantia
    for row in records:
        # Verifica se é um registro de DynamoDb
        if 'dynamodb' not in row:
            continue

        new_image = row['dynamodb']['NewImage']
        
        new_group = create_groups(new_image)
        debug_log(f'New Item: {new_group}')

        new_teams = create_teams_stats(new_image)
        debug_log(f'New Teams: {new_teams}')

        group_guess_id = new_group['groupGuessId']['S']

        if new_group and new_teams:
            response = check_group_item(group_guess_id)
            try:
                # Se o item já existir, será um update da tabela
                if response:
                    update_expression = ['#ModifiedAt = :ModifiedAt',]
                    expression_names = {'#ModifiedAt': 'ModifiedAt',}
                    expression_values = {
                        ':ModifiedAt': {'S': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')},
                    }

                    input_data = deep_clean_field(new_group)

                    fields_to_remove = []

                    for key, value in input_data.items():
                        print(f'Key: {key} - Value: {value}')
                        if value is None or value == '':
                            fields_to_remove.append(key)
                            continue

                        update_expression.append(f'#{key} = :{key}')
                        expression_names.update({f'#{key}': key})
                        expression_values.update({f':{key}': {'S': f'{value}'}})
                        
                    update_expression = f"SET {', '.join(update_expression)}"

                    if fields_to_remove:
                        fields_temp = ', '.join(fields_to_remove)
                        update_expression += f' REMOVE {fields_temp}'

                    ddb_commands = [
                        {'Update': {
                        'TableName': GROUPSTATSGUESSES_TABLE,
                        'ConditionExpression': "attribute_exists(groupGuessId)",
                        'Key': {
                            'groupGuessId': {'S': group_guess_id}
                        },
                        'UpdateExpression': update_expression,
                        'ExpressionAttributeNames': expression_names,
                        'ExpressionAttributeValues': expression_values,
                    }},
                    ]
                

                # ---
                elif not response:
                    ddb_commands = [
                        {
                        'Put': {
                            'TableName': GROUPSTATSGUESSES_TABLE,
                            'ConditionExpression': "attribute_not_exists(groupGuessId)",
                            "Item": new_group
                        }},
                    ]

                for team in new_teams:
                    ddb_commands.append(
                        {
                            'Put': {
                                'TableName': GROUPSTATSGUESSES_TABLE,
                                'ConditionExpression': "attribute_not_exists(groupGuessId)",
                                'Item': team['response']
                            }
                        }
                    )

                response = DDB_CLIENT.transact_write_items(TransactItems=ddb_commands)

                return response
            
            except Exception as e:
                error_log(f'{str(e)}')
                return {'error': {
                    'message': f"Error: {str(e)}",
                    'type': 'DynamoDbError'
                }}
        
        return error_log('Estatisticas não criadas.')


# Tratamento para inserir na tabela de Stats
def create_groups(new_image):
    params = deep_clean_field(new_image)

    guessId = params['guessId']
    userId = params['userId'] if 'userId' in params else get_user_id_in_case(guessId)
    grupo = params['group'].replace(" ", "").upper()
    match_id = int(params['matchId'].split('#')[1])

    response = {
        'groupGuessId': {'S': f'{grupo}#{userId}'},
        '__typename': {'S': f'{grupo.replace(" ", "").upper()}#{guessId}'},
        'group': {'S': grupo if grupo and match_id < 49 else 'Knockout Stage'}
    }

    return response


def create_teams_stats(new_image):
    params = deep_clean_field(new_image)

    guessId = params['guessId']
    user_id = params['userId'] if 'userId' in params else get_user_id_in_case(guessId)
    home_team_id = params['homeTeamId']
    away_team_id = params['awayTeamId']

    winning_team_id = params['winningTeamId']

    if winning_team_id == home_team_id:
        team_id_win = home_team_id
        team_id_loss = away_team_id
        goals_made_win = params['homeGoals']
        goals_made_loss = params['awayGoals']
        goals_suffered_win = params['awayGoals']
        goals_suffered_loss = params['homeGoals']
        team_win = params['homeTeam']
        team_loss = params['awayTeam']
        goals_difference_win = int(params['homeGoals']) - int(params['awayGoals'])
        goals_difference_loss = int(params['awayGoals']) - int(params['homeGoals'])
    elif winning_team_id == away_team_id:
        team_id_win = away_team_id
        team_id_loss = home_team_id
        goals_made_win = params['awayGoals']
        goals_made_loss = params['homeGoals']
        goals_suffered_win = params['homeGoals']
        goals_suffered_loss = params['awayGoals']
        team_win = params['awayTeam']
        team_loss = params['homeTeam']
        goals_difference_win = int(params['awayGoals']) - int(params['homeGoals'])
        goals_difference_loss = int(params['homeGoals']) - int(params['awayGoals'])
    elif winning_team_id == 'EMPATE':
        team_id_win = away_team_id
        team_id_loss = home_team_id
        goals_made_win = params['awayGoals']
        goals_made_loss = params['homeGoals']
        goals_suffered_win = params['homeGoals']
        goals_suffered_loss = params['awayGoals']
        team_win = params['awayTeam']
        team_loss = params['homeTeam']
        goals_difference_win = int(params['awayGoals']) - int(params['homeGoals'])
        goals_difference_loss = int(params['homeGoals']) - int(params['awayGoals'])


    responses = [
        {
        'response': {
            'groupGuessId': {'S': f'{team_id_win}#{user_id}'},
            '__typename': {'S': f'{team_id_win}#{guessId}'},
            'Team': {'S': team_win},
            'GoalsMade': {'N': f'{goals_made_win}'},
            'GoalsSuffered': {'N': f'{goals_suffered_win}'},
            'GoalsDifference': {'N': f'{goals_difference_win}'}
        }},
        {'response': {
            'groupGuessId': {'S': f'{team_id_loss}#{user_id}'},
            '__typename': {'S': f'{team_id_loss}#{guessId}'},
            'Team': {'S': team_loss},
            'GoalsMade': {'N': f'{goals_made_loss}'},
            'GoalsSuffered': {'N': f'{goals_suffered_loss}'},
            'GoalsDifference': {'N': f'{goals_difference_loss}'}
        }}
    ]

    return responses


# Busca pelo userId em caso de não estar nos parametros do input da API
def get_user_id_in_case(guessId):
    userId = ''

    try:
        response = DDB_CLIENT.query(
            TableName=GUESSES_TABLE,
            KeyConditionExpression='#guessId = :guessId',
            ExpressionAttributeNames={
                '#guessId': 'guessId'
            },
            ExpressionAttributeValues={
                ':guessId': {
                    'S': guessId
                }
            },
            ProjectionExpression='guessId,userId,matchId'
        )

    except Exception as e:
        error_log(f'get_user_id_in_case: {str(e)}')
        return userId

    if 'Items' in response and isinstance(response['Items'], list) and len(response['Items']) > 0:
        userId = response['Items'][0]['userId']['S']

        return userId
    

def check_group_item(group_guess_id):
    try:
        response = DDB_CLIENT.query(
            TableName=GROUPSTATSGUESSES_TABLE,
            KeyConditionExpression='#groupGuessId = :groupGuessId',
            ExpressionAttributeNames={
                '#groupGuessId': 'groupGuessId'
            },
            ExpressionAttributeValues={
                ':groupGuessId': {
                    'S': group_guess_id
                }
            }
        )

        debug_log(f'Response Groups: {response}')

    except Exception as e:
        error_log(f'check_group_item: {str(e)}')

    count = response['Count']

    if count > 0:
        return True
    else:
        return False


# Limpa os dados para o retorno do item no AppSync
def deep_clean_field(raw_dict: dict):
    response = {}

    for key, value in raw_dict.items():
        if key in ['S', 'N', 'B', 'L', 'NS', 'SS', 'BS', 'BOOL', ]:
            return value
        if key in ['NULL', ]:
            return None
        elif key in ['M', ]:
            return deep_clean_field(value)
        else:
            response.update({key: deep_clean_field(value)})

    return response


def error_log(msg) -> None:
    print('[ERRO] - [GroupStatsGuesses]', msg)


def debug_log(msg) -> None:
    print('[DEBUG] - [GroupStatsGuesses]', msg)