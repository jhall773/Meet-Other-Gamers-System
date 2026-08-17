import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from geopy.distance import geodesic

DB_PATH = "US_zip_codes.db"

def load_all_zips():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT zcta5_code FROM zipcodes")
    zips = [row[0] for row in cur.fetchall()]
    conn.close()
    return sorted(zips)

ALL_ZIPS = load_all_zips()

# ---------------------------------------------------------
# Main App Class
# ---------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meet Other Gamers - ZIP Tools")
        self.geometry("600x400")

        # Shared ZIP + State
        self.user_zip = None
        self.user_state = None

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}

        for Page in (Start_Page, ZipLookupPage, RadiusSearchPage):
            page_name = Page.__name__
            frame = Page(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("Start_Page")

    def show_frame(self, page_name):
        # Prevent entering Radius page without a saved ZIP
        if page_name == "RadiusSearchPage" and not self.user_zip:
            messagebox.showerror("Error", "You must select a ZIP Code first that can be associated with your account.")
            self.frames["ZipLookupPage"].tkraise()
            return
        
        frame = self.frames[page_name]

        # If going to RadiusSearchPage, refresh its labels so that it retrieves proper saved zipcode & state
        if page_name == "RadiusSearchPage":
            frame.refresh()
        
        frame.tkraise()

# ---------------------------------------------------------
# Start Page
# ---------------------------------------------------------
class Start_Page(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        ttk.Label(self, text="Meet Other Gamers - ZIP Tools",
                  font=("Arial", 16)).pack(pady=10)

        ttk.Button(self, text="ZIP Code Lookup",
                   command=lambda: controller.show_frame("ZipLookupPage")
                   ).pack(pady=5)

        ttk.Button(self, text="Miles-Radius Search",
                   command=lambda: controller.show_frame("RadiusSearchPage")
                   ).pack(pady=5)

# ---------------------------------------------------------
# ZIP Lookup Page
# ---------------------------------------------------------
class ZipLookupPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="ZIP Code Lookup",
                  font=("Arial", 14)).pack(pady=5)

        # Saved ZIP display
        self.saved_zip_label = ttk.Label(self, text="Saved ZIP Code: None")
        self.saved_zip_label.pack(pady=3)

        ttk.Button(self, text="Back",
                   command=lambda: controller.show_frame("Start_Page")
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

        if typed == "":
            return

        matches = [z for z in ALL_ZIPS if z.startswith(typed)]
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

        if not zip_code:
            messagebox.showerror("Error", "Please enter a ZIP code.")
            return

        conn = sqlite3.connect(DB_PATH)
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

# ---------------------------------------------------------
# Radius Search Page
# ---------------------------------------------------------
class RadiusSearchPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="Miles-Radius Search",
                  font=("Arial", 14)).pack(pady=5)

        # ⭐ Saved zip is initialized to "None" before "ZipLookup Page". But after that, this always refreshes
        #     with the "refresh()" function to match the last saved controller/App() "self.user_zip/state" values.
        self.using_zip_label = ttk.Label(self, text=f"Using ZIP Code: None")
        self.using_zip_label.pack(pady=3)

        ttk.Button(self, text="Back",
                   command=lambda: controller.show_frame("Start_Page")
                   ).pack(anchor="w", padx=10, pady=3)

        # Slider label
        self.radius_label = ttk.Label(self, text="Radius: 0 miles")
        self.radius_label.pack(anchor="w", padx=10)

        # Slider for radius (0–50 miles)
        self.radius_slider = ttk.Scale(self, from_=0, to=50,
                                       orient="horizontal",
                                       command=self.update_radius_label)
        self.radius_slider.pack(anchor="w", padx=10)
        self.radius_slider.configure(length=200)

        ttk.Button(self, text="Search Radius",
                   command=self.search_radius).pack(pady=5)

        # Frame to hold tree + scrollbar
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="left", fill="y")

        # Treeview with scrollbar
        self.tree = ttk.Treeview(tree_frame,
                                columns=("ZIP", "State", "Longitude", "Latitude"),
                                show="headings", height=6,
                                yscrollcommand=scrollbar.set)

        scrollbar.config(command=self.tree.yview)

        self.tree.heading("ZIP", text="ZIP (distance)")
        self.tree.heading("State", text="State")
        self.tree.heading("Longitude", text="Longitude")
        self.tree.heading("Latitude", text="Latitude")

        self.tree.pack(side="left", fill="both", expand=True)

    def refresh(self):
        """Called when the page is shown to update the ZIP label."""
        zip_code = self.controller.user_zip
        state = self.controller.user_state
        self.using_zip_label.config(text=f"Using ZIP Code: {zip_code} ({state})")

    def update_radius_label(self, value):
        miles = round(float(value) / 5) * 5
        self.radius_label.config(text=f"Radius: {miles} miles")

    def search_radius(self):
        # Always pull fresh values from controller
        zip_code = self.controller.user_zip
        state = self.controller.user_state

        # ⭐ Correct label update
        self.using_zip_label.config(text=f"Using ZIP Code: {zip_code} ({state})")

        radius = round(self.radius_slider.get() / 5) * 5

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            SELECT longitude, latitude
            FROM zipcodes
            WHERE zcta5_code = ?
            LIMIT 1
        """, (zip_code,))
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

        results = []
        for z, st, lon, lat in all_rows:
            dist = geodesic(center_point, (lat, lon)).miles
            if dist <= radius:
                results.append((z, st, lon, lat, dist))

        results.sort(key=lambda x: x[4])

        for item in self.tree.get_children():
            self.tree.delete(item)

        for z, st, lon, lat, dist in results:
            self.tree.insert("", "end",
                             values=(f"{z} ({dist:.1f} mi)", st, lon, lat))

# ---------------------------------------------------------
# Run App
# ---------------------------------------------------------
if __name__ == "__main__":
    app = App()
    app.mainloop()