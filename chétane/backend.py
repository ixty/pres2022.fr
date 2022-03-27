# coding: utf-8
''' database stuff - store & load data '''
import os
from datetime       import datetime
from time           import strftime, gmtime
from sqlite3        import connect, Row
from json           import dumps, loads

from chétane.config    import logger, load_conf, get_conf_val, conf_sources


load_conf()
# =========================================================================== #
# generic-y stuff
# =========================================================================== #
db_cons = {'daystr': None, 'con': None}

def _db_session(daystr=None, erronnofile=False):

    if not daystr:
        # daystr = datetime.now().strftime('%Y-%m-%d')
        erronnofile = True

    # already have a goog connection to db
    if db_cons['daystr'] == daystr:
        return db_cons['con']

    # connection has expired, close & open new db
    elif db_cons['daystr']:
        db_cons['con'].commit()
        db_cons['con'].close()
        db_cons['con'] = None
        db_cons['daystr'] = None

    # open new db
    db_cons['daystr'] = daystr
    db_name = '%s/%s.db' % (get_conf_val('datadir'), daystr)
    if erronnofile and not os.path.isfile(db_name):
        return None
    con = connect(db_name)
    db_cons['con'] = con

    # init tables
    con.execute("""
        create table if not exists candidates (
            candidate   text primary key,
            tweets      int,
            likes       int,
            interacts   int,
            sentiment   real,
            sentiment_c int,
            followers   int,
            activity    int
        );""")
    con.execute("""
        create table if not exists tags (
            candidate   text,
            tag         text,
            val         int,
            UNIQUE(candidate, tag)
        );""")
    con.execute("""
        create table if not exists toptweets (
            candidate   text,
            toptype     text,
            id          bigint,
            data        json,
            UNIQUE(candidate, id, toptype)
        );""")

    # add candidates
    for src in conf_sources():
        con.execute('''
            insert or ignore into candidates(
                candidate, tweets, likes, interacts, sentiment, sentiment_c, followers, activity
            ) values (
                ?, 0, 0, 0, 0.0, 0, 0, 0
            )''', [src['name']])
    # all good now
    con.commit()
    return con

def db_add_activity(candidate, new_tweets, new_likes, new_interacts, daystr=None):
    con = _db_session(daystr)
    con.execute('update candidates set tweets = tweets + ?, likes = likes + ?, interacts = interacts + ? where candidate = ?',
        [new_tweets, new_likes, new_interacts, candidate])
    # con.commit()

def db_add_sentiment(candidate, sentiment, daystr=None):
    con = _db_session(daystr)
    con.execute('update candidates set sentiment = sentiment + ?, sentiment_c = sentiment_c + 1 where candidate = ?',
        [sentiment, candidate])
    # con.commit()

def db_set_sentiment(candidate, sentiment_tot, sentiment_count, daystr=None):
    con = _db_session(daystr)
    con.execute('update candidates set sentiment = ?, sentiment_c = ? where candidate = ?',
        [sentiment_tot, sentiment_count, candidate])
    # con.commit()

def db_set_followers(candidate, num_followers, daystr=None):
    con = _db_session(daystr)
    con.execute('update candidates set followers = ? where candidate = ?',
        [num_followers, candidate])
    # con.commit()

def db_set_candidate_activity(candidate, activity, daystr=None):
    con = _db_session(daystr)
    con.execute('update candidates set activity = ? where candidate = ?',
        [activity, candidate])
    # con.commit()

def db_add_tag(candidate, tag, daystr=None):
    con = _db_session(daystr)
    cur = con.execute('update tags set val = val + 1 where candidate = ? and tag = ?',
        [candidate, tag])
    if cur.rowcount == 0:
        con.execute('insert into tags (candidate, tag, val) values (?, ?, 1)',
            [candidate, tag])
    # con.commit()

def db_set_tag(candidate, tag, val, daystr=None):
    con = _db_session(daystr)
    cur = con.execute('insert or replace into tags values (?, ?, ?)',
        [candidate, tag, val])
    # con.commit()

