# coding: utf-8
''' handles all web serving to display results '''
import os

from datetime               import datetime
from bottle                 import route, run, static_file, request, abort
from jinja2                 import Environment, FileSystemLoader

from chétane.config         import logger, get_conf_val, conf_sources
from chétane.backend        import db_stats, db_getdays, db_alldays
from chétane.utils          import defaultparm, datestr_add
from chétane.jinjafilters   import register_filters

# graphs_days = None

def run_srv(host, port):
    ''' spawn a web server serving our templates '''
    # pylint: disable=W0612

    if not host:
        host = get_conf_val('bind_addr')
    if not port:
        port = int(get_conf_val('bind_port'))

    path_web        = os.path.realpath(get_conf_val('path_web'))
    path_templates  = path_web + '/html/'
    env             = Environment(loader=FileSystemLoader(path_templates))

    # load custom jinja filters
    register_filters(env)


    # ===================================================== #
    # data processing funcs
    # ===================================================== #
    def normalize_tags(tags):
        if not tags:
            return tags
        maxcount = max([ it[1] for it in tags ])
        if maxcount:
            for i in range(len(tags)):
                v = 50.0 * tags[i][1] / maxcount
                if v < 16:
                    v = 16
                if v > 50:
                    v = 50
                tags[i] = (tags[i][0], v)
                # import math
                # tags[i] = (tags[i][0], math.log2(tags[i][1]))
        return tags

    def date_adjascents(d, valid_days):
        dayprev = datestr_add('day', d, -1)
        daynext = datestr_add('day', d, +1)
        if dayprev not in valid_days:
            dayprev = None
        if daynext not in valid_days:
            daynext = None
        return dayprev, daynext

    def get_candidates_data(daystr):
        # get date
        if not daystr:
            daystr = datetime.now().strftime('%Y-%m-%d')

        # get list of valid days
        valid_days = db_getdays()
        if not valid_days:
            abort(500, 'No Data')

        if daystr < valid_days[0]:
            daystr = valid_days[0]
        elif daystr > valid_days[-1]:
            daystr = valid_days[-1]
        if daystr not in valid_days:
            daystr = valid_days[-1]

        dayprev, daynext = date_adjascents(daystr, valid_days)

        # get stats
        candidates = db_stats(daystr)
        if not candidates:
            abort(404, 'Not Found')

        # merge candidate data & conf sources in the same dict
        sources = conf_sources()
        for s in sources:
            for c in candidates:
                if c['candidate'] == s['name']:
                    c.update(s)
                    c['tags'] = normalize_tags(c['tags'])

        # sort candidates & give them ranks
        candidates = sorted(candidates, key=lambda x: x['tweets'], reverse=True)
        for i in range(len(candidates)):
            candidates[i]['rank'] = i + 1

        # fix outdated profile pictures from candidates top tweets
        for c in candidates:
            if c.get('top_self'):
                c['photo'] = c['top_self'][0].get('user', {}).get('profile_image_url_https', '').replace('_normal.', '_400x400.')

        return daystr, dayprev, daynext, valid_days, candidates

    # ===================================================== #
    # static assets routes
    # ===================================================== #
    @route(r'/img/<fpath:re:.*\.(png|svg)>')
    def static_img(fpath):
        return static_file(fpath, root='%s/img' % path_web)

    @route(r'/css/<fpath:re:.*\.(css|map|ttf)>')
    def static_css(fpath):
        return static_file(fpath, root='%s/css' % path_web)

    @route(r'/js/<fpath:re:.*\.(js|map)>')
    def static_js(fpath):
        return static_file(fpath, root='%s/js' % path_web)

    @route('/favicon.ico')
    def favicon():
        return static_file('favicon.ico', root='%s/img' % path_web)


    # ===================================================== #
    # main routes
    # ===================================================== #


    @route('/')
    @route('/index.html')
    @route('/ranks')
    @route('/ranks.html')
    def ranks(daystr=None):
        tmpl = env.get_template('ranks.html')
        return tmpl.render(
            page='ranks',
            sources=conf_sources(),
            **db_alldays(),
        )


    @route('/graphs')
    @route('/graphs.html')
    def graphs():
        sources=conf_sources()
        tmpl = env.get_template('graphs.html')
        return tmpl.render(
            page='graphs',
            sources=sources,
            attrs={ src['name']: src for src in sources },
            **db_alldays()
        )


    @route('/tweets')
    @route('/tweets.html')
    @route('/tweets/<daystr>')
    @route('/tweets/<daystr>.html')
    def index(daystr=None):
        # get data
        daystr, dayprev, daynext, valid_days, candidates = get_candidates_data(daystr)

        # render
        tmpl = env.get_template('tweets.html')
        return tmpl.render(
            page='tweets',
            sources=conf_sources(),
            daystr=daystr,
            candidates=candidates,
            dayprev=dayprev,
            daynext=daynext,
            days=valid_days,
            # minsize=500,
        )

    @route('/tags')
    @route('/tags.html')
    def tags(daystr=None):

        data = db_alldays()
        sources = conf_sources()
        colors = {}
        photos = {}
        names = {}
        for src in sources:
            colors[src['name']] = src['color']
            photos[src['name']] = src['photo']
            names[src['name']] = src['fullname']

        tagdata = {}
        for day in data['days']:
            daydata = {}

            for c in data['candidates']:
                for tag, val in data['cstats'][c][day]['tags']:
                    if not tag in daydata:
                        daydata[tag] = {}
                    daydata[tag][c] = val
            for tag in daydata:
                daydata[tag]['_total'] = sum([ daydata[tag][c] for c in daydata[tag] ])

            lst = sorted([ (tag, daydata[tag]['_total']) for tag in daydata ], key=lambda x: x[1], reverse=True)[:30]
            tagdata[day] = { tag: daydata[tag] for tag, _ in lst }

        nodes = {}
        links = {}
        for day in data['days']:
            nodes[day] = []
            links[day] = []
            for c in data['candidates']:
                nodes[day].append({
                    'id': 'id_' + c,
                    'type': 'candidate',
                    'name': c,
                    'class': 'node node_candidate',
                    'value': data['cstats'][c][day]['tweets'],
                    'color': colors[c],
                    'photo': photos[c],
                    'title': names[c] + '\n' + str(data['cstats'][c][day]['tweets']) + ' tweets\n' + '\n'.join([ '%s: %d' % (tag, tagdata[day][tag][c]) for tag in tagdata[day] if c in tagdata[day][tag] ]),
                    'text': names[c][names[c].find(' ')+1:],
                })
            for tag in tagdata[day]:
                nodes[day].append({
                    'id': 'id_tag_' + tag.replace('#',''),
                    'type': 'tag',
                    'name': tag.replace('#',''),
                    'class': 'node node_hashtag node_tag_' + tag.replace('#','') + ' ' + ' '.join(['cand_' + c for c in tagdata[day][tag] if not c.startswith('_total') ]),
                    'value': tagdata[day][tag]['_total'],
                    'candidates': list(tagdata[day][tag].keys()),
                    'color': '#000000',
                    'title': 'Hashtag ' + tag + '\n' + '\n'.join('%s: %d' % (c, tagdata[day][tag][c]) for c in tagdata[day][tag]),
                    'text': tag,
                })
                for c in tagdata[day][tag]:
                    if c.startswith('_'):
                        continue
                    links[day].append({
                        'id': 'id_links_%s_%s' % (tag.replace('#',''), c),
                        'source': 'id_tag_' + tag.replace('#',''),
                        'target': 'id_' + c,
                        'value': tagdata[day][tag][c],
                        'color': '#' + colors[c],
                        'class': 'link cand_' + c + ' link_%s_%s' % (tag.replace('#',''), c),
                    })


        tmpl = env.get_template('tags.html')
        return tmpl.render(
            page='tags',
            sources=sources,
            nodes=nodes,
            links=links,
            daystr=data['days'][-1],
            **data,
        )




    # preload data
    logger.info('[server] > preloading data..')
    db_alldays()

    # start it up now
    logger.info('[server] > starting web server on %s:%d', host, port)
    run(host=host, port=port)

