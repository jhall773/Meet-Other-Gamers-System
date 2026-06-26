'''
Username generation logic
'''
# Generate a random 15-character alphanumeric username
def generate_username():
    import random
    username = []
    name_size = 15
    for i in range(name_size):
        # random generation:
        import random

        ascii_ranges = [
            range(48, 57),    # 48-57 are digits 0-9 in Ascii
            range(65, 90),    # 65–90 are capital letters in Ascii
            range(97, 123)    # 97-123 are lowercase letters in Ascii
        ]

        # Pick a random range, then a random number from it
        ascii_range = random.choice(ascii_ranges)
        ascii_val = random.choice(list(ascii_range))
        char = chr(ascii_val)
        username.append(char)
    username = ''.join(username)
    print("New User: " + username)
    return username 

# Query Supabase:
'''
username = generate_username()
username_gen_sql = f"select username from users where username = '{username}';"
'''

# If username exists → regenerate again until you make one that doesn't
# while running username_gen_sql gives you a value not "None"...

# If not → Store it locally on the device just like you do everything else (where db = local SQLite DB)
# def load_username_from_db(self): -> Except YOU ONLY NEED TO LOAD THIS from local DB
# def save_username_to_db(self): -> Both to local DB and global DB
# Local:
'''
conn = sqlite3.connect(self.db_path)
df.to_sql("users", conn, if_exists="fail", index=False)
conn.close()
'''
# Global
username_insert_sql = "insert into users (username) values ('candidate');" # Run this with the proper supabase sql engine