def db_add_toptweet(candidate, tweet, top_type, daystr=None):

    con = _db_session(daystr)
    con.execute('insert or replace into toptweets values (?, ?, ?, ?)', [candidate, top_type, tweet['id'], dumps(tweet)])

    # cur = con.execute('select count(id) from toptweets where candidate = ?', [candidate])
    # cnt = cur.fetchone()[0] or 0
    # if cnt < top_count or not cnt:
    #     con.execute('insert or replace into toptweets values (?, ?, ?, ?)', [candidate, top_type, tweet['id'], dumps(tweet)])
    #     # con.commit()
    #     return

    # # get min of json_key
    # cur = con.execute('select id, min(json_extract(data, ?)) from toptweets where candidate = ?', [json_key, candidate])
    # res = cur.fetchone()
    # if json_val > res[1]:
    #     con.execute('delete from toptweets where candidate = ? and id = ?', [candidate, res[1]])
    #     con.execute('insert or replace into toptweets values (?, ?, ?, ?)', [candidate, top_type, tweet['id'], dumps(tweet)])
    #     # con.commit()
    #     return

def db_commit(daystr=None):
    con = _db_session(daystr)
    if con:
        con.commit()

def db_getdays():
    out = []
    for path in os.listdir(get_conf_val('datadir')):
        try:
            datetime.strptime(path, '%Y-%m-%d.db')
        except ValueError:
            continue
        out.append(path[:-3])
    return sorted(out)


def db_stats(daystr=None, notweets=False, notags=False):
    out = []
    con = _db_session(daystr, True)
    if not con:
        return None
    cur = con.execute('select * from candidates order by candidate')
    hdr = [i[0] for i in cur.description]
    for row in cur.fetchall():
        cstats = dict(zip(hdr, row))

        if not notweets:
            cur = con.execute('select data from toptweets where candidate = ? and toptype = ? order by json_extract(data, ?) desc',
                [cstats['candidate'], 'likes', '$.__counter'])
            cstats['top_likes'] = [ loads(row[0]) for row in cur.fetchall() ]

            cur = con.execute('select data from toptweets where candidate = ? and toptype = ? order by json_extract(data, ?) desc',
                [cstats['candidate'], 'retweets', '$.__counter'])
            cstats['top_retweets'] = [ loads(row[0]) for row in cur.fetchall() ]

            cur = con.execute('select data from toptweets where candidate = ? and toptype = ? order by json_extract(data, ?) desc',
                [cstats['candidate'], 'followers', '$.__counter'])
            cstats['top_followers'] = [ loads(row[0]) for row in cur.fetchall() ]

            cur = con.execute('select data from toptweets where candidate = ? and toptype = ? order by json_extract(data, ?) desc',
                [cstats['candidate'], 'self', '$.__counter'])
            cstats['top_self'] = [ loads(row[0]) for row in cur.fetchall() ]

        if not notags:
            cur = con.execute('select tag, val from tags where candidate = ? order by val desc', [cstats['candidate']])
            cstats['tags'] = [ (row[0], row[1]) for row in cur.fetchall() ]

        out.append(cstats)
    con.close()
    db_cons['con'] = None
    db_cons['daystr'] = None
    return out

_db_alldays_data = None
def db_alldays():
    global _db_alldays_data
    if _db_alldays_data:
        return _db_alldays_data
    days = db_getdays()
    days_stats = {}
    cand_stats = {}
    rankings = {}
    firstscore = {}

    for day in days:
        ds = {}

        daystats = db_stats(day, notweets=True, notags=False)
        for c in daystats:
            ds[c['candidate']] = c
            if not c['candidate'] in cand_stats:
                cand_stats[c['candidate']] = {}
            if not c['candidate'] in firstscore:
                firstscore[c['candidate']] = c
            cand_stats[c['candidate']][day] = c

        days_stats[day] = ds
        rankings[day] = {}
        sdt = sorted(daystats, key=lambda x: x['tweets'], reverse=True)
        for i in range(len(sdt)):
            c = sdt[i]
            rankings[day][c['candidate']] = i + 1

    _db_alldays_data = {
        'days': days,
        'daystats': days_stats,
        'candidates': [ c['candidate'] for c in sorted(days_stats[days[-1]].values(), key=lambda x: x['tweets'], reverse=True) ],
        'cstats': cand_stats,
        'rankings': rankings,
        'firstscore': firstscore,
    }
    return _db_alldays_data

# get all emojis that are next to another
    # add each emoji (except if next is ZWJ)
    # all the whole thing

# 👨‍👩‍👧‍👦‍
# 👨‍ 👩‍ 👧‍ 👦‍
# ♻️
