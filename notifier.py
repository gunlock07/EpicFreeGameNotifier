"""Scheduled GitHub Actions notifier. Saves delivery state to state.json."""
import os
import json
import time
import logging
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from epic import get_catalog,get_games

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
STATE_PATH=Path(__file__).parent / 'state.json'
JST=timezone(timedelta(hours=9))

def read_state():
    try:
        state=json.loads(STATE_PATH.read_text('utf-8'))
        if not isinstance(state,dict):raise ValueError('invalid state')
    except FileNotFoundError: state={}
    return {'sent':state.get('sent',{}),'initialized':state.get('initialized',False)}

def write_state(state):
    temp=STATE_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    temp.replace(STATE_PATH)

def jst(dt):return dt.astimezone(JST).strftime('%Y年%m月%d日 %H:%M（日本時間）')

def embed(game,kind):
    label={'new':'🎁 新しい無料ゲーム','upcoming':'📅 次回の無料配布予告','reminder':'⏰ 無料配布終了間近'}[kind]
    description={'new':'無料配布が始まりました。期間中に受け取ってください！',
                 'upcoming':'Epic Games Storeで予告された次回の無料配布です。',
                 'reminder':'配布終了まで24時間以内です。受け取り忘れにご注意ください！'}[kind]
    result={'title':f'{label}：{game["title"]}'[:256], 'url':game['url'],
            'description':description, 'color':0x2ecc71 if kind=='new' else (0x3498db if kind=='upcoming' else 0xe67e22),
            'fields':[{'name':'開始','value':jst(game['start']),'inline':True},
                      {'name':'終了','value':jst(game['end']),'inline':True}],
            'footer':{'text':'Epic Free Game Notifier | 日本向け配信情報'}}
    if game.get('image') and game['image'].startswith('https://'):result['image']={'url':game['image']}
    return result

def send_message(token,channel,game,kind,role):
    content = f'<@&{role}>' if role and role.isdecimal() else ''
    payload={'content':content,'embeds':[embed(game,kind)],'allowed_mentions':{'parse':[], 'roles':[role] if content else []}}
    body=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    endpoint=f'https://discord.com/api/v10/channels/{channel}/messages'
    for attempt in range(4):
        request=Request(endpoint,data=body,method='POST',headers={'Authorization':'Bot '+token,'Content-Type':'application/json','User-Agent':'EpicFreeGameNotifier (https://github.com/)'} )
        try:
            with urlopen(request,timeout=25) as response:
                if response.status not in (200,201):raise RuntimeError(f'Discord returned {response.status}')
                return
        except HTTPError as e:
            if e.code in (429,500,502,503,504) and attempt<3:
                retry=2**attempt
                if e.code==429:
                    try: retry=float(json.loads(e.read()).get('retry_after',retry))
                    except (ValueError,TypeError):pass
                time.sleep(min(retry,15))
                continue
            raise RuntimeError(f'Discord API returned HTTP {e.code}') from e

def main():
    token=os.environ['DISCORD_BOT_TOKEN'].strip()
    channel=os.environ['DISCORD_CHANNEL_ID'].strip()
    role=os.environ.get('DISCORD_ROLE_ID','').strip()
    if not channel.isdecimal():raise ValueError('DISCORD_CHANNEL_ID must be numeric')
    now=datetime.now(timezone.utc)
    current, upcoming=get_games(get_catalog(),now)
    state=read_state()
    logging.info('Detected %d current, %d upcoming offers',len(current),len(upcoming))
    # Mark the first run's already-active offers as seen when requested.
    skip_existing=os.environ.get('SKIP_EXISTING_ON_FIRST_RUN','false').lower()=='true' and not state['initialized']
    all_offers=[('new',g) for g in current]+[('upcoming',g) for g in upcoming]
    for kind,game in all_offers:
        sent=state['sent'].setdefault(game['id'],{})
        if kind in sent:continue
        if kind=='new' and skip_existing:
            sent['new']='initial-skip'
            write_state(state)
            continue
        send_message(token,channel,game,kind,role)
        sent[kind]=datetime.now(timezone.utc).isoformat()
        write_state(state)
        logging.info('Sent %s: %s',kind,game['title'])
    for game in current:
        sent=state['sent'].setdefault(game['id'],{})
        if 'reminder' in sent:continue
        remaining=(game['end']-now).total_seconds()
        if 0<remaining<=24*3600:
            send_message(token,channel,game,'reminder',role)
            sent['reminder']=datetime.now(timezone.utc).isoformat()
            write_state(state)
            logging.info('Sent reminder: %s',game['title'])
    state['initialized']=True
    # Keep sent ids for 120 days; old giveaways receive a new ID when they recur.
    for key in list(state['sent']):
        try:
            start=datetime.fromisoformat(key.rsplit('|',1)[1])
            if (now-start).days>120:state['sent'].pop(key,None)
        except (ValueError,IndexError):pass
    write_state(state)
    logging.info('Completed successfully')

if __name__=='__main__': main()
