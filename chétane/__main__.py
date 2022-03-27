#!/usr/bin/env python3
# coding: utf-8
''' chétane module main: argparse & service multiprocessing '''
import os
from sys                import exit as sysexit
from argparse           import ArgumentParser
from datetime           import datetime, timedelta

from chétane.config        import logger, load_conf, conf_source, default_creds, get_conf_val
from chétane.sources       import twit_search, twit_realtime
from chétane.process       import process_candidate_day
from chétane.server        import run_srv


def cmd_source(opts):
    ''' will start either searching or realtime tweet acquisition '''

    # real time tweets acquisition
    if not opts.search:
        twit_realtime(default_creds(opts.account), opts.source)
        # only reached on errors
        sysexit(1)

    # search tweets history
    else:
        # defaults to today
        if not opts.date_to:
            opts.date_to = datetime.now().strftime("%Y-%m-%d")
        # defaults to 1 week ago
        if not opts.date_from:
            opts.date_from = (datetime.strptime(opts.date_to, '%Y-%m-%d') - timedelta(days=7)).strftime("%Y-%m-%d")
        ret = twit_search(default_creds(opts.account), opts.date_from, opts.date_to, opts.source)
        sysexit(ret)


def cmd_process(opts):
    ''' process all new tweets for one specific source, or all of them '''

    if opts.source:
        # process_raw(conf_source(opts.source), opts)
        process_candidate_day(conf_source(opts.source), opts)

    else:
        for src in get_conf_val('sources'):
            # process_raw(src, opts)
            process_candidate_day(src, opts)

def cmd_yesterday(opts):
    ''' process all data from last day '''

    dt = datetime.now() + timedelta(days=-1)
    ds = '%4d-%.2d-%.2d' % (dt.year, dt.month, dt.day)
    opts.daystr = ds

    for src in get_conf_val('sources'):
        process_candidate_day(src, opts)

    if not opts.noremove:
        print('> archiving & deleting day\'s data')
        if os.system('7z a data-%s.7z data-%s && rm -rf data-%s/' % (ds, ds, ds)):
            exit(1)


def cmd_server(opts):
    ''' runs the web server to display results '''
    run_srv(opts.addr, opts.port)


def main():
    ''' entry point of module '''

    # main arg parser + global switches
    parser = ArgumentParser(description='twitter sentiments analysis')
    parser.add_argument('-c', '--config', default=None, help='path to config file (defaults to ./chétane.conf, /etc/chétane/chétane.conf)')
    parser.set_defaults(func=lambda x: parser.print_help())

    # different operating modes
    rp = parser.add_subparsers()
    sp_data = rp.add_parser('source',       help='data acquisition mode')
    sp_proc = rp.add_parser('process',      help='data processing mode')
    sp_yest = rp.add_parser('yesterday',    help='process previous day\'s data')
    sp_srv  = rp.add_parser('server',       help='web server mode')

    # data acquisition commands
    sp_data.add_argument('--account',       help='use specific credentials from config file', default=None)
    sp_data.add_argument('--search',        help='do not perform real time acquisition but perform a search of old data',
                                            action='store_true')
    sp_data.add_argument('--date-from',     help='search start date (yyyy-mm-dd)')
    sp_data.add_argument('--date-to',       help='search start date (yyyy-mm-dd)')
    sp_data.add_argument('--source',        help='restrict to a specific source', default=None)
    sp_data.set_defaults(func=cmd_source)

    # data processing options
    sp_proc.add_argument('--source',        help='data source name')
    sp_proc.add_argument('--noremove',      help='do not delete raw tweets', default=False, action='store_true')
    sp_proc.add_argument('daystr',          help='specify YYYY-MM-DD day')
    sp_proc.set_defaults(func=cmd_process)

    # process last day's data
    sp_yest.add_argument('--noremove',      help='do not delete raw tweets', default=False, action='store_true')
    sp_yest.set_defaults(func=cmd_yesterday)

    # web server for output
    sp_srv.add_argument('-a', '--addr',     help='listen addr', default=None)
    sp_srv.add_argument('-p', '--port',     help='listen port', default=None, type=int)
    sp_srv.set_defaults(func=cmd_server)

    # do the parsing & start corresponding action
    opts = parser.parse_args()
    load_conf(opts.config)
    opts.func(opts)

if __name__ == '__main__':
    main()
