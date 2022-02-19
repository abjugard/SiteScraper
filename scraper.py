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
  response = await page.goto(target.url)
  if not response.ok:
    if response.status != 404:
      raise Exception(f'unexpected status {response.status}')
    return (None, response.status)

  element = await page.querySelector(target.selector)
  text = await page.evaluate('(element) => element.textContent', element)

  return (text.strip(), response.status)


async def get_state(target):
  text, status_code = await get_text(target)
  if text is None:
    return (None, status_code)
  outcome = text.lower() == target.positive_text.lower()
  return (outcome, status_code)


def state_changed(url, new_state):
  state_db_path = root / 'last_state.json'

  if state_db_path.is_file():
    with state_db_path.open(encoding='utf-8') as state_f:
      state_db = json.load(state_f)
  else:
    state_db = {}

  first_check = url not in state_db
  last_state = new_state if first_check else state_db[url]
  state_db[url] = new_state

  with state_db_path.open(mode='w', encoding='utf-8') as state_f:
    json.dump(state_db, state_f, ensure_ascii=False, indent=2)

  return (new_state != last_state, first_check)


def get_mail_data(target, outcome, status_code):
  modifier = 'is' if outcome else 'is not'
  topic = target.topic.format(modifier)
  if outcome is None:
    topic += f' ({status_code})'

  if outcome:
    return (topic + '!', (
        f'<h1>It {modifier} time, the {topic}! 🎉</h1>\n'
        f'<h2><a href="{target.url}">Go go go! 🏎💨</a></h2>'))
  else:
    return (topic, (
        f'<h1>It {modifier} time!</h1>\n'
        f"<h2>The {target.topic.format('is no longer')}. 😞</h2>"))


def send_mail(recipients, subject, html_content):
  message = Mail(
      from_email=config.sendgrid.sender,
      to_emails=config.sendgrid.sender,
      subject=subject,
      html_content=html_content + project_footer)
  message.bcc = recipients
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


def inform_subscribers(target, outcome, status_code):
  subject, html_content = get_mail_data(target, outcome, status_code)
  recipients = config.admin_email if outcome is None else target.subscribers
  send_mail(recipients, subject, html_content)


async def main():
  global browser
  browser = await launch(headless=True, executablePath=config.browser)
  for target in config.targets:
    if target.disabled:
      print('skipping disabled target:', target.url)
      continue
    try:
      outcome, status_code = await get_state(target)

      state = status_code if outcome is None else outcome
      changed, first_check = state_changed(target.url, state)

      log_message, _ = get_mail_data(target, outcome, status_code)
      print(log_message)
      if changed or (outcome and first_check):
        inform_subscribers(target, outcome, status_code)
    except Exception as e:
      subject = f'Error occurred for target: {target.url}'
      print(f'{subject} ({str(e)})', file=sys.stderr)
      conf_json = json.dumps(target.to_dict(), ensure_ascii=False, indent=2)
      body = (
          f'<h1>{subject}</h1>\n'
          f'<pre><code>Error: {str(e)}</code></pre>\n'
          f'<pre><code>{conf_json}</code></pre>')
      try:
        send_mail([config.admin_email], subject, body)
      except Exception as e_mail:
        browser.close()
        raise e_mail
  await browser.close()


if __name__ == '__main__':
  config = load_config()

  asyncio.new_event_loop().run_until_complete(main())
