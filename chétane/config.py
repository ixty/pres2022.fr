# coding: utf-8
''' config file loading & utilities '''
import os
import sys
import json
import logging
import datetime
import yaml

# currently loaded config
_loaded_config = None

# main application logger
logger = logging.getLogger('chétane')


# =========================================================================== #
# utils
# =========================================================================== #

def get_conf():
    ''' returns currently loaded config '''
    return _loaded_config

def get_conf_val(key):
    ''' returns a specific value from currently loaded config '''
    return _loaded_config[key]

def conf_fail(msg):
    ''' log msg + exit '''
    sys.stderr.write(msg + '\n')
    sys.exit(1)


# =========================================================================== #
# config file validation
# =========================================================================== #

def check_oauth(obj):
    ''' verifies credentials are OK '''
    for k in [ 'name', 'consumer_key', 'consumer_secret', 'access_token_key', 'access_token_secret' ]:
        if k not in obj or not obj[k]:
            conf_fail('> invalid oauth creds, missing "%s"' % k)


def check_source(obj):
    ''' verifies data source is OK '''
    for k in [ 'name', 'keywords' ]:
        if not obj.get(k, None):
            conf_fail('> invalid data source creds, missing "%s"' % k)

    if not len(obj['keywords']):
        conf_fail('> invalid data source creds, missing keyword(s)')


# =========================================================================== #
# main function, loads, validate & prepares the config
# =========================================================================== #

def load_conf(path=None):
    ''' finds, loads & checks conf file '''
    loaded_path = ''

    # already loaded?
    global _loaded_config
    if _loaded_config:
        return _loaded_config

    # check a few file pathes
    if path and os.path.isfile(path):
        loaded_path = path
        f = open(path, 'r')
    elif os.path.isfile('chétane.conf'):
        loaded_path = 'chétane.conf'
        f = open('chétane.conf', 'r')
    elif os.path.isfile('/etc/chétane/chétane.conf'):
        loaded_path = '/etc/chétane/chétane.conf'
        f = open('/etc/chétane/chétane.conf', 'r')
    else:
        conf_fail('> cant find conf file in "./chétane.conf" or "/etc/chétane/chétane.conf"\n')

    # load conf file
    try:
        conf = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(exc)
        conf_fail('> invalid conf file "%s"\n' % loaded_path)
    f.close()

    # check oauth credentials
    if not 'creds' in conf or len(conf['creds']) < 1:
        conf_fail('> "creds" section missing or empty')
        for c in conf['creds']:
            check_oauth(c)

    # check data sources
    if not 'sources' in conf or len(conf['sources']) < 1:
        conf_fail('> "sources" section missing or empty')
        for c in conf['sources']:
            check_source(c)

    # check other data from conf & set default values if needed
    conf.setdefault('loglevel',         'info')
    conf.setdefault('logfile',          None)
    conf.setdefault('datadir',          './data')
    conf.setdefault('datadir_raw',      './data-{daystr}/{source}.jsonl')
    conf.setdefault('source_report',    3600)
    conf.setdefault('source_stats',     5)
    conf.setdefault('path_web',         './web/')
    conf.setdefault('bind_addr',        '127.0.0.1')
    conf.setdefault('bind_port',        8080)

    if not os.path.isdir(conf['path_web']):
        conf_fail('> invalid path_web in config')

    # create data dir if needed
    if not os.path.isdir(conf['datadir']):
        os.makedirs(conf['datadir'], exist_ok=True)

    # setup logger
    set_logger(conf['loglevel'].upper(), conf['logfile'])

    # store global conf
    _loaded_config = conf

    logger.info('[config] > loaded config file from %s', loaded_path)
    return _loaded_config


# =========================================================================== #
# initialize application logger
# =========================================================================== #

def set_logger(level, path):
    ''' prepares the logger & sets up log level '''
    global logger

    logger = logging.getLogger('chétane')
    logger.setLevel(level.upper())

    # stderr / stdout logger
    ch = logging.StreamHandler()
    ch.setLevel(level.upper())
    fmt = logging.Formatter('%(levelname)s %(message)s')
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # file logger
    if path:
        fh = logging.FileHandler(path)
        fh.setLevel(level.upper())
        fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        fh.setFormatter(fmt)
        logger.addHandler(fh)


# =========================================================================== #
# getters for specific conf items
# =========================================================================== #
def conf_sources():
    ''' returns list of all sources '''
    if not _loaded_config:
        conf_fail('> no config file')
        return None

    return _loaded_config['sources']

def conf_source(name):
    ''' find a data source from conf '''
    if not _loaded_config:
        conf_fail('> unknown data source "%s"' % name)
        return None

    for ds in _loaded_config['sources']:
        if ds['name'] == name:
            return ds

    conf_fail('> unknown data source "%s"' % name)
    return None

def conf_source_groups():
    if not _loaded_config:
        conf_fail('> config not loaded')
        return []

    groups = [ ds.get('group', 'default') for ds in _loaded_config['sources'] ]
    return sorted(list(set(groups)))


def conf_creds(name):
    ''' find credentials with specified name in conf '''
    if not _loaded_config:
        conf_fail('> unknown credentials "%s"' % name)
        return None

    for ds in _loaded_config['creds']:
        if ds['name'] == name:
            return ds

    conf_fail('> unknown credentials "%s"' % name)
    return None


def default_creds(account=None):
    ''' returns default twitter credentials from our config file '''

    if account:
        # account specified from cmdline?
        c = conf_creds(account)
        if c:
            return c

    return _loaded_config['creds'][0]


# =========================================================================== #
# data source data storage paths
# =========================================================================== #

def source_path_raw(name, daystr=None):
    ''' returns path where raw tweets are stored for this source '''
    path = _loaded_config['datadir_raw'].format(
        datadir=_loaded_config['datadir'],
        source=name,
        daystr=daystr or datetime.datetime.now().strftime('%Y-%m-%d'),
    )
    if not os.path.isdir(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


