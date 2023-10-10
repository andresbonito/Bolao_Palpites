import boto3
from os import environ
from datetime import datetime

DDB_CLIENT = boto3.client('dynamodb')
GUESSES_TABLE = environ['GuessesTable']
RESULTS_TABLE = environ['ResultsTable']

def lambda_handler(event, context):
    debug_log(f'Evento: {event}')
    guessId = event.get('arguments', {}).get('guessId', None)
    input_data = event.get('arguments', {}).get('input', {})

    if guessId is None or guessId is {}:
        error_log('guessId is required')
        return {'error': {
            'message': 'guessId is required',
            'type': 'InvalidArguments'
        }}
    
    old_item = DDB_CLIENT.get_item(
        TableName=GUESSES_TABLE,
        Key={
            'guessId': {'S': guessId},
        }
    )

    if 'Item' not in old_item:
        error_log('Guess not found')
        return {
            'error': {
                'message': 'Guess not found',
                'type': 'RecordNotFound'
            }
        }
    
    item = old_item['Item']
    debug_log(deep_clean_field(item))

    home_goals = int(item['homeGoals']['N'])
    away_goals = int(item['awayGoals']['N'])
    matchId = item['matchId']['S']
    matchId = int(matchId.split('#')[-1])
    
    try:    
        # winningTeam vem aqui
        if 'awayGoals' in input_data and 'homeGoals' not in input_data:
            if home_goals > input_data['awayGoals']:
                winningTeam = item['homeTeam']['S']
            elif home_goals < input_data['awayGoals']:
                winningTeam = item['awayTeam']['S']
            else:
                winningTeam = 'EMPATE'
        elif 'homeGoals' in input_data and 'awayGoals' not in input_data:
            if away_goals > input_data['homeGoals']:
                winningTeam = item['awayTeam']['S']
            elif away_goals < input_data['homeGoals']:
                winningTeam = item['homeTeam']['S']
            else:
                winningTeam = 'EMPATE'
        elif 'homeGoals' in input_data and 'awayGoals' in input_data:
            if input_data['awayGoals'] > input_data['homeGoals']:
                winningTeam = item['awayTeam']['S']
            elif input_data['awayGoals'] < input_data['homeGoals']:
                winningTeam = item['homeTeam']['S']
            else:
                winningTeam = 'EMPATE'

        update_expression = ['#ModifiedAt = :ModifiedAt', '#winningTeam = :winningTeam']
        expression_names = {'#ModifiedAt': 'ModifiedAt', '#winningTeam': 'winningTeam'}
        expression_values = {
            ':ModifiedAt': {'S': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')},
            ':winningTeam': {'S': winningTeam}
        }

        fields_to_remove = []

        for key, value in input_data.items():
            if value is None or value == '':
                fields_to_remove.append(key)
                continue
         
            update_expression.append(f'#{key} = :{key}')
            expression_names.update({f'#{key}': key})

            if key in ['awayTeam', 'homeTeam']:
                expression_values.update({f':{key}': {'S': value.upper()}})
            elif key in ['awayGoals', 'homeGoals']:
                expression_values.update({f':{key}': {'N': f'{value}'}})
            elif key in ['penalties']:
                if winningTeam == 'EMPATE' and matchId > 48:
                    expression_values.update({f':{key}': {'S': value.upper()}})
                elif winningTeam != 'EMPATE':
                    expression_values.update({f':{key}': {'S': value}})
                

        update_expression = f"SET {', '.join(update_expression)}"

        if fields_to_remove:
            fields_temp = ', '.join(fields_to_remove)
            update_expression += f' REMOVE {fields_temp}'

        ddb_commands = [
            {'Update': {
                'TableName': GUESSES_TABLE,
                'ConditionExpression': "attribute_exists(guessId)",
                'Key': {
                    'guessId': {'S': guessId}
                },
                'UpdateExpression': update_expression,
                'ExpressionAttributeNames': expression_names,
                'ExpressionAttributeValues': expression_values,
            }},
        ]

        response = DDB_CLIENT.transact_write_items(TransactItems=ddb_commands)

        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            item = DDB_CLIENT.get_item(
                TableName=GUESSES_TABLE,
                Key={
                    'guessId': {'S': guessId},
                }
            )

            _, response = translate_result([item['Item'], ], retrieve=True)
            return response
    
    except Exception as e:
        error_log(f'{str(e)}')
        return {'error': {
            'message': f"Error: {str(e)}",
            'type': 'DynamoDbError'
        }}


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
    print('[ERRO] - [UpdateGuess]', msg)


def debug_log(msg) -> None:
    print('[DEBUG] - [UpdateGuess]', msg)