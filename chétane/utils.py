# coding: utf-8
''' various utilities '''
import string
import subprocess
from os         import path
from json       import load
from datetime   import datetime, timedelta
# from emoji      import EMOJI_DATA
import demoji


def daterange(start_date, end_date, include_enddate=False):
    ''' generator that yields every day-datetime between 2 dates '''
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)
    if include_enddate:
        yield end_date

def daterangestr(start_date, end_date, include_enddate=False):
    ''' generator that yields every day-datetime between 2 string dates '''
    if start_date == end_date:
        return [ start_date ]
    d0 = datetime.strptime(start_date, '%Y-%m-%d')
    d1 = datetime.strptime(end_date,   '%Y-%m-%d')
    return [ datetime.strftime(d, '%Y-%m-%d') for d in daterange(d0, d1, include_enddate) ]

def datestr_add(mode, datestr, val):
    d = datetime.strptime(datestr, '%Y-%m-%d')
    if mode == 'day':
        d += timedelta(days=val)
    elif mode == 'week':
        d += timedelta(days=val*7)
    return datetime.strftime(d, '%Y-%m-%d')

def dictpath(d, pth, default=None):
    ''' extract a val from a dict, supports addressing subitems with / (ex: "obj/inner/key") '''
    if '/' in pth:
        root, _, val = pth.partition('/')
        if root == '*':
            return ' '.join([ dictpath(d[i], val, default) for i in range(len(d)) ])
        if root in d:
            return dictpath(d[root], val, default)
        return default

    if pth in d and d[pth]:
        return d[pth]

    return default

def extract_emoji(s):
    ''' returns a list of all emojis found in str
        handles sequences like '🧑🏾‍🦱'
    '''

    return list(demoji.findall(s).keys())

def get_num_lines(fpath):
    p = subprocess.Popen(['wc', '-l', fpath], stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE)
    result, err = p.communicate()
    if p.returncode != 0:
        raise IOError(err)
    return int(result.strip().split()[0])

def extract_hashtags(s):
    ''' returns a list of all hashtags found in str '''
    out = []
    for w in s.split():
        if w.startswith('#'):
            while w and w[-1] in string.punctuation:
                w = w[:-1]
            out.append(w)
    return out


def json_load(p):
    ''' loads a file as json or return an empty dict '''
    if not path.isfile(p):
        return {}
    try:
        with open(p, 'r') as f:
            return load(f)
    except ValueError:
        return {}


def defaultparm(d, key, val):
    ''' set a val in a dict if key doesnt exist or if val evals to None '''
    if not key in d or not d[key]:
        d[key] = val


def tweet_fullsearch(tw):
    ''' return a concatenated string of all fields of interest in a tweet where we can find our keywords '''
    return ' '.join([
        dictpath(tw, f, '') for f in [
            'text',
            'full_text',
            'user/screen_name',
            'user/name',
            # 'user/description',
            'entities/user_mentions/*/name',
            'entities/user_mentions/*/screen_name',
            'entities/hashtags/*/text',
            # 'entities/urls/*/expanded_url',
            'extended_tweet/full_text',
            'extended_tweet/entities/user_mentions/*/name',
            'extended_tweet/entities/user_mentions/*/screen_name',
            'extended_tweet/entities/hashtags/*/text',
            # 'extended_tweet/entities/urls/*/expanded_url',
        ]
    ]).lower()


class counter_min_max():
    def __init__(self, max_count):
        ''' a counter for objects with increasing values only '''
        self.max_count = max_count
        self.mins = {}
        self.vals = []

    def update(self, id_, item, val_cur):
        ret = 0
        updated = 0

        # set the min if its the first time we see this item
        if id_ not in self.mins:
            self.mins[id_] = val_cur - 1

        val = val_cur - self.mins[id_]
        for i in range(len(self.vals)):
            if id_ == self.vals[i][0]:
                # already exists in top
                # update return 0
                updated = 1
                self.vals[i][1] = val
                self.vals[i][2] = item
                break
        else:
            self.vals.append([ id_, val, item ])

        self.vals = sorted(self.vals, key=lambda it: it[1], reverse=True)[:self.max_count]
        for v in self.vals:
            # found in final top list? ret 1
            if v[0] == id_:
                ret = 1 if not updated else 0
        return ret

    def results(self):
        ''' returns [ (item, item_score) ]'''
        return [ (o, v) for i, v, o in self.vals ]

def add_to_top(toptweets, tw, key, count=5):
    for i in range(len(toptweets)):
        # already have this tweet in top? if yes, update it
        if toptweets[i]['id'] == tw['id']:
            toptweets[i] = tw
            break
        # already have a tweet from the same user? take this one if it has more likes than the one we currently have
        if dictpath(tw, 'user/screen_name') == dictpath(toptweets[i], 'user/screen_name'):
            if tw['favorite_count'] > toptweets[i]['favorite_count']:
                toptweets[i] = tw
            break
    else:
        val = dictpath(tw, key, 0)
        if val:
            toptweets = sorted(toptweets + [tw], key=lambda tw: dictpath(tw, key, 0), reverse=True)[:count]
    return toptweets

