# coding: utf-8
''' custom jinja template filters '''
import json
from datetime       import datetime
from chétane.config    import get_conf_val
from chétane.utils import dictpath

def fmt_num(val):
    if val < 0:
        return '-' + fmt_num(-val)
    if val >= 1000000000:
        return '%.1fG' % (val / 1000000000)
    if val >= 1000000:
        return '%.1fM' % (val / 1000000)
    if val >= 1000:
        return '%.1fK' % (val / 1000)
    return '%d' % val

def delta_to_str(delta):
    if delta.days >= 365:
        return '%.1f ans' % (delta.days / 365,)
    elif delta.days >= 30:
        return '%d mois' % (delta.days / 30,)
    elif delta.days >= 1:
        return '%d jours' % (delta.days,)
    elif delta.seconds >= 3600:
        return '%d heures' % (delta.seconds / 3600,)
    elif delta.seconds >= 60:
        return '%d mins' % (delta.seconds / 60,)
    else:
        return '%d secs' % (delta.seconds,)

def datestr_to_now(s):
    if '.' not in s:
        s = s + '.0'
    delta = datetime.now() - datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')
    return delta_to_str(delta)

def tweet_since(tw, daystr):
    d0 = datetime.strptime(tw['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
    d1 = datetime.strptime(daystr, '%Y-%m-%d')
    return delta_to_str(d1 - d0)

def tweet_fixtext(tw):
    t = tw['text']
    r = dictpath(tw, 'retweeted_status/extended_tweet/full_text') or dictpath(tw, 'retweeted_status/text')
    if r:
        t = r

    for media in dictpath(tw, 'entities/media', []):
        t = t.replace(media['url'], '')
    for media in dictpath(tw, 'extended_tweet/entities/media', []):
        t = t.replace(media['url'], '')
    for media in dictpath(tw, 'extended_tweet/extended_entities/media', []):
        t = t.replace(media['url'], '')

    return t

def to_json(s):
    return json.dumps(s, indent=4)

def register_filters(env):
    env.filters['fmt_num']          = fmt_num
    env.filters['datestr_to_now']   = datestr_to_now
    env.filters['json']             = to_json
    env.filters['tweet_since']      = tweet_since
    env.filters['tweet_fixtext']    = tweet_fixtext

