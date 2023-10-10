import boto3
import string
import random
from os import environ


DDB_CLIENT = boto3.client('dynamodb')
# GUESSES_TABLE = environ['GuessesTable']
GROUPGUESSES_TABLE = environ['GroupStatsGuessesTable']
# TEAMS_TABLE = environ['TeamsTable']


def lambda_handler(event, context):
    debug_log(f'Evento: {event}')

    # # Armazena os registros recebidos
    # records = event.get('Records', [])

    # # Loop nos registros de garantia
    # for row in records:
    #     # Verifica se é um registro de DynamoDb
    #     if 'dynamodb' not in row:
    #         continue

    #     new_image = row['dynamodb']['NewImage']
    #     new_item = prepare_data(new_image)

    #     debug_log(new_item)

    #     if new_item:
    #         try:
    #             ddb_commands = [
    #                 {
    #                 'Put': {
    #                     'TableName': GROUPGUESSES_TABLE,
    #                     'ConditionExpression': "attribute_not_exists(statsGuessId)",
    #                     "Item": new_item
    #                 }},
    #             ]

    #             response = DDB_CLIENT.transact_write_items(TransactItems=ddb_commands)

    #             return response
            
    #         except Exception as e:
    #             error_log(f'{str(e)}')
    #             return {'error': {
    #                 'message': f"Error: {str(e)}",
    #                 'type': 'DynamoDbError'
    #             }}
        
    #     return error_log('Estatisticas não criadas.')


def prepare_data(new_image):
    params = deep_clean_field(new_image)



# def generate_random_id():
#     characters = string.ascii_uppercase + string.digits
#     random_id = ''.join(random.choice(characters) for _ in range(6))
#     return random_id


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
    print('[ERRO] - [GroupGuessesTrigger]', msg)


def debug_log(msg) -> None:
    print('[DEBUG] - [GroupGuessesTrigger]', msg)
