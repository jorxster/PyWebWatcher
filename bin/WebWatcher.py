#!/usr/bin/env python3
"""
Website Watcher script for comparing diffs and emailing.

Dependencies:
- wget
"""
__author__ = 'jorxster@gmail.com'
__date__ = '24 Sep 2020'
__version__ = "0.5.0"

import datetime, re, hashlib, os, shutil, sys, subprocess, time, yaml
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import wget

THIS_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(THIS_PATH, 'config', 'config.yaml')
CONFIG = yaml.load(open(config_path), Loader=yaml.Loader)
PATH = os.path.expandvars(CONFIG.get('path'))

# A regex for simplifying supplied domain.
REGEX_DOMAIN = '(http[s]?://)?(www\.)?(\w+)(/?.*)'
# re.search('REGEX_DOMAIN, 'http://www.zerohedge.ccom/blah?trusted="True"%020%')
# ('http://', 'www.', 'zerohedge', '.ccom/blah?trusted="True"%020%')


def send_email(url, diff):
    """
    Given a url and diff, format, connect, and send email.
    """
    tokens = tokens_from_url(url)

    gmail_user = CONFIG.get('google').get('email')
    gmail_password = CONFIG.get('google').get('password')

    if not gmail_user or not gmail_password:
        raise RuntimeError('Either email or password not defined')

    msg = MIMEMultipart()

    sent_from = gmail_user
    to = gmail_user
    subject = 'URL Updated : {}'.format(tokens['domain'])

    body = """\
    Regarding URL {} \n
    DIFF \n
    {}
    """.format(url, diff)

    # setup the parameters of the message
    msg['From'] = sent_from
    msg['To'] = to
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    print('\n')
    print(msg.as_string())

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(gmail_user, gmail_password)
    server.sendmail(sent_from, to, msg.as_string())
    server.quit()

    print('Email sent!')


def get_last_download(url):
    """
    Given URL, get last available dated cache download folder in config directory.
    """
    tokens = tokens_from_url(url)

    old_dir = os.path.join(PATH, tokens['domain'])
    # ensure unique subdir
    old_dir += '_{}'.format(tokens['hash'])

    if not os.path.exists(old_dir):
        print('No comparison directories exist! Aborting : {}'.format(old_dir))
        return

    all_subdirs = [os.path.join(old_dir, d) for d in os.listdir(old_dir) if os.path.isdir(os.path.join(old_dir, d))]
    if not all_subdirs:
        return

    latest_subdir = max(all_subdirs, key=os.path.getmtime)

    return os.path.join(latest_subdir, tokens['domain'])


def delete_dir(last_path):
    """
    Remove the given path recursively.
    """
    par_dir = os.path.dirname(last_path)
    print(f'Removing old directory and contents : {par_dir}')
    return shutil.rmtree(par_dir)


def make_dir(url):
    """
    Make dated subdirectory for storing URL download.
    """
    tokens = tokens_from_url(url)

    new_dir = os.path.join(PATH, tokens['domain'])
    # ensure unique subdir
    new_dir += '_{}'.format(tokens['hash'])

    # date sub-subsdir
    dt = datetime.datetime.fromtimestamp(time.time())
    # '2020-09-26-0937/'
    new_dir += '/{}'.format(dt.strftime('%Y-%m-%d-%H%M'))

    if not os.path.exists(new_dir):
        print('MAKING DIR : {}'.format(new_dir))
        os.makedirs(new_dir)

    filename = os.path.join(new_dir, tokens['domain'])
    return filename


def tokens_from_url(url):
    """
    Given a URL, construct and return a dict containing tokens for that url. A hash, the domain simplified, and the
    original URL.
    """
    hash = hashlib.md5(url.encode('ascii')).hexdigest()[:16]

    srch = re.search(REGEX_DOMAIN, url)

    return {
        'hash': hash,
        'domain': srch[3],
        'url': url,
    }


def download(url, dest_path):
    """
    Given URL and the destination download directoryr, download into that destination filename path.
    """
    wget.download(url, out=dest_path)


def get_diff(old, new):
    """
    Given two files, diff them and return the stdout from `diff`
    """
    print('Diff-ing {} vs {}'.format(old, new))
    out = subprocess.getoutput(f'diff {old} {new}')
    print('DIFF = \n')
    print(out)
    return out


def main():
    """
    Get config path, regex URL to get folder dir + hash to ensure unique per sub-url.

    Make sub-dir with time (down to min?)

    Wget into current time subdir.

    ---

    Diff with last time.

    If diff, send email.

    Delete last time folder (optional)
    """
    if len(sys.argv) < 2:
        print('Usage: Provide a URL as an argument')
        return

    url = sys.argv[1]
    print(url)

    last_path = get_last_download(url)
    if last_path:
        print('Last path found')

    dest_path = make_dir(url)
    download(url, dest_path)

    if not last_path:
        print('Aborting as no comparison available, downloading only')
        return

    diff = get_diff(last_path, dest_path)
    if not diff:
        print('No diff found, returning')
        delete_dir(last_path)
        return

    try:
        send_email(url, diff)
    except Exception:
        delete_dir(dest_path)
        raise

    delete_dir(last_path)


if __name__ == '__main__':
    main()