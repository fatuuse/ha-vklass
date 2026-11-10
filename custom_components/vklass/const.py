"""Constants for the Vklass integration."""
from datetime import timedelta

DOMAIN = "vklass"

LOGIN_PAGE = "https://auth.vklass.se/credentials"
LOGIN_SIGNIN = f"{LOGIN_PAGE}/signin"
BASE_URL = "https://custodian.vklass.se"
HOME_URL = f"{BASE_URL}/Home/Welcome"
NEWS_URL = f"{BASE_URL}/Home/News/"
CALENDAR_URL = f"{BASE_URL}/Events/FullCalendar"
CARE_URL = f"{BASE_URL}/CareSchedule/Overview/"
SCOREBOARD_URL = f"{BASE_URL}/Account/Scoreboard"
ABSENCE_URL = f"{BASE_URL}/Absence/Notify/"

UPDATE_INTERVAL = timedelta(minutes=30)
CALENDAR_DAYS = 7
REQUEST_TIMEOUT = 20
GYM_KEYWORD = "idh"
LESSON_EVENT_TYPE = 1
NEWS_DAYS = 3

# Options key: {"<student id>": <elementary school id>}
OPTION_SCHOOL_IDS = "school_ids"

# Calendar categories, derived from the CSS class Vklass puts on each event.
CATEGORY_BY_CLASS = {
    "vk-cl-event-lecture": "lecture",
    "vk-cl-event-assignment": "assignment",
    "vk-cl-event-event": "event",
    "vk-cl-event-plan": "plan",
    "vk-cl-event-vacantday": "vacantday",
}
CATEGORY_BY_EVENT_TYPE = {1: "lecture", 2: "assignment", 4: "event", 16: "plan"}
CALENDAR_CATEGORIES = ("lecture", "event", "assignment", "plan", "vacantday", "other")

# Event type 4 (calendar event) is treated as a lesson, but never as gym.
LESSON_CATEGORIES = ("lecture", "event")
GYM_CATEGORY = "lecture"
SESSION_SEPARATOR = " | "

OPTION_CALENDAR_CATEGORIES = "calendar_categories"

# Config entry data keys. Same strings as Home Assistant's CONF_USERNAME and CONF_PASSWORD.
DATA_USERNAME = "username"
DATA_PASSWORD = "password"
DATA_COOKIE = "cookie"
CONF_AUTH_METHOD = "auth_method"

AUTH_PASSWORD = "password"
AUTH_COOKIE = "cookie"

# The Vklass session cookie. It is set on the parent domain so every Vklass host receives it.
COOKIE_NAME = "se.vklass.authentication"
COOKIE_DOMAIN = ".vklass.se"

# Keepalive: a request to the scoreboard every 10 minutes keeps the Vklass session alive.
KEEPALIVE_INTERVAL = timedelta(minutes=10)

# Hide all-day events that span several days (for example a term or a plan) from the calendar.
OPTION_HIDE_MULTIDAY_ALLDAY = "hide_multiday_all_day"
