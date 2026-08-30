from datetime import datetime
from zoneinfo import ZoneInfo

# Engine For online DB
from supabase import create_client
from dotenv import load_dotenv
import os

# Retrieve API key from environment variables
def get_supabase():
    load_dotenv()
    key = os.getenv("MEET_GAMERS_API_KEY")
    url = os.getenv("MEET_GAMERS_URL")
    return create_client(url, key)

supabase_engine = get_supabase()

# Copied Usernames in Online DB for Testing
username = "S4TVfwp6NCn7jh8"
username2 = "7GxT6a0Fe5WMUU1"

# Note: message_view is a VIEW created by the SQL statement "Creating 'Message' View" in the supabase SQL Editor.
def send_message(username, recipient, msg):

    # Central Time Zone from IANA tz database
    central_tz = ZoneInfo("America/Chicago")
    database_time = datetime.now(central_tz)

    # Send message to online DB for other recipient user to view:
    supabase_engine.table("messages").insert(
                                             {"sender": username, 
                                              "recipient": recipient,
                                              "message": msg,
                                              "time": database_time.isoformat()}).execute()