# coding: utf-8
''' cleanup, sentiment analysis, organisation, etc. of tweet data '''
import os
import time
import sys
from json           import loads
from tqdm           import tqdm

# my code
from chétane.config    import logger, source_path_raw, get_conf
from chétane.utils     import extract_emoji, extract_hashtags, tweet_fullsearch, dictpath, get_num_lines, counter_min_max, add_to_top
from chétane.backend   import db_add_activity, db_add_toptweet, db_commit, db_set_tag, db_set_candidate_activity, db_set_followers

def process_many_tweets(source, it_tweets, it_count, daystr):
    ''' process all tweets, update db only once at the end '''
    conf = get_conf()

    # some counters
    count_tweets = 0
    count_interact = 0
    count_fromcandidate = 0
    candidate_followers = 0

    # counters to store best tweets
    tt = conf.get('process_toptweets', 5)
    toptweets_likes     = counter_min_max(tt)
    toptweets_retweets  = counter_min_max(tt)
    toptweets_self      = counter_min_max(tt)
    toptweets_followers = []

    # store all tags / emoji data for the day
    hashtags = {}
    emojis = {}

    for tw in tqdm(it_tweets(), total=it_count):
        # clean
        if tw.get('full_text'):
            tw['text'] = tw.get('full_text')
        elif 'extended_tweet' in tw and 'full_text' in tw['extended_tweet']:
            tw['text'] = tw['extended_tweet']['full_text']

        # drop twit if not fr
        if tw['lang'] not in ('fr', 'und'):
            continue

        # drop if it doesnt have source keywords
        ftxt = tweet_fullsearch(tw).lower()
        for kw in source['keywords']:
            if kw.lower() in ftxt:
                break
        else:
            continue


        # check if this tweet is sent by current candidate
        if tw['user']['screen_name'].lower() == source['handle'].lower():
            candidate_followers = tw['user']['followers_count']
            # if not tw.get('is_subtweet'):
            #     count_fromcandidate += 1

            day_c = time.strftime('%Y-%m-%d', time.strptime(tw['created_at'], '%a %b %d %H:%M:%S +0000 %Y'))
            if day_c == daystr:
                count_fromcandidate += toptweets_self.update(tw['id'], tw, tw['favorite_count'])

        # add emojis & hashtags
        for t in extract_emoji(tw['text']):
            if not t in emojis:
                emojis[t] = 1
            else:
                emojis[t] += 1

        for t in extract_hashtags(tw['text']):
            if not t in hashtags:
                hashtags[t] = 1
            else:
                hashtags[t] += 1

        if tw.get('is_subtweet'):
            count_interact += 1
        elif 'retweeted_status' in tw:
            count_interact += 1
        else:
            count_tweets += 1

        toptweets_likes.update(tw['id'], tw, tw['favorite_count'])
        toptweets_retweets.update(tw['id'], tw, tw['retweet_count'])
        toptweets_followers = add_to_top(toptweets_followers, tw, 'user/followers_count', tt)

    # update db for this candidata / day
    db_add_activity(source['name'], count_tweets, 0, count_interact, daystr)
    db_set_candidate_activity(source['name'], count_fromcandidate, daystr)
    db_set_followers(source['name'], candidate_followers, daystr)

    # store tags / emojis to db
    for k, v in sorted(emojis.items(), key=lambda x: x[1], reverse=True)[:conf.get('process_emojis', 20)]:
        db_set_tag(source['name'], k, v, daystr)
    for k, v in sorted(hashtags.items(), key=lambda x: x[1], reverse=True)[:conf.get('process_hashtags', 20)]:
        db_set_tag(source['name'], k, v, daystr)

    # store top tweets
    for tw, val in toptweets_self.results():
        tw['__counter'] = val
        db_add_toptweet(source['name'], tw, 'self', daystr)
    for tw, val in toptweets_likes.results():
        tw['__counter'] = val
        db_add_toptweet(source['name'], tw, 'likes', daystr)
    for tw, val in toptweets_retweets.results():
        tw['__counter'] = val
        db_add_toptweet(source['name'], tw, 'retweets', daystr)
    for tw in toptweets_followers:
        tw['__counter'] = tw['user']['followers_count']
        db_add_toptweet(source['name'], tw, 'followers', daystr)

    db_commit(daystr)
    return 1


def process_candidate_day(src, opts):

    fpath = source_path_raw(src['name'], opts.daystr)
    try:
        nl = get_num_lines(fpath)
    except IOError:
        sys.stderr.write('warning: no file for candidate %s on %s\n' % (src['name'], opts.daystr))
        return

    print('> processing tweets %d from %s' % (nl, fpath))
    line_count = 0

    def it_tweets():
        nonlocal line_count
        with open(fpath, 'r', encoding='utf8') as f:
            for l in f:
                try:
                    tw = loads(l)
                except ValueError:
                    sys.stderr.write('invalid tweet %s:%d\n' % (fpath, line_count))
                    line_count += 1
                    continue
                line_count += 1
                yield tw

                if tw.get('retweeted_status'):
                    tw['retweeted_status']['is_subtweet'] = 1
                    yield tw['retweeted_status']
                if tw.get('quoted_status'):
                    tw['quoted_status']['is_subtweet'] = 1
                    yield tw['quoted_status']

    process_many_tweets(src, it_tweets, nl, opts.daystr)
