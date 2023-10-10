import boto3
import random
import string
from datetime import datetime
from os import environ


DDB_CLIENT = boto3.client('dynamodb')
GUESSES_TABLE = environ['GuessesTable']
RESULTS_TABLE = environ['ResultsTable']
TEAMS_TABLE = environ['TeamsTable']


def lambda_handler(event, context):
    debug_log(f'Evento: {event}')
    guessId = create_guess_id(10)
    input_data = event.get('arguments', {}).get('input', {})

    # Verifica se o guessId vem vazio
    if guessId is None:
        error_log('guessId is required')
        return {'error': {
            'message': 'guessId is required',
            'type': 'InvalidArguments'
        }}
    
    # Condição para que, em caso de empate nos jogos de mata mata, tenha o vencedor nos penalties
    if input_data['matchId'] > 48 and input_data['awayGoals'] == input_data['homeGoals']\
          and 'penalties' not in input_data:
        error_log('penalties is required')
        return {'error': {
            'message': 'penalties is required',
            'type': 'InvalidArguments'
        }}
    elif input_data['matchId'] > 48 and input_data['awayGoals'] != input_data['homeGoals']\
          and 'penalties' in input_data:
        error_log('penalties is not required')
        return {'error': {
            'message': 'penalties is not required',
            'type': 'InvalidArguments'
        }}
    
    if 'penalties' in input_data:
        if input_data['penalties'] != input_data['homeTeam']\
         and input_data['penalties'] != input_data['awayTeam']:
            error_log('penalties winner not in guess')
            return {'error': {
                'message': 'penalties winner not in guess',
                'type': 'InvalidArguments'
            }}


    # Prepara os dados para inserir na tabela
    new_item = prepare_data(guessId, input_data)
    debug_log(f'New Item: {new_item}')

    if not new_item:
        error_log('teamIds not found, check teams input')
        return {'error': {
            'message': 'teamIds not found, check teams input',
            'type': 'InvalidArguments'
        }}

    try:
        ddb_commands = [
            {'Put': {
                'TableName': GUESSES_TABLE,
                'ConditionExpression': "attribute_not_exists(guessId)",
                "Item": new_item
            }}
        ]

        response = DDB_CLIENT.transact_write_items(TransactItems=ddb_commands)

        # Se a resposta for bem sucedida, retorna o item
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            item = DDB_CLIENT.get_item(
                TableName=GUESSES_TABLE,
                Key={
                    'guessId': new_item['guessId'],
                }
            )

            # Tratativa para que venha apenas o item na resposta
            _, response = translate_result([item['Item'], ], retrieve=True)
            return response
        else:
            error_log(f'lambda_handler (1): {response["ResponseMetadata"]}')
            return {'error': {
                'message': f"Error: {str(response['ResponseMetadata']['HTTPStatusCode'])}",
                'type': 'DynamoDbError'
            }}

    except Exception as e:
        error_log(f'{str(e)}')
        return {'error': {
            'message': f"Error: {str(e)}",
            'type': 'DynamoDbError'
        }}

def prepare_data(guessId, input_data):
    # Verifica o tipo da partida, teamIds e grupos
    if input_data['matchId'] < 49:
        round = 'Group Stage'
        home_team_id, grupo = get_teamId(input_data['homeTeam'].upper())
        away_team_id, _ = get_teamId(input_data['awayTeam'].upper())
    else:
        round = 'Knouckout Stage'
        home_team_id, _ = get_teamId(input_data['homeTeam'].upper())
        away_team_id, _ = get_teamId(input_data['awayTeam'].upper())

    if not home_team_id and not away_team_id:
        return None

    # Verifica quem é o vencedor da partida
    if input_data['homeGoals'] > input_data['awayGoals']:
        winningTeam = input_data['homeTeam']
        winningTeamId = home_team_id
    elif input_data['homeGoals'] < input_data['awayGoals']:
        winningTeam = input_data['awayTeam']
        winningTeamId = away_team_id
    elif input_data['homeGoals'] == input_data['awayGoals']:
        winningTeam = 'EMPATE'
        winningTeamId = 'EMPATE'

    # Item a ser inserido na tabela 
    response = {
        "guessId": {"S": guessId},
        "__typename": {"S": 'palpite'},
        "CreatedAt": {'S': f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}'},
        "winningTeam": {"S": winningTeam.upper()},
        "winningTeamId": {"S": winningTeamId},
        "matchId": {"S": f'match#0{input_data["matchId"]}' if input_data['matchId'] < 10 else f'match#{input_data["matchId"]}'},
        'homeTeam': {"S": input_data['homeTeam'].upper()},
        'homeTeamId': {"S": home_team_id},
        'awayTeam': {"S": input_data['awayTeam'].upper()},
        'awayTeamId': {"S": away_team_id},
        'awayGoals': {"N": f'{input_data["awayGoals"]}'},
        'homeGoals': {"N": f'{input_data["homeGoals"]}'},
        'round': {"S": round},
        'group': {"S": grupo if input_data['matchId'] < 49 else ''},
        'userId': {"S": input_data['userId']}
    }

    # Se houver penaltis, cria a coluna de penaltis na resposta anterior
    if 'penalties' in input_data:
        response.update({
            'penalties': {"S": input_data['penalties'].upper()}
        })

    return response

# Pega o item para enviar os teamIds e grupos
def get_teamId(team):
    try:
        response = DDB_CLIENT.query(
            TableName=TEAMS_TABLE,
            IndexName='team',
            KeyConditionExpression='#team = :team',
            ExpressionAttributeNames={
                '#team': 'team'
            },
            ExpressionAttributeValues={
                ':team': {
                    'S': team
                }
            }
        )

        if 'Items' in response and isinstance(response['Items'], list) and len(response['Items']) > 0:
            team_id = response['Items'][0]['teamId']['S']
            grupo = response['Items'][0]['group']['S']

            return team_id, grupo
    
    except Exception as e:
        error_log(f'get_teamId: {str(e)}')
        return None, None


# Limpa os dados para o retorno do item no AppSync
def translate_result(raw_data, retrieve=False):
    response = [] if not retrieve else {}

    if raw_data is None:
        return 0, response
    elif not retrieve:
        if len(raw_data) == 0:
            return 0, []

    for row in raw_data:
        if retrieve:
            response = deep_clean_field(row)
            break

        response.append(deep_clean_field(row))

    return len(raw_data) if raw_data else 0, response


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


# Função que cria o guessId
def create_guess_id(length, verify=True):
    while verify:
        letters = string.ascii_uppercase + string.digits
        id = ""
        
        for _ in range(length):    
            id += letters[random.randint(0, len(letters) - 1)]

        verify = verifiy_guess(id.upper())

    return id.upper()
    

# Função que verifica se existe o guessId
def verifiy_guess(guessId):
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
        }
    )

    success = True if response['Count'] > 0 else False

    return success


def error_log(msg) -> None:
    print('[ERRO] - [MakeGuess]', msg)


def debug_log(msg) -> None:
    print('[DEBUG] - [MakeGuess]', msg)