# Vklass for Home Assistant (alpha)

An unofficial custom integration for [Vklass](https://www.vklass.se), the Swedish school platform.
It reads information from your parent account and creates sensors per child in Home Assistant.

> **Status: alpha.** Vklass has no public API. This integration reads the same web pages the
> Vklass website uses, so it can break whenever Vklass changes them. Use it for testing and
> give feedback, not for anything that must never fail.

## What it provides

Per child: care times and a weekly care list, attendance, next lesson, lunch, grades, course judgements,
upcoming absences, idrott days and a calendar. For the account: news, unread messages and notifications.
Absences can be reported for today with a button, which is disabled by default.

## Installation

### HACS (custom repository)

1. In HACS, open the menu and choose **Custom repositories**.
2. Add the repository URL and select category **Integration**.
3. Install **Vklass** and restart Home Assistant.

### Manual

Copy `custom_components/vklass` into your Home Assistant `config/custom_components/` folder and restart.

## Setup

The settings below are shown during setup, and can be changed later under **Configure**.

### Choose how to log in

- **Session cookie (recommended).** Works with BankID and other login methods. Log in to Vklass in your
  browser, copy the value of the cookie named `se.vklass.authentication`, and paste it into the setup.
  The cookie can expire. Then Home Assistant asks you for a new one.
- **Username and password.** Stored in Home Assistant's configuration. Use this only if you cannot
  use a cookie.

Either way, the secret is stored in plain text in Home Assistant's configuration storage.

1. Go to **Settings → Devices & services → Add integration** and search for **Vklass**.
2. Enter the username and password for your Vklass parent account. The login is checked before saving.

In the same dialog you can choose which calendar categories appear in the **Schedule** calendar. You can also hide all-day events that span several days, such as whole terms or plans.

Children are found on the Vklass welcome page. A child that is referenced there but has no card
gets the placeholder name `Student <id>` until its card can be read.

## Refresh schedule

- **Full refresh:** every 8 hours.
- **Attendance and care times:** every 15 minutes on weekdays from 07:00 to 09:30 and from 15:00 to 17:00, so you
  can see whether a child has arrived or been picked up.
- **Keepalive:** every 10 minutes. It only keeps the session alive.
- **Next lesson** is recalculated 10 minutes after each lesson starts, and just after it ends.
- **Other clock-dependent values** such as today, the lunch switch at 15:00 and the week shown from Saturday are
  recalculated once an hour from stored data. Vklass is not called for this.
- **Update entity:** `homeassistant.update_entity` on any Vklass entity starts a full refresh now.

## Keeping the session alive

The integration requests the Vklass scoreboard every 10 minutes. This keeps the session active, so a
session cookie is not lost from inactivity. If Vklass rotates the cookie, the new value is saved
automatically. If the session expires anyway, Home Assistant asks you to log in again.

## Entities disabled by default

When an entity is first created, it is disabled if it cannot have data for that child. Examples are
attendance and care times for a child without care. Enable them in Home Assistant if you need them. The rules only apply to new
entities, so existing entities keep their state.

## Reporting an absence

Each child has a button, **Report absence today**. Pressing it reports an absence from the current
time until 23:59 the same day.

- The button is **disabled by default**. Enable it in the entity settings before you use it.
- It does nothing if an absence already covers the current time.
- After reporting, the integration checks that Vklass shows the new absence. If it does not,
  Home Assistant shows an error, so you can check Vklass yourself.
- Check the result in Vklass the first time you use it. Reports go straight to the school.
- A report made from a time after the school's cut-off is rejected by Vklass, and the button shows an error.

## Suggested notifications

Three example automations are in `examples/`, ready to copy into Home Assistant:

- `notify_unread_messages.yaml`: unread messages or notifications, opens Vklass when tapped.
- `notify_new_news.yaml`: a new news article, opens the article when tapped.
- `notify_idrott_tomorrow.yaml`: at 19:00, reminds you which children have idrott tomorrow.

Change the notify service in each file to your own. They are examples, not part of the integration.
See also `examples/automation_news_to_calendar.yaml` for AI proposals of calendar events.

## Privacy and security

- Your username and password are stored in Home Assistant's configuration storage in plain text,
  like other integrations that log in with a password. Use a strong password and keep your
  Home Assistant instance secure.
- Some Vklass pages contain links that give access to a calendar without logging in. Do not share
  these links, and do not paste them into issues, screenshots or chats. If one was shared, revoke
  it in Vklass.
- The diagnostics download redacts credentials and contains no child names or ids. Check the file
  before you attach it to an issue.

## Reporting problems

Open an issue with:

1. The Home Assistant version and the integration version (see the manifest).
2. What you expected and what happened.
3. The relevant log lines (search for `vklass`), with names and ids removed.
4. The diagnostics file, downloaded from the integration's page.

## Disclaimer

This project is not affiliated with, endorsed by or supported by Vklass. Use it at your own risk.
