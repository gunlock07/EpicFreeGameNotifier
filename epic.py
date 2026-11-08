"""Read Epic Store promotional data, without third-party Python dependencies."""
from datetime import datetime, timezone
from urllib.parse import urlencode, quote
import json
import urllib.request

URL = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions'

def parse_date(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)

def get_catalog():
    query = urlencode({'locale': 'ja-JP', 'country': 'JP', 'allowCountries': 'JP'})
    req = urllib.request.Request(URL+'?'+query, headers={'User-Agent':'EpicFreeGameNotifier/2.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def get_games(catalog, now=None):
    now = now or datetime.now(timezone.utc)
    elements = catalog['data']['Catalog']['searchStore']['elements']
    current, upcoming = {}, {}
    for g in elements:
        if g.get('offerType') not in (None, 'BASE_GAME'):
            continue
        prom = g.get('promotions') or {}
        for field, destination in [('promotionalOffers',current),('upcomingPromotionalOffers',upcoming)]:
            for group in prom.get(field) or []:
                for offer in group.get('promotionalOffers') or []:
                    try:
                        start, end = parse_date(offer['startDate']), parse_date(offer['endDate'])
                        discount = (offer.get('discountSetting') or {}).get('discountPercentage')
                    except (ValueError, KeyError, TypeError):
                        continue
                    if discount != 0 or end <= start:
                        continue
                    if field == 'promotionalOffers' and not (start <= now < end):
                        continue
                    if field == 'upcomingPromotionalOffers' and start <= now:
                        continue
                    slug = next((m.get('pageSlug') for m in g.get('offerMappings') or [] if m.get('pageSlug')), None)
                    slug = slug or g.get('productSlug') or g.get('urlSlug')
                    if slug and str(slug).startswith('https://store.epicgames.com/'):
                        game_url = slug
                    elif slug:
                        slug = str(slug).strip('/').removesuffix('/home')
                        game_url = 'https://store.epicgames.com/ja/p/' + quote(slug, safe='/')
                    else:
                        game_url = 'https://store.epicgames.com/ja/free-games'
                    imgs = g.get('keyImages') or []
                    img = next((im.get('url') for kind in ('OfferImageWide','DieselStoreFrontWide','Thumbnail','OfferImageTall') for im in imgs if im.get('type') == kind and im.get('url')), None)
                    uid = str(g.get('id') or g.get('namespace') or slug or g.get('title')) + '|' + start.isoformat()
                    destination[uid] = {'id':uid, 'title':g.get('title') or 'タイトル未発表', 'start':start, 'end':end,'url':game_url,'image':img}
    return sorted(current.values(),key=lambda v:v['end']), sorted(upcoming.values(),key=lambda v:v['start'])
