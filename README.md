# Site scraper

A scraper which loads the `target.url` in a headless browser,
compares the text of an element selected using a `target.selector`
to the value specified by `target.positive_text`.

When a positive outcome is observed for a certain `target`, an email will 
be sent to the `target.subscribers`. Succeeding runs will send an email only 
if the result differs from the run before it.

## Requirements
* Python 3.9 with pip
* A SendGrid account
* Chromium (technically only the static libraries it depends on)

## Running
Copy `config.json.example` to `config.json` and populate the values in it.
Copy and modify `SiteScraper.service.example` to `SiteScraper.service` and 
hardlink it to your systemd unit library. Copy and modify 
`SiteScraper.timer.example` to `SiteScraper.timer` and hardlink it to your 
systemd unit library. 

Run `pip3 install -r requirements.txt` to install dependencies

Run `systemctl enable --now SiteScraper.timer`