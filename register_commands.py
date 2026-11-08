"""Register global Discord slash commands (can take a while to propagate)."""
import json
import os
from urllib.request import Request,urlopen

app_id=os.environ['DISCORD_APPLICATION_ID']
token=os.environ['DISCORD_BOT_TOKEN']
commands=[
    {'name':'無料ゲーム','description':'現在無料で配布中のEpic Gamesタイトルを表示'},
    {'name':'次回配布','description':'次回のEpic Games無料配布予告を表示'},
    {'name':'ヘルプ','description':'BOTの使い方を表示'},
]
url=f'https://discord.com/api/v10/applications/{app_id}/commands'
request=Request(url,method='PUT',data=json.dumps(commands,ensure_ascii=False).encode('utf-8'),headers={
    'Authorization':'Bot '+token,'Content-Type':'application/json','User-Agent':'EpicFreeGameNotifier/2.0'})
with urlopen(request,timeout=25) as r:
    result=json.load(r)
print('Registered commands:', ', '.join(x['name'] for x in result))
