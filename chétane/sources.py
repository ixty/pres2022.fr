# coding: utf-8
''' code to get data from twitter '''
import os
import json
from time               import time, sleep, ctime
from datetime           import datetime, timedelta
from threading          import Thread
from traceback          import format_exc
from urllib3.exceptions import ProtocolError

import tweepy

from chétane.config    import logger, get_conf_val, source_path_raw
from chétane.utils     import daterange, tweet_fullsearch

# stats[source] = [ datetime, ... ] list of timestamps of last received tweets
# use stats_getdata() to consolidate & retrieve the results
stats_data      = {}
stats_thr       = None
stats_end       = False


# =========================================================================== #
# tweet processing
# =========================================================================== #

def twit_sources(tw):
    '''
        finds which source(s) this tweet matched
        returns array of src
    '''
    srcs = get_conf_val('sources')

    # build a keyword to source lookup dict
    keywords = {}
    for src in srcs:
        for kw in src['keywords']:
            kw = kw.lower()
            if kw not in keywords:
                keywords[kw] = []
            keywords[kw].append(src)

    # add up all text fields that can contain our search keywords
    ftxt = tweet_fullsearch(tw)

    # lookup all keywords
    srcs = []
    for kw in keywords:
        if kw in ftxt:
            for src in keywords[kw]:
                if src not in srcs:
                    srcs.append(src)

    # analyze subtweets
    for st in ('quoted_status', 'retweeted_status'):
        if st in tw:
            for src in twit_sources(tw[st]):
                if src not in srcs:
                    srcs.append(src)

    # dont add subtweets if it doesnt match our keywords!
    return srcs


def twit_handle(tw):
    ''' launched for every received tweet '''

    # does this tweet match more than one data source?
    for src in twit_sources(tw):
        logger.debug('[source] > [%s] %s (%s): %s', src['name'], tw['user']['screen_name'], tw['user']['name'], tw['text'].strip())

        path = source_path_raw(src['name'])
        with open(path, 'a+') as f:
            f.write(json.dumps(tw))
            f.write('\n')

        # record some statistics
        stats_newtweet(src['name'])


def get_all_keywords(source=None):
    ''' returns all the keywords for all sources '''
    srcs = get_conf_val('sources')
    keywords = []

    for src in srcs:
        if source and src['name'] != source:
            continue
        logger.info('[source] > [%-12s] keywords [%s]', src['name'], ','.join(src['keywords']))

        for kw in src['keywords']:
            keywords.append(kw)

    return keywords


# =========================================================================== #
# acquisition: search
# =========================================================================== #

def twit_search_day(creds, kwords, date):
    ''' uses search api to get all matching tweets for a single day '''

    auth = tweepy.AppAuthHandler(creds['consumer_key'], creds['consumer_secret'])
    api  = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    max_id = None
    day_c = date.strftime('%Y-%m-%d')
    day_n = (date + timedelta(days=1)).strftime('%Y-%m-%d')

    q = ' OR '.join(kwords) + ' since:%s until:%s' % (day_c, day_n)
    logger.info('[source] > search query [%s]', q )

    while 1:
        try:
            if not max_id:
                tweets = api.search(q=q, count=100)
            else:
                tweets = api.search(q=q, count=100, max_id=str(max_id))

            logger.info('[source] > got %d tweets', len(tweets))
            if not len(tweets):
                break

            for tw in tweets:
                twit_handle(tw._json) # pylint: disable=W0212

            max_id = tweets[-1].id - 1

        except tweepy.TweepError as e:
            logger.error('[source] > tweepy error - %s', str(e))
            break


def twit_search(creds, date_from, date_to, source=None):
    ''' gets all tweets that match specific keywords between 2 dates '''
    logger.info('[source] > search (%s to %s)', date_from, date_to)
    stats_start()

    # get keywords from all data sources
    kwords  = get_all_keywords(source)

    # fix time_start for all sources
    for src in get_conf_val('sources'):
        if source and src['name'] != source:
            continue

    # search tweets for each day
    d0 = datetime.strptime(date_from, '%Y-%m-%d')
    d1 = datetime.strptime(date_to, '%Y-%m-%d')

    for d in daterange(d0, d1, False):
        twit_search_day(creds, kwords, d)
    stats_stop()
    logger.info('[source] > search done')
    return 0


