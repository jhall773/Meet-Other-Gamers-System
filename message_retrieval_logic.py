from datetime import datetime

# Engine For online DB
from supabase import create_client
from dotenv import load_dotenv
import os

# Retrieve API key from environment variables
load_dotenv()
key = os.getenv("MEET_GAMERS_API_KEY")
url = os.getenv("MEET_GAMERS_URL")
supabase_engine = create_client(url, key)

# Copied Usernames in Online DB for Testing
username = "S4TVfwp6NCn7jh8"
username2 = "7GxT6a0Fe5WMUU1"

# ------------------------- Retrieve Sent Msgs --------------------------------
# Note: message_view is a VIEW created by the SQL statement "Creating 'Message' View" in the supabase SQL Editor.
def retrieve_sent_msgs(username):
    result = (
        supabase_engine
        .table("message_view")
        .select("*")
        .eq(column="sender", value=username)
        .execute()
    )

    # Form the recipient list
    recipient_list = set()
    for row in result.data:
        recipient_list.add(row["recipient"])

    # Retrieve Message Data from the SQL results
    row_num = 0
    sent_msgs = {recip:[] for recip in recipient_list}
    for recip in recipient_list:
        while row_num < len(result.data) and result.data[row_num]["recipient"] == recip:
            # From the timestamptz string returned from supabase, create a datetime object
            # Example of supabase timestamptz string: "2026-08-04T15:30:00.000Z"
            time = datetime.fromisoformat(result.data[row_num]["time"].replace("Z", "+00:00"))
            sent_msgs[recip].append(
                ['sent', result.data[row_num]["message"], time]
                )
            row_num += 1
        row_num += 1

    return sent_msgs, recipient_list 
sent_messages, recipient_list = retrieve_sent_msgs(username)
print(sent_messages)
print()
# ------------------------- Retrieve Sent Msgs --------------------------------


# ------------------------- Retrieve Recieved Msgs ----------------------------
def retrieve_recv_msgs(username):
    result = (
        supabase_engine
        .table("message_view")
        .select("*")
        .eq(column="recipient", value=username)
        .execute()
    )

    # Form the sender list
    sender_list = set()
    for row in result.data:
        sender_list.add(row["sender"])

    # Retrieve Message Data from the SQL results
    row_num = 0
    recv_msgs = {sender:[] for sender in sender_list}
    for sender in sender_list:
        while row_num < len(result.data) and result.data[row_num]["sender"] == sender:
            # From the timestamptz string returned from supabase, create a datetime object
            # Example of supabase timestamptz string: "2026-08-04T15:30:00.000Z"
            time = datetime.fromisoformat(result.data[row_num]["time"].replace("Z", "+00:00"))
            recv_msgs[sender].append(
                ['recieved', result.data[row_num]["message"], time]
                )
            row_num += 1
        row_num += 1

    return recv_msgs, sender_list 
recieved_messages, sender_list = retrieve_recv_msgs(username)
print(recieved_messages)
print()
# ------------------------- Retrieve Recieved Msgs ----------------------------


# ------------------------- Return Conversations ------------------------------
def generate_conversations(username):
    sent_messages, recipient_list = retrieve_sent_msgs(username)
    recieved_messages, sender_list = retrieve_recv_msgs(username)
    # Conversations = Combined sent_msgs (messages to) + recv_msgs (messages from) for the same username.
    combined_user_list = recipient_list.union(sender_list)
    Conversations = {user: [] for user in combined_user_list}

    for user in Conversations.keys():
        combined_msgs = sent_messages[user].copy()
        combined_msgs.extend(recieved_messages[user])
        Conversations[user]  = combined_msgs
        # Sort by timestamp
        Conversations[user].sort(key=lambda x: datetime.strptime(str(x[2]), "%Y-%m-%d %H:%M:%S.%f%z"), reverse=True)

    return Conversations
# ------------------------- Return Conversations ------------------------------
print(generate_conversations(username))