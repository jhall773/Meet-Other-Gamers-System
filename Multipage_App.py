import tkinter as tk
from tkinter import ttk
import pandas as pd
import sqlite3
import os

# Engine For online DB
from supabase import create_client
url = "https://fnfborlpomdjdzycsbzg.supabase.co"
key = "sb_publishable_uIDfGLa8AH1gLEpdseOuDg_OCdut_W_"
supabase_engine = create_client(url, key)

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Multipage Selection + Ranking Demo")
        self.geometry("450x350")

        # Share Username on Start Page
        self.username = ""

        # Shared state
        self.selected_games = []

        # Load previous rankings if database exists
        self.db_path = "rankings.db"
        self.load_rankings_from_db()


        # Container that holds all pages
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        # Dictionary to store page instances
        self.frames = {}

        # Initialize all pages
        for Page in (StartPage, PageOne, PageTwo, PageThree, PageFour, PageFive):
            page_name = Page.__name__
            frame = Page(parent=container, controller=self)
            self.frames[page_name] = frame

            # Stack all pages in the same location
            frame.grid(row=0, column=0, sticky="nsew")

        # Show the first page
        self.show_frame("StartPage")

    def show_frame(self, page_name):
        """Bring a frame to the front"""
        frame = self.frames[page_name]
        frame.tkraise()

    # ----------------------------------------------------------
    # 🔥 Save rankings to SQLite using pandas
    # ----------------------------------------------------------
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


    def save_username_to_db(self):
        from Username_generation_logic import generate_username
        import datetime
        from zoneinfo import ZoneInfo

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

        # Central Time Zone from IANA tz database
        central_tz = ZoneInfo("America/Chicago")
        database_time = datetime.datetime.now(central_tz)

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


# ---------------- START PAGE ----------------

class StartPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Loading and displaying username:
        local_username = self.controller.load_username_from_db()
        if not local_username:
            self.controller.save_username_to_db()
            local_username = self.controller.load_username_from_db()

        ttk.Label(self, text=f"Username: {local_username}", font=("Arial", 15)).pack()

        # Displaying page title:
        ttk.Label(self, text="Start Page", font=("Arial", 18)).pack(pady=20)

        ttk.Button(self, text="Go to Page One",
                   command=lambda: controller.show_frame("PageOne")).pack()

        ttk.Button(self,text="Go to Page 2 (Select Games)",
                   command=lambda: controller.show_frame("PageTwo")).pack()
        
        # Note: Page 3 Automatically follows page 2 if the "Page 2" button is selected. 
        # After you select new games, you must re-rank them.

        ttk.Button(self,text="Go to Page 3 (Rank/Re-Rank Games)",
                   command=lambda: controller.show_frame("PageThree")).pack()
        
        ttk.Button(self,text="Go to Page 4 (View Ranking List)",
                   command=lambda: controller.show_frame("PageFour")).pack()
        
        ttk.Button(self,text="Go to Page 5 (Search for Gamers)",
                   command=lambda: controller.show_frame("PageFive")).pack()


# ---------------- PAGE 1: Blank (TBD) ----------------

class PageOne(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        ttk.Label(self, text="Page One", font=("Arial", 18)).pack(pady=20)

        ttk.Button(self, text="Back to Start",
                   command=lambda: controller.show_frame("StartPage")).pack()


# ---------------- PAGE 2: Choose Game Titles ----------------

class PageTwo(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        # PAGE TITLE
        ttk.Label(self, text="Page 2: Choose Games", font=("Arial", 16)).pack(pady=10)

        # Example list of Game Titles
        self.games = ["Splatoon 3", "Mario Kart 8 Deluxe", "Super Smash Bros. Ultimate", "Fortnite", "Overwatch", "Apex Legends", "Minecraft"]

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

        # ---------------------------------------------------------
        # VALIDATION LABEL (hidden until needed)
        # ---------------------------------------------------------
        self.validation_label = ttk.Label(
            self,
            text="Please complete all rankings",
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

            ttk.Label(row, text=game, width=15).pack(side="left")

            var = tk.StringVar()
            combo = ttk.Combobox(row, textvariable=var, width=5, state="readonly")
            combo.pack(side="left")

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


# ---------------- PAGE 4 ----------------

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
            text="Back to Ranking Page",
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


# ---------------- PAGE 5: Search Page ----------------

class PageFive(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # PAGE TITLE
        ttk.Label(self, text="Page 5: Search for Gamers", font=("Arial", 16)).pack(pady=10)

        # ---------------------------------------------------------
        # LAYOUT: LEFT SETTINGS PANEL + RIGHT RESULTS PANEL
        # ---------------------------------------------------------
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # LEFT SIDE SETTINGS
        settings_frame = ttk.Frame(main)
        settings_frame.pack(side="left", fill="y", padx=10, pady=10)

        ttk.Label(settings_frame, text="Search Settings", font=("Arial", 14)).pack(pady=5)

        ttk.Label(settings_frame, text="How many results:").pack(anchor="w")
        self.num_results = tk.IntVar(value=10)
        ttk.Spinbox(settings_frame, from_=1, to=50, textvariable=self.num_results, width=5).pack(anchor="w")

        ttk.Button(
            settings_frame,
            text="Run Search",
            command=self.run_search
        ).pack(pady=10)

        # Try to display current user's ranking list with the settings
        self.controller.load_rankings_from_db()
        
        if not self.controller.rankings:
            ttk.Label(self.results_frame, text="You have no current rankings to compare").pack()
            return
        
        ttk.Label(settings_frame, text="Your Ranking List:").pack(pady=5)
        for i, item in enumerate(self.controller.rankings, start=1):
            ttk.Label(settings_frame, text=f"{i}. {item}").pack()

        ttk.Button(
            settings_frame,
            text="Back to Start Page",
            command=lambda: controller.show_frame("StartPage")
        ).pack(pady=10)

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

    # ---------------------------------------------------------
    # RUN SEARCH: LOAD DB, COMPUTE SIMILARITY, DISPLAY RESULTS
    # ---------------------------------------------------------
    def run_search(self):
        # Clear old results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Load online DB rankings
        try:
            response = supabase_engine.table("rankings").select("*").execute()
            df = pd.DataFrame(response.data)

        except Exception:
            ttk.Label(self.results_frame, text="No external rankings found").pack()
            return

        if df.empty:
            ttk.Label(self.results_frame, text="No external user rankings found").pack()
            return

        # Current user's ranking list
        self.controller.load_rankings_from_db()
        current = self.controller.rankings
        if not current:
            ttk.Label(self.results_frame, text="You have no current rankings to compare").pack()
            return

        current_list = [item for item, rank in sorted(current.items(), key=lambda x: x[1])]

        # ---------------------------------------------------------
        # GROUP BY USERNAME → build each user's ranked list
        # ---------------------------------------------------------
        results = []

        for external_username in df["username"].unique():
            # 🔥 Skip the current user
            if external_username == self.controller.username:
                continue

            user_rows = df[df["username"] == external_username].sort_values("rank")

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
        score += len(top5_current.intersection(top5_saved)) * 3

        return score


if __name__ == "__main__":
    app = App()
    app.mainloop()