import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from scholarly import scholarly
from fuzzywuzzy import process
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

# Domain verification
def verify_domain(domain: str) -> (bool, str):
    url = domain if re.match(r'https?://', domain) else f'https://{domain}'
    try:
        resp = requests.get(url, timeout=5)
        if resp.ok:
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else url
            return True, title
    except Exception:
        pass
    return False, None

# Fetch author profile by name + affiliation filter

def fetch_author_data(name: str, affiliation: str = None) -> dict:
    candidates = list(scholarly.search_author(name))
    if not candidates:
        return {'name': name, 'affiliation': affiliation, 'total_citations': None,
                'h_index': None, 'i10_index': None, 'publications': None}

    # select best match by affiliation if provided
    if affiliation:
        affs = [c.get('affiliation', '') if isinstance(c, dict) else getattr(c, 'affiliation', '')
                for c in candidates]
        best_aff, _ = process.extractOne(affiliation, affs)
        idx = affs.index(best_aff)
        candidate = candidates[idx]
    else:
        candidate = candidates[0]

    author = scholarly.fill(candidate)

    # support dict or object
    def get_attr(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    data = {
        'name': get_attr(author, 'name'),
        'affiliation': get_attr(author, 'affiliation'),
        'total_citations': get_attr(author, 'citedby'),
        'h_index': get_attr(author, 'hindex'),
        'i10_index': get_attr(author, 'i10index'),
        'publications': len(get_attr(author, 'publications') or [])
    }
    return data

# Scheduler for automated runs
def schedule_updates(func, interval_minutes: int):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func, 'interval', minutes=interval_minutes)
    scheduler.start()

# Email notification
def send_email(subject: str, body: str, to: str):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_USER')
    msg['To'] = to
    msg.set_content(body)

    with smtplib.SMTP_SSL(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.send_message(msg)