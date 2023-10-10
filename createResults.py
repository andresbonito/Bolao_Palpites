import boto3
import pandas as pd
from os import environ

results_table = environ['ResultsTable']

DDB_CLIENT = boto3.client('dynamodb')


def lambda_handler(event, context):
    lista_dados_partidas = data_treat()

    i = 0
    for match in lista_dados_partidas:
        i += 1
        if i <= 9:
            match_id = f'match#0{i}'
        else:
            match_id = f'match#{i}'

        away_goals = str(match['away_goals'])
        away_team = match['away_team']
        home_goals = str(match['home_goals'])
        home_team = match['home_team']
        stage = str(match['stage'])

        winningTeam = match['winningTeam']
        
        if i <= 48:
            round = 'Group Stage'
        else:
            round = 'Knouckout Stage'

        new_item = {
            'matchId':{
                'S': match_id
            },
            '__typename':{
                'S': 'resultado'
            },
            'away_goals':{
                'N': away_goals
            },
            'away_team':{
                'S': away_team
            },
            'home_goals':{
                'N': home_goals
            },
            'home_team':{
                'S': home_team
            },
            'winningTeam':{
                'S': winningTeam
            },
            'round': {
                'S': round
            },
            'stage': {
                'S': stage
            }
        }

        if new_item['winningTeam']['S'] == 'Empate' and i > 48:
            penalties = match['penaltiesWinner']
            new_item.update({
                'Penalties': {
                    'S': penalties
                }
            })

        _ = DDB_CLIENT.put_item(
            TableName= results_table,
            Item= new_item
        )

    return 'Success'


def data_treat():
    df = pd.read_csv('Fifa_world_cup_matches.csv')
    df.insert(0, 'id_partida', [f'match#{i}' for i in range(1,65)])

    dados_partida = []

    for i in range(1,65):
        times_por_partida = df[df['id_partida'] == f'match#{i}']
        home_team =  times_por_partida['team1'].values[0]
        away_team =  times_por_partida['team2'].values[0]

        home_goals = times_por_partida['number of goals team1'].values[0]
        away_goals = times_por_partida['number of goals team2'].values[0]

        stage = times_por_partida['category'].values[0]

        if home_goals > away_goals:
            winningTeam = home_team
        elif home_goals < away_goals:
            winningTeam = away_team
        else:
            winningTeam = 'Empate'
            penalties = times_por_partida['penalties'].values[0]
        
        response = {
            'home_team': home_team,
            'away_team': away_team,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'winningTeam': winningTeam,
            'stage': stage,
            'penaltiesWinner': penalties if winningTeam == 'Empate' else '' 
        }
        dados_partida.append(response)
    
    return dados_partida

def error_log(msg) -> None:
    print(f'[ERRO] - [createResults]', msg)