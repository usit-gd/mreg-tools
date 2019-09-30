import json
import logging
import os
import shutil
import subprocess
import sys

from functools import wraps
from time import time

# replace in python 3.7 with datetime.fromisoformat
from iso8601 import parse_date

logger = None


def error(msg, code=os.EX_UNAVAILABLE):
    logger.error(msg)
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def mkdir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError as e:
        error(f"{e}", code=e.errno)


def write_file(cfg, filename, f):
    dstfile = os.path.join(cfg['default']['destdir'], filename)
    encoding = cfg['default'].get('fileencoding', 'utf-8')

    # XXX: add difflib or ignore
    if os.path.isfile(dstfile):
        os.rename(dstfile, f"{dstfile}_old")
    with open(dstfile, 'w', encoding=encoding) as dest:
        f.seek(0)
        shutil.copyfileobj(f, dest)
    os.chmod(dstfile, 0o400)


def read_json_file(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, EOFError):
        logging.warning(f"Could read data from {filename}")
        return None


def write_json_file(filename, info):
    try:
        with open(filename, 'w') as f:
            return json.dump(info, f)
    except PermissionError:
        error(f"No permission to write to {filename}")


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        logging.info(f'func:{f.__name__} args:[{args}, {kw}] took: {te-ts:.4} sec')
        return result
    return wrap


@timing
def updated_entries(cfg, conn, url, filename, obj_filter='?page_size=1&ordering=-updated_at') -> bool:
    """Check if first entry is unchanged"""

    filename = os.path.join(cfg['default']['workdir'], filename)
    url += obj_filter
    new_data = conn.get(url).json()
    if new_data['count'] == 0:
        error(f"No entries at: {url}")
    old_data = read_json_file(filename)
    if old_data is None:
        write_json_file(filename, new_data)
        return True

    old_updated_at = parse_date(old_data['results'][0]['updated_at'])
    new_updated_at = parse_date(new_data['results'][0]['updated_at'])
    if old_data['count'] != new_data['count'] or \
       old_data['results'][0]['id'] != new_data['results'][0]['id'] or \
       old_updated_at < new_updated_at:
        write_json_file(filename, new_data)
        return True
    return False


@timing
def run_postcommand(cfg):
    command = json.loads(cfg['default']['postcommand'])
    subprocess.run(command)