# =========================================================================== #
# acquisition: streaming
# =========================================================================== #

def twit_realtime(creds, source=None):
    ''' real time tweets '''
    logger.info('[source] > realtime')
    stats_start()

    # get keywords from all data sources
    kwords  = get_all_keywords(source)
    if not len(kwords):
        logger.warning('[source] > got no keywords to track, aborting')
        return

    # create auth obj from conf's credentials
    auth    = tweepy.OAuthHandler(creds['consumer_key'], creds['consumer_secret'])
    auth.set_access_token(creds['access_token_key'], creds['access_token_secret'])

    # create stream listener now
    class stream_listener(tweepy.Stream):
        ''' class to listen for twitter stream events '''

        def __init__(self):
            super(stream_listener, self).__init__(creds['consumer_key'], creds['consumer_secret'], creds['access_token_key'], creds['access_token_secret'])

        def on_status(self, status):
            twit_handle(status._json) # pylint: disable=W0212

        def on_error(self, status_code):
            logger.error(status_code)
            return False

    # instanciate it ...
    api     = tweepy.API(auth, wait_on_rate_limit=True)
    stream  = stream_listener()

    # listen & wait for real time tweets now
    try:
        stream.filter(track=kwords)
    except KeyboardInterrupt:
        logger.info('[source] > interrupt')
    except ProtocolError as e:
        logger.error('[source] > error:')
        tb = format_exc()
        logger.error(tb)
    finally:
        stream.disconnect()
        stats_stop()
        return 1 # return error

# =========================================================================== #
# statistics on data acquisition
# =========================================================================== #

def stats_newtweet(src_name):
    ''' add a new timestamp to this src's stats '''

    if src_name not in stats_data:
        stats_data[src_name] = {
            'timestamps':   [],
            'count_acq':    0,
            'rate_m':       0.0,
        }

    # we store all added tweets' timestamps to a list
    stats_data[src_name]['timestamps'].append(datetime.now())
    stats_data[src_name]['count_acq'] += 1


def stats_getdata():
    '''
        consolidates statistics for all data sources
        returns dict[source] = { 'count_acq': xxx, 'rate_m': yyy }
    '''
    out = {}
    now = datetime.now()
    per = timedelta(seconds=60)

    for src in stats_data:
        lst = stats_data[src]['timestamps']

        stats_data[src]['timestamps'] = [ dt for dt in lst if dt + per >= now ]
        stats_data[src]['rate_m'] = len(stats_data[src]['timestamps'])

        out[src] = {
            'count_acq':    stats_data[src]['count_acq'],
            'rate_m':       stats_data[src]['rate_m'],
        }

    # out['timestamp'] = str(now)
    return out


def stats_thread():
    ''' target for a thread to consolidate & dump to disk each data source's statistics & info '''
    last_refresh = time()
    last_report  = time()

    while not stats_end:
        sleep(0.1)
        now = time()

        # consolidate data every X seconds
        if last_refresh + get_conf_val('source_stats') < now:
            last_refresh = now
            stats = stats_getdata()
            for src in stats:
                # output to disk
                stats[src]['time_last'] = str(datetime.now())

                # different timer to avoid spamming logs
                if last_report + get_conf_val('source_report') < now:
                    logger.info('[source] > [%-20s] %-6d tweets (%-6.1f tw/m)', src, stats[src]['count_acq'], stats[src]['rate_m'])

            if last_report + get_conf_val('source_report') < now:
                logger.info('[source] > - last update time %s', ctime())
                last_report = now


def stats_start():
    ''' litle helper to start statistics update thread '''
    global stats_thr
    global stats_end
    stats_end = False
    stats_thr = Thread(target=stats_thread, name='source_stats')
    stats_thr.daemon = True
    stats_thr.start()


def stats_stop():
    ''' litle helper to stop statistics update thread '''
    global stats_thr
    global stats_end
    stats_end = True
    stats_thr.join(1)
