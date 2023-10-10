import boto3
import pandas as pd
from os import environ


DDB_CLIENT = boto3.client('dynamodb')

TEAMS_TABLE = environ['TeamsTable']


def lambda_handler(event, context):
    lista_dados_times = data_treat()

    for match in lista_dados_times:
        
        teamId = match['teamId']
        group = match['group']
        team = match['team']


        new_item = {
            'teamId':{
                'S': teamId
            },
            '__typename':{
                'S': 'time'
            },
            'group':{
                'S': group
            },
            'team':{
                'S': team
            }
        }

        _ = DDB_CLIENT.put_item(
            TableName= TEAMS_TABLE,
            Item= new_item
        )

    return 'Success'


def data_treat():
    df = pd.read_csv('teamsTable.csv')
    df.insert(0, 'id_partida', [f'match#{i}' for i in range(1,33)])

    dados_times = []

    for i in range(32):
        teamIds = df['teamId'].tolist()
        groups = df['group'].tolist()
        teams = df['team'].tolist()
        
        teamId = teamIds[i]
        teamId = teamId.replace('#', '')
        group = groups[i]
        team = teams[i]

        response = {
            'teamId': teamId,
            'group': group,
            'team': team,
        }

        dados_times.append(response)
    
    return dados_times


def error_log(msg) -> None:
    print('[ERRO] - [createTeams]', msg)


def debug_log(msg) -> None:
    print('[DEBUG] - [createTeams]', msg)