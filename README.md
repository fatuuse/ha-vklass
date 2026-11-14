# Vklass for Home Assistant (alpha)

An unofficial custom integration for [Vklass](https://www.vklass.se), the Swedish school platform.
It reads information from your parent account and creates sensors per child in Home Assistant.

> **Status: alpha.** Vklass has no public API. This integration reads the same web pages the
> Vklass website uses, so it can break whenever Vklass changes them. Use it for testing and
> give feedback, not for anything that must never fail.

## What it provides

Every child on the account gets a device. Entity names use the child's name.

| Entity | Type | Source |
| --- | --- | --- |
| Care today / Care tomorrow | sensor | Care schedule (times, closed, on leave) |
| Attendance | sensor | Welcome page |
| Next lesson | sensor | Calendar. Overlapping lessons are joined with ` \| ` |
| Lunch | sensor | Welcome page. State is today's lunch until 15:00, then tomorrow's. Attribute `days` has every day |
| Merit value | sensor | Grades page (grade school, see below) |
| Current grades | sensor | Grades page (grade school, see below) |
| Active courses / Course attendance | sensor | Study overview (grade school, see below) |
| Upcoming absences | sensor | Absence page (read only) |
| Gym today / Gym tomorrow | binary sensor | Calendar (lecture with code "IDH"; calendar events never count) |
| Holiday confirmation needed | binary sensor (problem) | Care schedule |
| Schedule | calendar | Calendar (lessons, events, assignments, plans, vacant days) |
| Absent now | binary sensor (presence) | Absence page (read only) |

Account level:

| Entity | Type |
| --- | --- |
| News (last 3 days) | sensor, with article titles and links as attributes |
| Unread messages | sensor |
| Notifications | sensor |

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

School ids are found automatically. If a child has more than one possible school id, open the
integration's **Configure** dialog and choose the right one. You can also type an id yourself, or
leave the field empty to keep the automatic choice. Children without a school id get no grades or
course data.

In the same dialog you can choose which calendar categories appear in the **Schedule** calendar. You can also hide all-day events that span several days, such as whole terms or plans.

Children are found on the Vklass welcome page. A child that is referenced there but has no card
gets the placeholder name `Student <id>` until its card can be read.

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

These are examples for automations in Home Assistant. They are not part of the integration, so copy
them and change them as you like. The entity ids depend on the language Home Assistant used when the
entities were created. Check them under **Settings → Devices & services → Entities** and replace them
if yours differ.

### Unread messages or notifications

Notifies you when Vklass has unread messages or notifications. Tapping the notification opens Vklass.

```yaml
alias: Vklass - unread messages
trigger:
  - platform: numeric_state
    entity_id: sensor.vklass_unread_messages
    above: 0
  - platform: numeric_state
    entity_id: sensor.vklass_notifications
    above: 0
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Vklass"
      message: "You have unread messages or notifications in Vklass."
      data:
        clickAction: "https://custodian.vklass.se"
mode: queued
```

### New news article

Notifies you when a new article appears, and opens the article when you tap the notification. The
news sensor's state is the number of articles, and its newest article is the first one in `articles`.

```yaml
alias: Vklass - new news
trigger:
  - platform: state
    entity_id: sensor.vklass_news_last_3_days
condition:
  - condition: template
    value_template: >-
      {{ trigger.to_state.state | int(0) > trigger.from_state.state | int(0) }}
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "New in Vklass"
      message: "{{ state_attr('sensor.vklass_news_last_3_days', 'articles')[0].title }}"
      data:
        clickAction: "{{ state_attr('sensor.vklass_news_last_3_days', 'articles')[0].url }}"
mode: queued
```

### Evening reminder: gym clothes for tomorrow

At 19:00, lists every child who has gym tomorrow, and reminds you to pack gym clothes. Nothing is sent
on evenings when no child has gym.

```yaml
alias: Vklass - gym clothes tomorrow
trigger:
  - platform: time
    at: "19:00:00"
variables:
  children_with_gym: >-
    {{ states.binary_sensor
       | selectattr('entity_id', 'search', 'gympa_imorgon|gym_tomorrow')
       | selectattr('state', 'eq', 'on')
       | map(attribute='name')
       | map('replace', ' Gympa imorgon', '')
       | map('replace', ' Gym tomorrow', '')
       | list }}
condition:
  - condition: template
    value_template: "{{ children_with_gym | length > 0 }}"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Gym tomorrow"
      message: >-
        Pack gym clothes for: {{ children_with_gym | join(', ') }}.
mode: single
```

Replace `notify.mobile_app_your_phone` with your own notify service. You can find it under
**Developer tools → Actions** by searching for `notify.mobile`.

## Known limitations

- **School ids are discovered from Vklass responses.** If Vklass does not return one, the grades and
  course sensors stay empty for that child until you enter the id yourself.
- **Absence reporting uses the website form.** If Vklass changes the form, the button stops working and shows an error.
- **Parsing depends on Vklass markup.** Scraping can break silently after a Vklass update. Check the
  logs and the diagnostics after an update.
- **Overlap detection is simple.** Two lessons count as overlapping when their times overlap with the
  next lesson. Chains of overlaps are not followed.
- **Scoreboard names are a guess.** The fields `messages` and `notifications` are based on the
  response keys only. If the counts do not match what you see in Vklass, please report it.
- **No Swedish or English translation review.** Texts were written by hand and need proofreading.
- **Only pages that show children on the welcome page are found.** A child that is not referenced
  on the welcome page at all is not discovered.

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

## Development

Parsers and summary functions can be tested without Home Assistant:

```bash
pip install requests
python3 tests/test_parsers.py
```

The tests use invented data only. Please keep it that way in pull requests: no real names,
student ids, school ids or calendar links in code, tests, fixtures or documentation.

Layout:

- `custom_components/vklass/api.py` - HTTP client and page parsers (no Home Assistant imports)
- `custom_components/vklass/summaries.py` - pure summary functions (no Home Assistant imports)
- `custom_components/vklass/coordinator.py` - polling and data assembly
- `custom_components/vklass/sensor.py`, `binary_sensor.py`, `entity.py` - entities
- `custom_components/vklass/config_flow.py` - config and options flow
- `custom_components/vklass/diagnostics.py` - safe diagnostics

## Disclaimer

This project is not affiliated with, endorsed by or supported by Vklass. Use it at your own risk.
