#!/usr/bin/env python3

import json
import sys
import asyncio

from pathlib import Path
from utils import NestedNamespace

from pyppeteer import launch

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, \
    TrackingSettings, ClickTracking, OpenTracking

root = Path(__file__).parent.absolute()


def load_config():
  conf_path = root / 'config.json'
  with conf_path.open(encoding='utf-8') as conf_f:
    conf = json.load(conf_f)

  return NestedNamespace(conf)


async def get_text(target):
  browser = await launch(headless=True)
  page = await browser.newPage()
  await page.goto(target.url)

  button = await page.querySelector(target.selector)
  text = await page.evaluate('(element) => element.textContent', button)
  await browser.close()

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
    return (topic + '!', f"""
<h1>It {modifier} time, the {topic}! 🎉</h1>
<h2><a href="{target.url}">Go go go! 🏎💨</a><h2>
    """)

  return (topic, f"""
<h1>It {modifier} time!</h1>
<h2>The {target.topic.format('is no longer')}. 😞<h2>
    """)


def send_mail(target, positive_outcome):
  subject, html_content = get_mail_data(target, positive_outcome)
  footer = '\n<a href="https://github.com/abjugard/SiteScraper">' \
      + 'Generated using abjugard/SiteScraper!</a>'

  message = Mail(
      from_email=config.sendgrid.sender,
      to_emails=target.subscribers,
      subject=subject,
      html_content=html_content + footer)
  message.tracking_settings = TrackingSettings(
      ClickTracking(False, False),
      OpenTracking(False))
  try:
    sg = SendGridAPIClient(config.sendgrid.api_key)
    sg.send(message)
  except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)


async def main():
  for target in config.targets:
    outcome = await get_state(target)
    state_differs, is_first_check = state_changed(target.url, outcome)
    log_message, _ = get_mail_data(target, outcome)
    print(log_message)
    if state_differs or (outcome and is_first_check):
      send_mail(target, outcome)


if __name__ == '__main__':
  config = load_config()

  asyncio.get_event_loop().run_until_complete(main())
