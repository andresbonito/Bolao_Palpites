import boto3
from os import environ

scores_tables = environ['ScoresTables']

DDB_CLIENT = boto3.client('dynamodb')

def lambda_handler(event, context):
    try:
        create_scores()
    except Exception as e:
        error_log(str(e))

def create_scores():
    response = DDB_CLIENT.put_item(
        TableName= scores_tables,
        Item={
            'scoreId':{
                'S': 'score_id'
            },
            '__typename':{
                'S': 'Pontuação'
            },
            'PlacarExato':{
                'S': '10'
            },
            'VencedorEGols':{
                'S': '5'
            },
            'Vencedor':{
                'S': '3'
            },
            'GolsDeUmTime':{
                'S': '1'
            },
            'bonusOitavas':{
                'S': '5'
            },
            'bonusQuartas':{
                'S': '10'
            },
            'bonusSemi':{
                'S': '20'
            },
            'bonusTerceiro':{
                'S': '25'
            },
            'bonusFinal':{
                'S': '30'
            },
            'bonusCampeao':{
                'S': '50'
            },

        }
    )

    return response

def error_log(msg) -> None:
    print(f'[ERRO] - [Scores]', msg)