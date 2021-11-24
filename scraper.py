#!/usr/bin/env python3

import asyncio
import json
import sys

from pathlib import Path
from utils import NestedNamespace

from pyppeteer import launch

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, \
    TrackingSettings, ClickTracking, OpenTracking

root = Path(__file__).parent.absolute()

project_url = 'https://github.com/abjugard/SiteScraper'
project_promo_text = 'Generated using abjugard/SiteScraper!'
project_footer = f'\n<br>\n<a href="{project_url}">{project_promo_text}</a>'

browser = None


def load_config():
  conf_path = root / 'config.json'
  with conf_path.open(encoding='utf-8') as conf_f:
    conf = json.load(conf_f)

  return NestedNamespace(conf)


async def get_text(target):
  page = await browser.newPage()
  await page.goto(target.url)

  button = await page.querySelector(target.selector)
  text = await page.evaluate('(element) => element.textContent', button)

  return text.strip()


async def get_state(target):
  text = await get_text(target)
  outcome = text.lower() == target.positive_text.lower()
  return outcome


def state_changed(url, new_state):
  state_db_path = root / 'last_state.json'

  if state_db_path.is_file():
    with state_db_path.open(encoding='utf-8') as state_f:
      state_db = json.load(state_f)
  else:
    state_db = {}

  is_first_check = url not in state_db
  last_state = new_state if is_first_check else state_db[url]
  state_db[url] = new_state

  with state_db_path.open(mode='w', encoding='utf-8') as state_f:
    json.dump(state_db, state_f, ensure_ascii=False, indent=2)

  return (last_state is not new_state, is_first_check)


def get_mail_data(target, positive_outcome):
  modifier = 'is' if positive_outcome else 'is not'
  topic = target.topic.format(modifier)

  if positive_outcome:
    return (topic + '!', (
        f'<h1>It {modifier} time, the {topic}! 🎉</h1>\n'
        f'<h2><a href="{target.url}">Go go go! 🏎💨</a></h2>'))
  else:
    return (topic, (
        f'<h1>It {modifier} time!</h1>\n'
        f"<h2>The {target.topic.format('is no longer')}. 😞<h2>"))


def send_mail(to_emails, subject, html_content):
  message = Mail(
      from_email=config.sendgrid.sender,
      to_emails=to_emails,
      subject=subject,
      html_content=html_content + project_footer)
  message.tracking_settings = TrackingSettings(
      ClickTracking(False, False),
      OpenTracking(False))
  try:
    sg = SendGridAPIClient(config.sendgrid.api_key)
    response = sg.send(message)
    print(response.status_code)
    print(response.body)
    print(response.headers)
  except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)


def inform_subscribers(target, positive_outcome):
  subject, html_content = get_mail_data(target, positive_outcome)
  send_mail(target.subscribers, subject, html_content)


async def main():
  global browser
  browser = await launch(headless=True)
  for target in config.targets:
    try:
      outcome = await get_state(target)
      state_differs, is_first_check = state_changed(target.url, outcome)
      log_message, _ = get_mail_data(target, outcome)
      print(log_message)
      if state_differs or (outcome and is_first_check):
        inform_subscribers(target, outcome)
    except Exception as e:
      subject = f'Error occurred for target: {target.url}'
      print(f'{subject} ({str(e)})', file=sys.stderr)
      conf_json = json.dumps(target.to_dict(), ensure_ascii=False, indent=2)
      body = (
          f'<h1>{subject}</h1>\n'
          f'<pre><code>Error: {str(e)}</code></pre>\n'
          f'<pre><code>{conf_json}</code></pre>')
      send_mail([config.admin_email], subject, body)
  await browser.close()


if __name__ == '__main__':
  config = load_config()

  asyncio.get_event_loop().run_until_complete(main())
