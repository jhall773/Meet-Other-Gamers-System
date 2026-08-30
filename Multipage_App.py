import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from geopy.distance import geodesic
import pandas as pd
import sqlite3

# Functions for Building Conversations and Messages from other files
from message_send_logic import send_message
from message_retrieval_logic import generate_conversations

# Engine For online DB
from supabase import create_client
from dotenv import load_dotenv
import sys, os
from resource_path import resource_path
load_dotenv()
key = os.getenv("MEET_GAMERS_API_KEY")
url = os.getenv("MEET_GAMERS_URL")
supabase_engine = create_client(url, key)

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Multipage Selection + Ranking Demo")
        self.geometry("800x600")

        # Share Username on Start Page
        self.username = ""

        # Shared state across pages
        self.selected_games = []

        # Shared age across pages
        self.age = "N/A"

        # Shared ZIP + State across pages
        self.user_zip = None
        self.user_state = None

        # Shared rankings accross pages
        self.rankings = {}

        # Load previous rankings if database exists
        self.db_path = "rankings.db"
        self.load_rankings_from_db()

        # Load all US ZIP codes if user needs to find their ZIP
        self.zip_db_path = resource_path("US_zip_codes.db")

        # Container that holds all pages
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        # Dictionary to store page instances
        self.frames = {}

        # Initialize all pages
        for Page in (StartPage, PageTwo, PageThree, PageFour, PageFive,
                     PageSix, PageSeven, PageEight):
            page_name = Page.__name__
            if Page is PageEight:
                frame = Page(parent=container,
                            controller=self,
                            Conversations=generate_conversations(self.username),
                            send_message_func=send_message)
            else:
                frame = Page(parent=container, controller=self)

            self.frames[page_name] = frame

            # Stack all pages in the same location
            frame.grid(row=0, column=0, sticky="nsew")

        # Show the first page
        self.show_frame("StartPage")

    def show_frame(self, page_name):
        """Bring a frame to the front"""
        frame = self.frames[page_name]

        # Page Refreshers updating information.

        # If going to StartPage (Main Menu), refresh so it properly shows saved age
        if page_name == "StartPage":
            frame.refresh_age()

        # If going to PageSeven, refresh so it properly shows saved zipcode & state
        if page_name == "PageSeven":
            frame.refresh_required_data() # refresh and check for needed data to render page properly.

        frame.tkraise()

    # ------------------------------------------------------------------------------
    # 🔥 Load all US ZIP codes from US_zip_codes.db
    # ------------------------------------------------------------------------------
    def load_all_zips(self):
        conn = sqlite3.connect(self.zip_db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT zcta5_code FROM zipcodes")
        zips = [row[0] for row in cur.fetchall()]
        conn.close()
        return sorted(zips)

    # ------------------------------------------------------------------------------
    # 🔥 Save rankings to SQLite using pandas and to online DB with supabase engine
    # ------------------------------------------------------------------------------
    def save_rankings_to_db(self):
        if not self.rankings:
            return

        df = pd.DataFrame(
            [(game, rank) for game, rank in self.rankings.items()],
            columns=["game", "rank"]
        )

        conn = sqlite3.connect(self.db_path)
        df.to_sql("rankings", conn, if_exists="replace", index=False)
        conn.close()

        # Save to online DB:
        rows = df.to_dict(orient="records")

        for row in rows:
            row["username"] = self.load_username_from_db()

        supabase_engine.table("rankings").upsert(rows).execute()

    # -----------------------------------------------------------------------------------------------
    # 🔥 Save username to SQLite using pandas and to online DB with supabase engine
    # -----------------------------------------------------------------------------------------------
    def save_username_to_db(self):
        from Username_generation_logic import generate_username

        # Query Supabase:
        self.username = generate_username()

        # online_username_sql = f"select username from users where username = '{username}';"
        # supabase sql results are APIResponse objects with attributes data = [] and count = 0 or more
        online_username_data = (supabase_engine
                                .table("users").select("username")
                                .eq(column="username", value=self.username)
                                .execute()
                               )

        # If username exists → regenerate again until you make one that doesn't
        # while running username_gen_sql gives you a value not "None"...

        while online_username_data.data:
            self.username = generate_username()
            online_username_data = (supabase_engine
                                .table("users").select("username")
                                .eq(column="username", value=self.username)
                                .execute()
                               )

        # If username does NOT exist in online DB:

        database_time = datetime.now(timezone.utc)

        df = pd.DataFrame(
            [(self.username, database_time)],
            columns = ["username", "created_at"]
        )

        # Save to local DB (CAN ONLY DO THIS ONCE):
        conn = sqlite3.connect(self.db_path)
        df.to_sql("users", conn, if_exists="fail", index=False)
        conn.close()

        # Save to online DB (CAN ONLY DO THIS ONCE):
        supabase_engine.table("users").insert({"username":self.username, "created_at":database_time.isoformat()}).execute()

    # -----------------------------------------------------------------------------------------------
    # 🔥 Save age range to SQLite using pandas and to online DB with supabase engine
    # -----------------------------------------------------------------------------------------------
    def save_age_to_db(self, age_str):
        self.age = age_str

        df = pd.DataFrame(
            [(self.age, self.username)],
            columns = ["age", "username"]
        )

        # Save to local DB:
        conn = sqlite3.connect(self.db_path)
        df.to_sql("age", conn, if_exists="replace", index=False)
        conn.close()

        # Save to online DB:
        supabase_engine.table("age").upsert({"user": self.username, "age": self.age}).execute()

    # -----------------------------------------------------------------------------------------------
    # 🔥 Save zipcode range to SQLite using pandas and to online DB with supabase engine
    # -----------------------------------------------------------------------------------------------
    def save_zipcode_to_db(self, zipcode, state):
        self.user_zip = zipcode
        self.user_state = state

        df = pd.DataFrame(
            [(self.user_zip, self.user_state, self.username)],
            columns = ["zipcode", "state", "username"]
        )

        # Save to local DB:
        conn = sqlite3.connect(self.db_path)
        df.to_sql("user_zipcode", conn, if_exists="replace", index=False)
        conn.close()

        # Save to online DB:
        supabase_engine.table("user_zipcodes").upsert({"username": self.username, "state": self.user_state, "zipcode": self.user_zip}).execute()

    # ----------------------------------------------------------
    # 🔥 Load rankings from SQLite if available
    # ----------------------------------------------------------
    def load_rankings_from_db(self):
        if not os.path.exists(self.db_path):
            return

        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql("SELECT * FROM rankings", conn)
        except Exception:
            conn.close()
            return

        conn.close()

        if df.empty:
            return

        # Restore state
        self.selected_games = df["game"].tolist()
        self.rankings = dict(zip(df["game"], df["rank"]))

    # ----------------------------------------------------------
    # 🔥 Load username from SQLite if available
    # ----------------------------------------------------------
    def load_username_from_db(self):
        if not os.path.exists(self.db_path):
            return

        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql("SELECT username FROM users", conn)
        except Exception:
            conn.close()
            return

        conn.close()

        if df.empty:
            return

        # Restore state
        self.username = df.squeeze()
        return self.username

    # ----------------------------------------------------------
    # 🔥 Load age from SQLite if available
    # ----------------------------------------------------------
    def load_age_from_db(self):
        if not os.path.exists(self.db_path):
            return

        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql("SELECT age FROM age", conn)
        except Exception:
            conn.close()
            return

        conn.close()

        if df.empty:
            return

        # Restore state
        self.age = df.squeeze()
        return self.age

    # ----------------------------------------------------------
    # 🔥 Load zipcode from SQLite if available
    # ----------------------------------------------------------
    def load_zipcode_from_db(self):
        if not os.path.exists(self.db_path):
            return

        conn = sqlite3.connect(self.db_path)
        try:
            df_zip = pd.read_sql("SELECT zipcode FROM user_zipcode", conn)
            df_state = pd.read_sql("SELECT state FROM user_zipcode", conn)
        except Exception:
            conn.close()
            return

        conn.close()

        if df_zip.empty or df_state.empty:
            return

        # Restore state
        self.user_zip = df_zip.squeeze()
        self.user_state = df_state.squeeze()

        return (self.user_zip, self.user_state)

# ---------------- START PAGE ----------------

class StartPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Loading and displaying username and age:
        local_username = self.controller.load_username_from_db()
        if not local_username:
            self.controller.save_username_to_db()
            local_username = self.controller.load_username_from_db()

        ttk.Label(self, text=f"Username: {local_username}", font=("Arial", 15)).pack()

        local_age = self.controller.load_age_from_db()
        local_age = "N/A" if not local_age else local_age
        self.age_label = ttk.Label(self, text=f"Age: {local_age}", font=("Arial", 15))
        self.age_label.pack()

        # Displaying page title:
        ttk.Label(self, text="Start Page", font=("Arial", 18)).pack(pady=20)

        ttk.Button(self,text="Go to Page 2 (Select Games)",
                   command=lambda: controller.show_frame("PageTwo")).pack()
        
        # Note: Page 3 Automatically follows page 2 if the "Page 2" button is selected. 
        # After you select new games, you must re-rank them.

        ttk.Button(self,text="Go to Page 3 (Rank/Re-Rank Games)",
                   command=lambda: controller.show_frame("PageThree")).pack()
        
        ttk.Button(self,text="Go to Page 4 (View Ranking List)",
                   command=lambda: controller.show_frame("PageFour")).pack()

        ttk.Button(self,text="Go to Page 5 (Search for Your Location (ZIP code))",
                           command=lambda: controller.show_frame("PageFive")).pack()

        ttk.Button(self,text="Go to Page 6 (Select Your Age)",
                           command=lambda: controller.show_frame("PageSix")).pack()
        
        ttk.Button(self,text="Go to Page 7 (Search for Gamers)",
                   command=lambda: controller.show_frame("PageSeven")).pack()

        ttk.Button(self,text="Go to Page 8 (See Gamer Messages)",
                   command=lambda: controller.show_frame("PageEight")).pack()

    def refresh_age(self):
        """Called when the page is shown by App() controller to update the age."""
        age = self.controller.load_age_from_db()
        self.age_label.config(text=f"Age: {age}", font=("Arial", 15))
        
# ---------------- PAGE 2: Choose Game Titles ----------------

class PageTwo(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        # PAGE TITLE
        ttk.Label(self, text="Page 2: Choose 5 Games", font=("Arial", 16)).pack(pady=10)

        # Example list of Game Titles
        self.games = ["Splatoon 3", "Mario Kart 8 Deluxe", "Super Smash Bros. Ultimate", "Fortnite", "Overwatch 2", "Call of Duty: Modern Warefare 1-4", "Call of Duty: Black Ops 6-7", "Apex Legends", "Minecraft"]

        # Dictionary of checkbox variables
        self.vars = {}

        for game in self.games:
            var = tk.BooleanVar()
            chk = ttk.Checkbutton(self, text=game, variable=var)
            chk.pack(anchor="w", padx=20)
            self.vars[game] = var

        ttk.Button(
            self,
            text="Save Selections and Continue",
            command=lambda: self.save_and_continue(controller)
        ).pack(pady=20)

    def save_and_continue(self, controller):
        # Save selected game titles
        controller.selected_games = [
            game for game, var in self.vars.items() if var.get()
        ]

        if len(controller.selected_games) < 5:
            messagebox.showerror(message="Please select 5 Game Titles.")
            return
        elif len(controller.selected_games) > 5:
            messagebox.showerror(message=f"You have selected more than 5 games. Please deselect {len(controller.selected_games) - 5} Game Title(s).")
            return
        else:
            # Reset rankings in controller
            controller.rankings = {}

            # Reset Page 3 internal state so it rebuilds correctly
            page3 = controller.frames["PageThree"]

            page3.rank_vars = {}
            page3.comboboxes = {}
            page3.has_loaded_once = False

            # Clear the dropdown frame widgets
            for widget in page3.dropdown_frame.winfo_children():
                widget.destroy()

            # Reset the button text
            page3.load_button.config(text="Load Ranking Options")

            # Disable Continue button again
            page3.continue_button.config(state="disabled")

            # Hide validation label
            page3.validation_label.pack_forget()

            controller.show_frame("PageThree")

# ---------------- PAGE 3: Game Rankings ----------------

class PageThree(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.has_loaded_once = False

        # PAGE TITLE
        ttk.Label(self, text="Page 3: Rank Your Selections", font=("Arial", 16)).pack(pady=10)

        # ---------------------------------------------------------
        # FRAME THAT HOLDS ALL DROPDOWNS
        # ---------------------------------------------------------
        self.dropdown_frame = ttk.Frame(self)
        self.dropdown_frame.pack(pady=10)

        # ---------------------------------------------------------
        # LOAD / REFRESH BUTTON
        # (renames itself after first click)
        # ---------------------------------------------------------
        self.load_button = ttk.Button(
            self,
            text="Load Ranking Options",
            command=self.build_dropdowns
        )
        self.load_button.pack()

        # ---------------------------------------------------------
        # CONTINUE BUTTON (disabled until all ranks chosen)
        # ---------------------------------------------------------
        self.continue_button = ttk.Button(
            self,
            text="Continue to Page 4",
            command=lambda: controller.show_frame("PageFour"),
            state="disabled"
        )
        self.continue_button.pack(pady=10)

        # --------------------------------------------------------------------------------
        # BACK TO START PAGE BUTTON (in case the user made a mistake/ has no list to rank)
        # --------------------------------------------------------------------------------
        ttk.Button(self,
                   text="Back to Start Page",
                   command=lambda: controller.show_frame("StartPage")
                  ).pack(pady=5)

        # ---------------------------------------------------------
        # VALIDATION LABEL (hidden until needed)
        # ---------------------------------------------------------
        self.validation_label = ttk.Label(
            self,
            text="Please complete rankings list and complete all rankings",
            foreground="red"
        )
        self.validation_label.pack()
        self.validation_label.pack_forget()

        # ---------------------------------------------------------
        # INTERNAL STORAGE FOR DROPDOWNS
        # ---------------------------------------------------------
        self.rank_vars = {}      # item -> StringVar
        self.comboboxes = {}     # item -> Combobox widget

    # -------------------------------------------------------------
    # THIS RUNS EVERY TIME THE PAGE IS SHOWN
    # -------------------------------------------------------------
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        # Do NOT auto-build dropdowns here.
        # Page 3 should only load rankings when the button is pressed.

    # -------------------------------------------------------------
    # BUILD ALL DROPDOWNS (fresh or refreshed)
    # -------------------------------------------------------------
    def build_dropdowns(self):
        selections = self.controller.selected_games

        # First time ever loading → use DB rankings if available
        if not self.has_loaded_once:
            self.has_loaded_once = True
        else:
            # After first time → treat as a true refresh/reset
            self.controller.rankings = {}
            self.controller.save_rankings_to_db()


        # Rename button after first click
        if self.load_button.cget("text") == "Load Ranking Options":
            self.load_button.config(text="Refresh Rankings")

        # Clear old dropdowns
        for widget in self.dropdown_frame.winfo_children():
            widget.destroy()

        self.rank_vars.clear()
        self.comboboxes.clear()

        count = len(selections)

        # If nothing selected on Page 2
        if count == 0:
            ttk.Label(self.dropdown_frame, text="No games selected on Page 2").pack()
            self.continue_button.config(state="disabled")
            self.validation_label.pack()
            return

        # Create dropdowns for each selected game title
        for game in selections:
            row = ttk.Frame(self.dropdown_frame)
            row.pack(fill="x", pady=5)

            ttk.Label(row, text=game, width=50).pack(side="left")

            var = tk.StringVar()
            combo = ttk.Combobox(row, textvariable=var, width=5, state="readonly")
            combo.pack(side="right")

            self.rank_vars[game] = var
            self.comboboxes[game] = combo

            # -----------------------------------------------------
            # PRE-FILL FROM DATABASE IF AVAILABLE
            # -----------------------------------------------------
            if game in self.controller.rankings:
                saved_rank = str(self.controller.rankings[game])
                var.set(saved_rank)

            # Update dropdowns whenever a rank changes
            var.trace_add("write", lambda *args: self.update_dropdowns())

        # Initial update (sets available ranks + button state)
        self.update_dropdowns()

    # -------------------------------------------------------------
    # UPDATE DROPDOWN OPTIONS + SAVE RANKINGS + VALIDATE COMPLETION
    # -------------------------------------------------------------
    def update_dropdowns(self):
        selections = self.controller.selected_games
        total = len(selections)

        # Collect used ranks
        used_ranks = set()
        for item, var in self.rank_vars.items():
            value = var.get()
            if value.isdigit():
                used_ranks.add(int(value))

        all_ranks = set(range(1, total + 1))

        # Update each dropdown's available values
        for item, var in self.rank_vars.items():
            current_value = var.get()
            available = sorted(list(all_ranks - used_ranks))

            # Allow keeping the current rank
            if current_value.isdigit():
                current_rank = int(current_value)
                if current_rank not in available:
                    available.append(current_rank)
                    available = sorted(available)

            combo = self.comboboxes[item]
            combo["values"] = available

        # Save rankings to controller
        self.controller.rankings = {
            item: int(var.get())
            for item, var in self.rank_vars.items()
            if var.get().isdigit()
        }

        # ---------------------------------------------------------
        # ENABLE CONTINUE BUTTON ONLY WHEN ALL RANKS ARE SET
        # ---------------------------------------------------------
        if len(self.controller.rankings) == total and total > 0:
            self.continue_button.config(state="normal")
            self.validation_label.pack_forget()

            # Save to DB when complete
            self.controller.save_rankings_to_db()

        else:
            self.continue_button.config(state="disabled")
            self.validation_label.pack()

# ---------------- PAGE 4: View Game Rankings List ----------------

class PageFour(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # PAGE TITLE
        ttk.Label(self, text="Page 4: Final Rankings", font=("Arial", 16)).pack(pady=10)

        self.output_frame = ttk.Frame(self)
        self.output_frame.pack(pady=10)


        ttk.Button(
            self,
            text="Go to Ranking Page",
            command=lambda: controller.show_frame("PageThree")
        ).pack(pady=5)

        ttk.Button(
            self,
            text="Back to Start Page",
            command=lambda: controller.show_frame("StartPage")
        ).pack(pady=5)


    # This method runs every time the page is shown
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.display_rankings()   # auto-refresh on page show


    def display_rankings(self):
        for widget in self.output_frame.winfo_children():
            widget.destroy()

        
        self.controller.load_rankings_from_db()
        rankings = self.controller.rankings

        
        if not rankings:
            ttk.Label(self.output_frame, text="No rankings selected yet").pack()
            return
        

        sorted_items = sorted(rankings.items(), key=lambda x: x[1])

        for game, rank in sorted_items:
            ttk.Label(self.output_frame, text=f"{rank}. {game}").pack(anchor="w")

# ---------------- PAGE 5: Zipcode Lookup Page ----------------

class PageFive(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # PAGE TITLE
        ttk.Label(self, text="Page 5: ZIP Code Lookup",
                    font=("Arial", 14)).pack(pady=5)

        # Saved ZIP display
        self.saved_zip_label = ttk.Label(self, text="Saved ZIP Code: None")
        self.saved_zip_label.pack(pady=3)

        # Check if an old ZIP code and State were saved
        old_zip_state = self.controller.load_zipcode_from_db()
        if old_zip_state:
            old_zip_code = old_zip_state[0]
            old_state = old_zip_state[1]
            self.saved_zip_label.config(text=f"Saved ZIP Code: {old_zip_code} ({old_state})")

        ttk.Button(self, text="Back to Start Page",
                    command=lambda: controller.show_frame("StartPage")
                    ).pack(anchor="w", padx=10, pady=3)

        ttk.Label(self, text="Enter ZIP Code:").pack(anchor="w", padx=10)
        self.entry_zip = ttk.Entry(self, width=15)
        self.entry_zip.pack(anchor="w", padx=10)
        self.entry_zip.bind("<KeyRelease>", self.update_autocomplete)

        # Autocomplete with scrollbar
        listbox_frame = ttk.Frame(self)
        listbox_frame.pack(anchor="w", padx=10)

        self.listbox = tk.Listbox(listbox_frame, height=4, width=10)
        self.listbox.pack(side="left")

        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical",
                                    command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.bind("<ButtonRelease-1>", self.fill_from_listbox)

        ttk.Button(self, text="Lookup ZIP",
                    command=self.lookup_zip).pack(pady=5)

        self.tree = ttk.Treeview(self,
                                    columns=("State", "Longitude", "Latitude"),
                                    show="headings", height=6)
        self.tree.heading("State", text="State")
        self.tree.heading("Longitude", text="Longitude")
        self.tree.heading("Latitude", text="Latitude")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        # Single-click event
        self.tree.bind("<ButtonRelease-1>", self.on_row_click)
    
    def update_autocomplete(self, event):
        typed = self.entry_zip.get()
        self.listbox.delete(0, tk.END)
        self.ALL_ZIPS = self.controller.load_all_zips()

        if typed == "":
            return

        matches = [z for z in self.ALL_ZIPS if z.startswith(typed)]
        for m in matches[:10]:
            self.listbox.insert(tk.END, m)

    def fill_from_listbox(self, event):
        try:
            selection = self.listbox.get(self.listbox.curselection())
        except:
            return
        self.entry_zip.delete(0, tk.END)
        self.entry_zip.insert(0, selection)

    def lookup_zip(self):
        zip_code = self.entry_zip.get().strip()
        zip_db_path = self.controller.zip_db_path

        if not zip_code:
            messagebox.showerror("Error", "Please enter a ZIP code.")
            return

        conn = sqlite3.connect(zip_db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT ste_name, longitude, latitude
            FROM zipcodes
            WHERE zcta5_code = ?
        """, (zip_code,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            messagebox.showinfo("Not Found", f"No data found for ZIP {zip_code}.")
            return

        # Save ZIP + first state
        state = rows[0][0]
        self.controller.user_zip = zip_code
        self.controller.user_state = state

        self.saved_zip_label.config(text=f"Saved ZIP Code: {zip_code} ({state})")
        self.controller.save_zipcode_to_db(zip_code, state)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in rows:
            state, lon, lat = row
            self.tree.insert("", "end", values=(state, lon, lat))

    def on_row_click(self, event):
        selected = self.tree.focus()
        if not selected:
            return

        values = self.tree.item(selected, "values")
        if not values:
            return

        state, lon, lat = values
        zip_code = self.controller.user_zip

        messagebox.showinfo(
            "ZIP Selected",
            f"You selected ZIP {zip_code} in {state}.\nCoordinates: {lat}, {lon}"
        )

# ---------------- PAGE 6: Age Page ----------------

class PageSix(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.username = self.controller.username
        self.age = self.controller.age

        # PAGE TITLE
        ttk.Label(self, text="Page 6: Select Your Age", font=("Arial", 16)).pack(pady=10)

        # ---------------------------------------------------------
        # LAYOUT: Radiobutton Age Selection
        # ---------------------------------------------------------
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        self.age = tk.StringVar(value="N/A")

        ttk.Label(main, text="Please select your age range:").pack(anchor="w", pady=(5, 0))

        ttk.Radiobutton(main, text="13-17", value="13-17", variable=self.age).pack(anchor="w")
        ttk.Radiobutton(main, text="18-25", value="18-25", variable=self.age).pack(anchor="w")
        ttk.Radiobutton(main, text="26-30", value="26-30", variable=self.age).pack(anchor="w")
        ttk.Radiobutton(main, text="31 and up", value="31+", variable=self.age).pack(anchor="w")

        ttk.Button(
            main,
            text="Save Your Age",
            command=self.save_age
        ).pack(pady=5)

        ttk.Button(
            main,
            text="Back to Start Page",
            command=lambda: controller.show_frame("StartPage")
        ).pack(pady=5)

    def save_age(self):
        print("AGE VALUE:", self.age.get())
        self.controller.save_age_to_db(self.age.get())

# ---------------- PAGE 7: Search Page ----------------

class PageSeven(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.username = self.controller.username

        # PAGE TITLE
        ttk.Label(self, text="Page 7: Search for Gamers", font=("Arial", 16)).pack(pady=10)

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

    # -------------------------------------------------------------------------------------------
    # REFRESH REQUIRED DATA: Used by the main App() so it finds rankings, location, and age data.
    #                        If rankings, location, or age is missing, DOES NOT LOAD FULL PAGE.
    #                        Loads buttons to go fill in missing data instead.
    # -------------------------------------------------------------------------------------------
    def refresh_required_data(self):
        # Clear old widgets
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Reload data fresh
        self.controller.load_rankings_from_db()
        self.controller.load_zipcode_from_db()
        self.controller.load_age_from_db()

        missing_data = False

        if not self.controller.rankings:
            ttk.Label(self.main_frame, text="You have no current rankings to compare:").pack(pady=5)
            ttk.Button(self.main_frame, text="Go to Page 2 (Select Games)",
                    command=lambda: self.controller.show_frame("PageTwo")).pack(pady=5)
            missing_data = True

        if not self.controller.user_zip:
            ttk.Label(self.main_frame, text="You have not set your location yet:").pack(pady=5)
            ttk.Button(self.main_frame, text="Go to Page 5 (Search for Your Location)",
                    command=lambda: self.controller.show_frame("PageFive")).pack(pady=5)
            missing_data = True

        if not self.controller.age or self.controller.age == "N/A":
            ttk.Label(self.main_frame, text="You have not saved your age yet:").pack(pady=5)
            ttk.Button(self.main_frame, text="Go to Page 6 (Select Your Age)",
                    command=lambda: self.controller.show_frame("PageSix")).pack(pady=5)
            missing_data = True

        if missing_data:
            ttk.Label(self.main_frame, text="Alternatively, you can go:").pack(pady=5)
            ttk.Button(self.main_frame, text="Back to Start Page",
                    command=lambda: self.controller.show_frame("StartPage")).pack(pady=5)
            return

        # If no missing data, build full page here
        self.build_full_page()

    # -----------------------------------------------------------
    # FULL PAGE LAYOUT: LEFT SETTINGS PANEL + RIGHT RESULTS PANEL
    # -----------------------------------------------------------
    def build_full_page(self):        
        main = ttk.Frame(self.main_frame)
        main.pack(fill="both", expand=True)

        # LEFT SIDE SETTINGS
        settings_frame = ttk.Frame(main)
        settings_frame.pack(side="left", fill="y", padx=10, pady=10)

        ttk.Label(settings_frame, text="Search Settings", font=("Arial", 14)).pack(pady=5)

        ttk.Label(settings_frame, text="How many results:").pack(anchor="w")
        self.num_results = tk.IntVar(value=10)
        ttk.Spinbox(settings_frame, from_=1, to=50, textvariable=self.num_results, width=5).pack(anchor="w")

        self.age_13_17 = tk.BooleanVar()
        self.age_18_25 = tk.BooleanVar()
        self.age_26_30 = tk.BooleanVar()
        self.age_31_up = tk.BooleanVar()

        ttk.Label(settings_frame, text="Please select all age ranges you would like to search for:").pack(
                                                                                 anchor="w", pady=(5, 0))

        ttk.Checkbutton(settings_frame, text="13-17", variable=self.age_13_17).pack(anchor="w")
        ttk.Checkbutton(settings_frame, text="18-25", variable=self.age_18_25).pack(anchor="w")
        ttk.Checkbutton(settings_frame, text="26-30", variable=self.age_26_30).pack(anchor="w")
        ttk.Checkbutton(settings_frame, text="31 and up", variable=self.age_31_up).pack(anchor="w")

        self.age_ranges = [(self.age_13_17, "13-17"), 
                           (self.age_18_25, "18-25"),
                           (self.age_26_30, "26-30"),
                           (self.age_31_up, "30+")]

        # Saved zip is initialized to "None" before "ZipLookup Page". 
        # But after that, this always refreshes with the "refresh()" function to match the last saved 
        # controller/App() "self.user_zip/state" values.
        # Check if an old ZIP code and State were saved
        self.using_zip_label = ttk.Label(settings_frame, text=f"Using ZIP Code: None")

        old_zip_code, old_state = self.controller.load_zipcode_from_db()
        if old_zip_code and old_state:  
            self.using_zip_label.config(text=f"Using ZIP Code: {old_zip_code} ({old_state})")

        self.using_zip_label.pack(pady=3)

        # Slider label
        self.radius_label = ttk.Label(settings_frame, text="Radius Within: 5 miles")
        self.radius_label.pack(anchor="w", padx=10)

        # Slider for radius (5–50 miles)
        self.radius_slider = ttk.Scale(settings_frame, from_=5, to=50,
                                        orient="horizontal",
                                        command=self.update_radius_label)
        self.radius_slider.pack(anchor="w", padx=10)
        self.radius_slider.configure(length=200)
        
        ttk.Button(
            settings_frame,
            text="Run Search",
            command=self.run_search
        ).pack(pady=5)
        
        ttk.Label(settings_frame, text="Your Ranking List:").pack(pady=5)
        for i, item in enumerate(sorted(self.controller.rankings.items(), key=lambda x: x[1]), start=1):
            ttk.Label(settings_frame, text=f"{i}. {item[0]}").pack()

        ttk.Button(
            settings_frame,
            text="Back to Start Page",
            command=lambda: self.controller.show_frame("StartPage")
        ).pack(pady=5)

        # RIGHT SIDE RESULTS (scrollable)
        results_container = ttk.Frame(main)
        results_container.pack(side="right", fill="both", expand=True)

        canvas = tk.Canvas(results_container)
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=canvas.yview)
        self.results_frame = ttk.Frame(canvas)

        self.results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # -----------------------------------------------------------------------------------------------------
    # UPDATE RADIUS LABEL: Used by ttk.Scale Object (slider bar) above to show current mile-radius setting.
    # -----------------------------------------------------------------------------------------------------
    def update_radius_label(self, value):
        miles = round(float(value) / 5) * 5
        self.radius_label.config(text=f"Radius Within: {miles} miles")

    # -------------------------------------------------------------------------------------------------------------
    # SEARCH RADIUS: Used by RUN SEARCH function below to gain valid locations that match the miles-radius setting.
    # -------------------------------------------------------------------------------------------------------------
    def search_radius(self):
        # Always load fresh values from controller
        # Check if an old ZIP code and State were saved
        old_zip_state = self.controller.load_zipcode_from_db()
        if old_zip_state:
            old_zip_code = old_zip_state[0]
            old_state = old_zip_state[1]

            # ⭐ Correct label update
            self.using_zip_label.config(text=f"Using ZIP Code: {old_zip_code} ({old_state})")

        zip_db_path = self.controller.zip_db_path

        radius = round(self.radius_slider.get() / 5) * 5

        conn = sqlite3.connect(zip_db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT longitude, latitude
            FROM zipcodes
            WHERE zcta5_code = ?
            LIMIT 1
        """, (old_zip_code,))
        center = cur.fetchone()

        if not center:
            messagebox.showerror("Error", "ZIP not found.")
            conn.close()
            return

        center_lon, center_lat = center
        center_point = (center_lat, center_lon)

        cur.execute("SELECT zcta5_code, ste_name, longitude, latitude FROM zipcodes")
        all_rows = cur.fetchall()
        conn.close()

        results = set()
        for z, st, lon, lat in all_rows:
            dist = geodesic(center_point, (lat, lon)).miles
            if dist <= radius:
                results.add((int(z), st))

        return results

    # ---------------------------------------------------------
    # RUN SEARCH: LOAD DB, COMPUTE SIMILARITY, DISPLAY RESULTS
    # ---------------------------------------------------------
    def run_search(self):
        # Clear old results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Find all acceptable ages
        acceptable_ages = []
        for age_range, age_str in self.age_ranges:
            if age_range.get() == True:
                acceptable_ages.append(age_str)

        # If user did not select an age range, warn them of this.
        if len(acceptable_ages) == 0:
            messagebox.showerror(message="Please enter at least 1 age range for the search.")
            return

        # Find all acceptable ZIP codes
        acceptable_zips = self.search_radius()   # set of (zip, state)

        # Load online DB rankings
        try:
            # 1. Get usernames with acceptable ages
            user_age_results = (
                supabase_engine
                .table("age")
                .select("age, users(username)")
                .in_("age", acceptable_ages)
                .execute()
            )

            age_usernames = [row["users"]["username"] for row in user_age_results.data]

            # 2. Get ZIP codes for all users
            zip_results = (
                supabase_engine
                .table("user_zipcodes")
                .select("username, zipcode, state")
                .execute()
            )

            zip_df = pd.DataFrame(zip_results.data)

            # 3. Filter usernames by acceptable_zips
            zip_df["zip_state"] = list(zip(zip_df["zipcode"], zip_df["state"]))
            zip_filtered_df = zip_df[zip_df["zip_state"].isin(acceptable_zips)]

            zip_usernames = set(zip_filtered_df["username"])

            # 4. Load user rankings
            response = supabase_engine.table("rankings").select("*").execute()
            user_rankings_df = pd.DataFrame(response.data)

            # 5. Filter user rankings to only get rankings from users with acceptable ages
            filtered_df = user_rankings_df[user_rankings_df["username"].isin(age_usernames)]

            # 6. Filter user rankings to only get rankings from properly aged users with acceptable ZIPs
            filtered_df = filtered_df[filtered_df["username"].isin(zip_usernames)]

            # 7. Remove yourself from list of users
            filtered_df = filtered_df[filtered_df["username"] != self.controller.username]

        except Exception:
            ttk.Label(self.results_frame, text="Error occured when searching for external rankings.").pack()
            return

        if filtered_df.empty:
            ttk.Label(self.results_frame, text="No external user rankings found.\nPlease try different filters.").pack()
            return

        # Current user's ranking list
        self.controller.load_rankings_from_db()
        current = self.controller.rankings
        if not current:
            ttk.Label(self.results_frame, text="You have no current rankings to compare with.").pack()
            return

        current_list = [item for item, rank in sorted(current.items(), key=lambda x: x[1])]

        # ---------------------------------------------------------
        # GROUP BY USERNAME → build each user's ranked list
        # ---------------------------------------------------------
        results = []

        for external_username in filtered_df["username"].unique():
            # 🔥 Skip the current user
            if external_username == self.controller.username:
                continue

            user_rows = user_rankings_df[user_rankings_df["username"] == external_username].sort_values("rank")

            # Build that user's list (top 5 only)
            user_list = user_rows["game"].tolist()[:5]

            # Compute similarity score
            score = self.compute_similarity(current_list, user_list)

            results.append((external_username, user_list, score))

        # ---------------------------------------------------------
        # Sort results by similarity score (highest first)
        # ---------------------------------------------------------
        results.sort(key=lambda x: x[2], reverse=True)

        # ---------------------------------------------------------
        # Display results
        # ---------------------------------------------------------
        for external_username, user_list, score in results[:self.num_results.get()]:
            frame = ttk.Frame(self.results_frame)
            frame.pack(anchor="w", pady=10)

            ttk.Label(frame, text=f"User: {external_username}", font=("Arial", 12)).pack(anchor="w")
            ttk.Label(frame, text=f"Score: {score}", foreground="blue").pack(anchor="w")

            ttk.Label(frame, text="List:", font=("Arial", 10)).pack(anchor="w")

            for i, item in enumerate(user_list, start=1):
                ttk.Label(frame, text=f"{i}. {item}").pack(anchor="w")

            ttk.Button(frame,
                       text="Send Message",
                       command=lambda u=external_username: (
                                                    self.controller.frames["PageEight"].open_compose_from_page7(u),
                                                    self.controller.show_frame("PageEight")
                                                  )
                      ).pack(anchor="w")
            
    # ---------------------------------------------------------
    # SIMILARITY FUNCTION (weighted ranking match)
    # ---------------------------------------------------------
    def compute_similarity(self, current, saved):
        score = 0

        # Weighting: top ranks matter more
        for i in range(min(len(current), len(saved))):
            if current[i] == saved[i]:
                score += (len(current) - i) * 2  # strong match for high ranks

        # Partial matches anywhere in top 5
        top5_current = set(current[:5])
        top5_saved = set(saved[:5])
        score += len(top5_current.intersection(top5_saved))

        return score

# ---------------- PAGE 8: Messages and Conversations ----------------

class PageEight(ttk.Frame):
    def __init__(self, parent, controller, Conversations, send_message_func):
        super().__init__(parent)
        self.controller = controller
        self.username = self.controller.username
        self.Conversations = Conversations
        self.send_message_func = send_message_func

        # State variables
        self.selected_user = None
        self.selected_message = None

        # Main container
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        # Build all displays
        self.build_display1()
        self.build_display2()
        self.build_display3()
        self.build_display4()

        # Start on Display 1
        self.show_display(1)

    # ------------------------------------------------------------
    # Helper: Switch between displays
    # ------------------------------------------------------------
    def show_display(self, num):
        self.display1_frame.pack_forget()
        self.display2_frame.pack_forget()
        self.display3_frame.pack_forget()
        self.display4_frame.pack_forget()

        if num == 1:
            self.refresh_display1()
            self.display1_frame.pack(fill="both", expand=True)
        elif num == 2:
            self.refresh_display2()
            self.display2_frame.pack(fill="both", expand=True)
        elif num == 3:
            self.refresh_display3()
            self.display3_frame.pack(fill="both", expand=True)
        elif num == 4:
            self.refresh_display4()
            self.display4_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------
    # DISPLAY 1 — Inbox Overview
    # ------------------------------------------------------------
    def build_display1(self):
        self.display1_frame = ttk.Frame(self.main_frame)

        ttk.Label(self.display1_frame, text="Inbox Overview", font=("Arial", 16)).pack(pady=10)

        # Scrollable area
        container = ttk.Frame(self.display1_frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.display1_list = ttk.Frame(canvas)

        self.display1_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.display1_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(self.display1_frame, text="Go to Page 7: Search Page",
                   command=lambda: self.controller.show_frame("PageSeven")).pack(pady=10)

        ttk.Button(self.display1_frame, text="Back to Start Page",
                   command=lambda: self.controller.show_frame("StartPage")).pack(pady=10)

    def refresh_display1(self):
        for w in self.display1_list.winfo_children():
            w.destroy()

        for external_username, msgs in self.Conversations.items():
            if external_username == self.controller.username:
                continue

            # Sort messages by timestamp
            msgs_sorted = sorted(msgs, key=lambda x: x[2], reverse=True)
            latest = msgs_sorted[0]

            block = ttk.Frame(self.display1_list)
            block.pack(fill="x", pady=5, padx=10)

            # Converting online database time "latest[2]" -> localtime on this machine when displaying
            dt_utc = datetime.strptime(latest[2].isoformat(), "%Y-%m-%dT%H:%M:%S.%f%z")
            local_tz = datetime.now().astimezone().tzinfo
            dt_local = dt_utc.astimezone(local_tz)

            ttk.Label(block, text=f"Username: {external_username}", font=("Arial", 12)).pack(anchor="w")
            ttk.Label(block, text=f"Last Msg {latest[0]}: {latest[1][:200]}").pack(anchor="w")
            ttk.Label(block, text=f"Time: {dt_local}").pack(anchor="w")

            ttk.Button(block, text="View All Messages",
                       command=lambda u=external_username: self.open_user_messages(u)).pack(anchor="w", pady=3)

            ttk.Button(block, text="Send Message",
                       command=lambda u=external_username: self.open_compose_from_page7(u)).pack(anchor="w")

    def open_user_messages(self, username):
        self.selected_user = username
        self.show_display(2)

    def open_compose_from_page7(self, username):
        self.selected_user = username
        self.show_display(4)

    # ------------------------------------------------------------
    # DISPLAY 2 — All Messages for Selected User
    # ------------------------------------------------------------
    def build_display2(self):
        self.display2_frame = ttk.Frame(self.main_frame)

        ttk.Label(self.display2_frame, text="Messages with User", font=("Arial", 16)).pack(pady=10)

        container = ttk.Frame(self.display2_frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.display2_list = ttk.Frame(canvas)

        self.display2_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.display2_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(self.display2_frame, text="Back to Inbox",
                   command=lambda: self.show_display(1)).pack(pady=10)

    def refresh_display2(self):
        for w in self.display2_list.winfo_children():
            w.destroy()

        msgs = sorted(self.Conversations[self.selected_user], key=lambda x: x[2], reverse=True)

        for msg in msgs:
            block = ttk.Frame(self.display2_list)
            block.pack(fill="x", pady=5, padx=10)

            # Converting online database time "msg[2]" -> localtime on this machine when displaying.
            dt_utc = datetime.strptime(msg[2].isoformat(), "%Y-%m-%dT%H:%M:%S.%f%z")
            local_tz = datetime.now().astimezone().tzinfo
            dt_local = dt_utc.astimezone(local_tz)

            ttk.Label(block, text=f"{msg[0].upper()} — {dt_local}").pack(anchor="w")
            ttk.Label(block, text=msg[1][:200]).pack(anchor="w")

            ttk.Button(block, text="View Full Message",
                       command=lambda m=msg: self.open_full_message(m)).pack(anchor="w")

    def open_full_message(self, msg):
        self.selected_message = msg
        self.show_display(3)

    # ------------------------------------------------------------
    # DISPLAY 3 — Full Message View
    # ------------------------------------------------------------
    def build_display3(self):
        self.display3_frame = ttk.Frame(self.main_frame)

        ttk.Label(self.display3_frame, text="Full Message View", font=("Arial", 16)).pack(pady=10)

        self.display3_text = tk.Text(self.display3_frame, wrap="word", height=10, width=60)
        self.display3_text.config(state="disabled")
        self.display3_text.pack(pady=10)

        ttk.Button(self.display3_frame, text="Send Message to User",
                   command=lambda: self.show_display(4)).pack(pady=5)

        ttk.Button(self.display3_frame, text="Back to User Messages",
                   command=lambda: self.show_display(2)).pack(pady=5)

        ttk.Button(self.display3_frame, text="Back to Inbox",
                   command=lambda: self.show_display(1)).pack(pady=5)

    def refresh_display3(self):
        # Temporarily enable so we can insert text
        self.display3_text.config(state="normal")
        self.display3_text.delete("1.0", tk.END)

        msg = self.selected_message

        # Converting online database time "msg[2]" -> local_time on this machine when displaying.
        dt_utc = datetime.strptime(msg[2].isoformat(), "%Y-%m-%dT%H:%M:%S.%f%z")
        local_tz = datetime.now().astimezone().tzinfo
        local_dt = dt_utc.astimezone(local_tz)

        # Displaying the full message
        if msg[0] == 'recieved':
            header = f"{msg[0].upper()} from {self.selected_user} at {local_dt}\n\n"
        if msg[0] == 'sent':
            header = f"{msg[0].upper()} to {self.selected_user} at {local_dt}\n\n"

        self.display3_text.insert(tk.END, header)
        self.display3_text.insert(tk.END, msg[1])

        # Disable editing again
        self.display3_text.config(state="disabled")


    # ------------------------------------------------------------
    # DISPLAY 4 — Compose Message
    # ------------------------------------------------------------
    def build_display4(self):
        self.display4_frame = ttk.Frame(self.main_frame)

        self.compose_label = ttk.Label(self.display4_frame, text="", font=("Arial", 16))
        self.compose_label.pack(pady=10)

        self.compose_entry = tk.Text(self.display4_frame, wrap="word", height=10, width=60)
        self.compose_entry.pack(pady=10)

        ttk.Button(self.display4_frame, text="Send Message",
                   command=self.confirm_send).pack(pady=5)

        ttk.Button(self.display4_frame, text="Back to Inbox",
                   command=lambda: self.show_display(1)).pack(pady=5)

    def refresh_display4(self):
        self.compose_label.config(text=f"Message to {self.selected_user}")
        self.compose_entry.delete("1.0", tk.END)

    def confirm_send(self):
        msg_text = self.compose_entry.get("1.0", tk.END).strip()
        if not msg_text:
            messagebox.showwarning("Empty Message", "Message cannot be empty.")
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to send this message?"):
            self.send_message_func(
                                    self.username,              # sender
                                    self.selected_user,         # recipient
                                    msg_text                    # message
                                  )

            # Append to Conversations
            database_time = datetime.now(timezone.utc)

            if self.selected_user in self.Conversations.keys(): # If sending to a Gamer you have talked to before.
                self.Conversations[self.selected_user].append(
                    ["sent", msg_text, database_time]
                )
            else: # If this is the first time you have ever recieved or sent a message to this Gamer.
                self.Conversations[self.selected_user] = []
                self.Conversations[self.selected_user].append(
                    ["sent", msg_text, database_time]
                )

            # Sort messages
            self.Conversations[self.selected_user].sort(key=lambda x: x[2], reverse=True)

            messagebox.showinfo("Sent", "Message sent successfully.")
            self.show_display(1)


if __name__ == "__main__":
    app = App()
    app.mainloop()