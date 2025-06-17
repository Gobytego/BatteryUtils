import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import sys

SETTINGS_FILE = "battery_calculator_settings.json"

class BatteryCalculatorGUI:
    # Universal cell voltage properties for typical Li-ion e-bike batteries
    CELL_VOLTAGE_FULL = 4.2  # Volts per cell at 100% charge
    CELL_VOLTAGE_EMPTY = 3.0 # Volts per cell at 0% charge
    CELL_VOLTAGE_NOMINAL = 3.7 # Nominal Volts per cell (used for inferring S)

    # Map common nominal pack voltages to their typical number of cells in series (S)
    NOMINAL_VOLTAGE_TO_SERIES_CELLS = {
        36: 10, # 10S * 3.7V_nominal = 37.0V
        48: 13, # 13S * 3.7V_nominal = 48.1V
        52: 14, # 14S * 3.7V_nominal = 51.8V
        60: 16, # 16S * 3.7V_nominal = 59.2V
        72: 20, # 20S * 3.7V_nominal = 74.0V
        # Add more mappings as needed
    }

    # Reference Wheel Sizes for Wh/mile interpolation
    SMALL_WHEEL_REF = 10.0  # inches, e.g., for scooters, highly efficient base
    LARGE_WHEEL_REF = 27.5  # inches, user's large wheel size, represents larger e-bikes/motorcycles

    # Average Wh/mile efficiency based on driving style FOR SMALL AND LARGE WHEELS
    # These values are recalibrated based on the user's provided examples.
    SMALL_WHEEL_EFFICIENCY = {
        "Eco": 33.28,       # Updated from Bike 1 (48V*10.4Ah / 15 miles = 33.28 Wh/mile)
        "Casual": 30.0,     # Moderate efficiency for small vehicles (kept original as no new data provided)
        "Agressive": 45.0   # Less efficient for small vehicles (kept original as no new data provided)
    }
    LARGE_WHEEL_EFFICIENCY = {
        "Eco": 41.6,        # Updated from Bike 2 (52V*20Ah / 25 miles = 41.6 Wh/mile)
        "Casual": 65.0,     # Scaled up consistently for larger wheels, more power (kept original)
        "Agressive": 80.0   # Scaled up consistently for larger wheels, more power (kept original)
    }

    MAX_PROFILES = 3 # Maximum number of profiles allowed

    def __init__(self, master):
        self.master = master
        master.title("Battery Calculator")

        # Store all profiles loaded from the settings file
        self.all_profiles = {}
        # Stores the name of the currently active profile
        self.current_profile_name = tk.StringVar(value="Default Profile")

        # --- Main Layout Frames ---
        self.input_frame = ttk.Frame(master)
        self.input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="new")

        self.results_frame = ttk.Frame(master)
        self.results_frame.grid(row=0, column=1, padx=10, pady=10, sticky="new")

        # --- Profile Management Section ---
        self.profile_frame = ttk.LabelFrame(self.input_frame, text="--- Profile Management ---")
        self.profile_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        ttk.Label(self.profile_frame, text="Select Profile:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.profile_combo = ttk.Combobox(self.profile_frame, textvariable=self.current_profile_name, width=20, state="readonly")
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_selection)
        
        self.load_all_profiles() # Load all profiles from file initially
        # Initialize profile combo with current profiles (moved after self.profile_combo creation)
        self.update_profile_combo()

        self.profile_buttons_frame = ttk.Frame(self.profile_frame)
        self.profile_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5)

        ttk.Button(self.profile_buttons_frame, text="New", command=self.create_new_profile).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.profile_buttons_frame, text="Save", command=self.save_current_profile).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.profile_buttons_frame, text="Load", command=lambda: self.load_profile_data(self.current_profile_name.get())).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.profile_buttons_frame, text="Delete", command=self.delete_selected_profile).pack(side=tk.LEFT, padx=2)

        # --- Battery Information ---
        ttk.Label(self.input_frame, text="--- Battery Info ---").grid(row=1, column=0, columnspan=2, pady=5) # Row shifted
        ttk.Label(self.input_frame, text="Nominal Voltage (V):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.voltage_entry = ttk.Entry(self.input_frame, width=15)
        self.voltage_entry.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)
        self.voltage_entry.bind("<FocusOut>", self.update_voltage_info_labels)
        self.voltage_entry.bind("<KeyRelease>", self.update_voltage_info_labels) 

        # Cells in Series (S) - initially hidden, shown if nominal voltage is unknown
        self.series_cells_label = ttk.Label(self.input_frame, text="Cells in Series (S):")
        self.series_cells_entry = ttk.Entry(self.input_frame, width=15)
        self.series_cells_entry.bind("<FocusOut>", self.update_voltage_info_labels)
        self.series_cells_entry.bind("<KeyRelease>", self.update_voltage_info_labels)

        # Info labels for min/max voltage based on series cells
        self.max_voltage_info_label = ttk.Label(self.input_frame, text="Full Charge V: N/A")
        self.max_voltage_info_label.grid(row=4, column=0, sticky=tk.W, padx=5, pady=2) # Row shifted
        self.min_voltage_info_label = ttk.Label(self.input_frame, text="Empty V: N/A")
        self.min_voltage_info_label.grid(row=5, column=0, sticky=tk.W, padx=5, pady=2) # Row shifted
        
        # Initial call to set visibility and labels
        self.update_voltage_info_labels()

        ttk.Label(self.input_frame, text="Capacity Type:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.capacity_type_combo = ttk.Combobox(self.input_frame, values=["Wh", "Ah"], width=13)
        self.capacity_type_combo.grid(row=6, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
        self.capacity_type_combo.set("Wh") # Default for new profiles
        self.capacity_type_combo.bind("<<ComboboxSelected>>", self.update_capacity_label)

        self.capacity_label_text = tk.StringVar()
        ttk.Label(self.input_frame, textvariable=self.capacity_label_text).grid(row=7, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.capacity_entry = ttk.Entry(self.input_frame, width=15)
        self.capacity_entry.grid(row=7, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
        self.update_capacity_label()


        # --- Charging Information ---
        ttk.Label(self.input_frame, text="--- Charging ---").grid(row=8, column=0, columnspan=2, pady=5) # Row shifted
        ttk.Label(self.input_frame, text="Charger Rate (A):").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.charge_rate_entry = ttk.Entry(self.input_frame, width=15)
        self.charge_rate_entry.grid(row=9, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted

        # --- Current Battery State Input Choice ---
        self.charge_input_method = tk.StringVar(value="percentage") # Default for new profiles

        self.radio_frame = ttk.Frame(self.input_frame)
        self.radio_frame.grid(row=10, column=0, columnspan=2, pady=5) # Row shifted

        self.percent_radio = ttk.Radiobutton(self.radio_frame, text="Current Percentage (%)", variable=self.charge_input_method, value="percentage", command=self.toggle_charge_input)
        self.percent_radio.pack(side=tk.LEFT, padx=5)

        self.voltage_radio = ttk.Radiobutton(self.radio_frame, text="Current Voltage (V)", variable=self.charge_input_method, value="voltage", command=self.toggle_charge_input)
        self.voltage_radio.pack(side=tk.LEFT, padx=5)

        self.current_percentage_label = ttk.Label(self.input_frame, text="Current Percentage (%):")
        self.current_percentage_label.grid(row=11, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.current_percentage_entry = ttk.Entry(self.input_frame, width=15)
        self.current_percentage_entry.grid(row=11, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
        self.current_percentage_entry.insert(0, "0")

        self.current_voltage_label = ttk.Label(self.input_frame, text="Current Voltage (V):")
        self.current_voltage_entry = ttk.Entry(self.input_frame, width=15)
        self.current_voltage_entry.insert(0, "")

        self.toggle_charge_input() # Call to set initial state based on default/loaded profile

        # --- Motor and Bike Information ---
        ttk.Label(self.input_frame, text="--- Motor/Bike Info ---").grid(row=12, column=0, columnspan=2, pady=5) # Row shifted
        ttk.Label(self.input_frame, text="Motor Wattage (W):").grid(row=13, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.motor_wattage_entry = ttk.Entry(self.input_frame, width=15)
        self.motor_wattage_entry.grid(row=13, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted

        ttk.Label(self.input_frame, text="Wheel Diameter (in):").grid(row=14, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.wheel_diameter_entry = ttk.Entry(self.input_frame, width=15)
        self.wheel_diameter_entry.grid(row=14, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted

        ttk.Label(self.input_frame, text="Driving Style:").grid(row=15, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
        self.driving_style_combo = ttk.Combobox(self.input_frame, values=["Agressive", "Casual", "Eco"], width=13)
        self.driving_style_combo.grid(row=15, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
        self.driving_style_combo.set("Casual") # Default for new profiles

        # --- Buttons ---
        calculate_button = ttk.Button(self.input_frame, text="Calculate", command=self.calculate_all)
        calculate_button.grid(row=16, column=0, columnspan=2, pady=10) # Row shifted

        # Clear button now only clears fields, not profile.
        self.clear_button = ttk.Button(self.input_frame, text="Clear Fields", command=self.clear_fields)
        self.clear_button.grid(row=17, column=0, columnspan=2, pady=5) # Row shifted

        # --- Output Labels (Results and Breakdown) ---
        ttk.Label(self.results_frame, text="--- Results ---").grid(row=0, column=0, columnspan=2, pady=10)
        ttk.Label(self.results_frame, text="Estimated Range:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.calculated_range_label = ttk.Label(self.results_frame, text="")
        self.calculated_range_label.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        self.calculated_range_unit_label = ttk.Label(self.results_frame, text="miles")

        ttk.Label(self.results_frame, text="Remaining Range:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.remaining_range_label = ttk.Label(self.results_frame, text="")
        self.remaining_range_label.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)
        self.remaining_range_unit_label = ttk.Label(self.results_frame, text="miles")

        ttk.Label(self.results_frame, text="Remaining Charge %:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.remaining_charge_percentage_label = ttk.Label(self.results_frame, text="")
        self.remaining_charge_percentage_label.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5)

        ttk.Label(self.results_frame, text="Estimated Charge Time:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.charge_time_label = ttk.Label(self.results_frame, text="")
        self.charge_time_label.grid(row=4, column=1, sticky=tk.E, padx=5, pady=5)
        ttk.Label(self.results_frame, text="hours").grid(row=4, column=2, sticky=tk.W)

        ttk.Label(self.results_frame, text="Miles/Wh (Adjusted):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.miles_per_wh_label = ttk.Label(self.results_frame, text="")
        self.miles_per_wh_label.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)

        ttk.Label(self.results_frame, text="Miles/Ah (Adjusted):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.miles_per_ah_label = ttk.Label(self.results_frame, text="")
        self.miles_per_ah_label.grid(row=6, column=1, sticky=tk.E, padx=5, pady=5)

        # --- Breakdown Column ---
        ttk.Label(self.results_frame, text="--- Breakdown ---").grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Label(self.results_frame, text="Nominal Voltage:").grid(row=8, column=0, sticky=tk.W, padx=5)
        self.breakdown_voltage_label = ttk.Label(self.results_frame, text="")
        self.breakdown_voltage_label.grid(row=8, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Cells in Series (S):").grid(row=9, column=0, sticky=tk.W, padx=5)
        self.breakdown_series_cells_label = ttk.Label(self.results_frame, text="")
        self.breakdown_series_cells_label.grid(row=9, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Min/Max Voltage (Calculated):").grid(row=10, column=0, sticky=tk.W, padx=5)
        self.breakdown_min_max_voltage_label = ttk.Label(self.results_frame, text="")
        self.breakdown_min_max_voltage_label.grid(row=10, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Ah:").grid(row=11, column=0, sticky=tk.W, padx=5)
        self.breakdown_ah_label = ttk.Label(self.results_frame, text="")
        self.breakdown_ah_label.grid(row=11, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Wh:").grid(row=12, column=0, sticky=tk.W, padx=5)
        self.breakdown_wh_label = ttk.Label(self.results_frame, text="")
        self.breakdown_wh_label.grid(row=12, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Motor Watts:").grid(row=13, column=0, sticky=tk.W, padx=5)
        self.breakdown_motor_watts_label = ttk.Label(self.results_frame, text="")
        self.breakdown_motor_watts_label.grid(row=13, column=1, sticky=tk.E, padx=5)
        
        ttk.Label(self.results_frame, text="Wheel Diameter:").grid(row=14, column=0, sticky=tk.W, padx=5)
        self.breakdown_wheel_diameter_label = ttk.Label(self.results_frame, text="")
        self.breakdown_wheel_diameter_label.grid(row=14, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Charge Rate:").grid(row=15, column=0, sticky=tk.W, padx=5)
        self.breakdown_charge_rate_label = ttk.Label(self.results_frame, text="")
        self.breakdown_charge_rate_label.grid(row=15, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Current State %:").grid(row=16, column=0, sticky=tk.W, padx=5)
        self.breakdown_current_state_percent_label = ttk.Label(self.results_frame, text="")
        self.breakdown_current_state_percent_label.grid(row=16, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Current State V:").grid(row=17, column=0, sticky=tk.W, padx=5)
        self.breakdown_current_state_voltage_label = ttk.Label(self.results_frame, text="")
        self.breakdown_current_state_voltage_label.grid(row=17, column=1, sticky=tk.E, padx=5)

        # --- Emojis ---
        emoji_label = ttk.Label(self.results_frame, text="🚲🔋🛴", font=("Arial", 30))
        emoji_label.grid(row=18, column=0, columnspan=2, pady=10)

        # --- Attribution ---
        attribution_label = ttk.Label(self.results_frame, text="Made by Adam of Gobytego", font=("Arial", 10, "italic"))
        attribution_label.grid(row=19, column=0, columnspan=2, pady=5)


        # --- Padding and Weight ---
        for i in range(20): # Adjusted for new breakdown label and attribution
            self.results_frame.grid_rowconfigure(i, weight=1)
        self.results_frame.grid_columnconfigure(1, weight=1)
        self.input_frame.grid_columnconfigure(1, weight=1)

        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(0, weight=1)

        # Load data for the initial profile (either last active or default)
        self.load_profile_data(self.current_profile_name.get())


    def load_all_profiles(self):
        """Loads all profiles from the settings file."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    self.all_profiles = data.get("profiles", {})
                    # Set the last active profile if available, otherwise default
                    last_active = data.get("last_active_profile")
                    if last_active and last_active in self.all_profiles:
                        self.current_profile_name.set(last_active)
                    elif self.all_profiles: # If there are profiles but no last_active, pick the first one
                        self.current_profile_name.set(list(self.all_profiles.keys())[0])
                    else: # No profiles at all, create a default one
                        self.all_profiles["Default Profile"] = self._get_default_profile_settings()
                        self.current_profile_name.set("Default Profile")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load settings: {e}\nCreating a new default profile.")
                self.all_profiles = {"Default Profile": self._get_default_profile_settings()}
                self.current_profile_name.set("Default Profile")
        else:
            self.all_profiles = {"Default Profile": self._get_default_profile_settings()}
            self.current_profile_name.set("Default Profile")
        
        # self.update_profile_combo() # This call was moved to after self.profile_combo creation


    def _get_default_profile_settings(self):
        """Returns a dictionary with default settings for a new profile."""
        return {
            "voltage": "",
            "series_cells": "",
            "capacity_type": "Wh",
            "capacity": "",
            "charge_rate": "",
            "current_percentage": "0",
            "current_voltage": "",
            "charge_input_method": "percentage",
            "motor_wattage": "",
            "wheel_diameter": "",
            "driving_style": "Casual"
        }

    def update_profile_combo(self):
        """Updates the profile selection combobox with current profile names."""
        self.profile_combo['values'] = list(self.all_profiles.keys())
        # Ensure the currently selected value is still in the list, or default
        if self.current_profile_name.get() not in self.all_profiles:
            if self.all_profiles:
                self.current_profile_name.set(list(self.all_profiles.keys())[0])
            else:
                self.current_profile_name.set("Default Profile") # Should not happen if a default is always created
        self.profile_combo.set(self.current_profile_name.get()) # Refresh display


    def load_profile_data(self, profile_name):
        """Loads the settings for the given profile name into the GUI fields."""
        if profile_name not in self.all_profiles:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.")
            return

        settings = self.all_profiles[profile_name]
        self.clear_fields(keep_profile_name=True) # Clear current display but keep profile name

        # Populate fields from the loaded settings
        self.voltage_entry.insert(0, settings.get("voltage", ""))
        self.series_cells_entry.insert(0, settings.get("series_cells", ""))
        self.capacity_type_combo.set(settings.get("capacity_type", "Wh"))
        self.capacity_entry.insert(0, settings.get("capacity", ""))
        self.charge_rate_entry.insert(0, settings.get("charge_rate", ""))
        self.current_percentage_entry.insert(0, settings.get("current_percentage", "0"))
        self.current_voltage_entry.insert(0, settings.get("current_voltage", ""))
        self.motor_wattage_entry.insert(0, settings.get("motor_wattage", ""))
        self.wheel_diameter_entry.insert(0, settings.get("wheel_diameter", ""))
        self.driving_style_combo.set(settings.get("driving_style", "Casual"))
        self.charge_input_method.set(settings.get("charge_input_method", "percentage"))

        self.update_capacity_label() # Ensure correct label for capacity
        self.toggle_charge_input() # Ensure correct visibility of charge input fields
        self.update_voltage_info_labels() # Ensure correct visibility/info for series cells/voltage


    def on_profile_selection(self, event):
        """Callback when a new profile is selected from the combobox."""
        selected_profile = self.current_profile_name.get()
        if selected_profile:
            self.load_profile_data(selected_profile)


    def save_current_profile(self):
        """Saves the current GUI field values into the active profile."""
        profile_name = self.current_profile_name.get()
        current_settings = {
            "voltage": self.voltage_entry.get(),
            "series_cells": self.series_cells_entry.get() if self.series_cells_entry.winfo_ismapped() else "", # Only save if visible
            "capacity_type": self.capacity_type_combo.get(),
            "capacity": self.capacity_entry.get(),
            "charge_rate": self.charge_rate_entry.get(),
            "current_percentage": self.current_percentage_entry.get(),
            "current_voltage": self.current_voltage_entry.get(),
            "charge_input_method": self.charge_input_method.get(),
            "motor_wattage": self.motor_wattage_entry.get(),
            "wheel_diameter": self.wheel_diameter_entry.get(),
            "driving_style": self.driving_style_combo.get(),
        }
        self.all_profiles[profile_name] = current_settings
        self._save_all_profiles_to_file(profile_name)
        messagebox.showinfo("Success", f"Profile '{profile_name}' saved successfully!")

    def _save_all_profiles_to_file(self, last_active_profile_name):
        """Saves the entire self.all_profiles dictionary to the settings file."""
        try:
            data_to_save = {
                "profiles": self.all_profiles,
                "last_active_profile": last_active_profile_name
            }
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save all profiles: {e}")


    def create_new_profile(self):
        """Prompts for a new profile name and creates it."""
        if len(self.all_profiles) >= self.MAX_PROFILES:
            messagebox.showwarning("Profile Limit", f"You can only have up to {self.MAX_PROFILES} profiles.")
            return

        new_name = simpledialog.askstring("New Profile", "Enter a name for the new profile:")
        if new_name:
            new_name = new_name.strip()
            if not new_name:
                messagebox.showerror("Invalid Name", "Profile name cannot be empty.")
                return
            if new_name in self.all_profiles:
                messagebox.showerror("Duplicate Name", f"Profile '{new_name}' already exists. Please choose a different name.")
                return

            self.all_profiles[new_name] = self._get_default_profile_settings()
            self.current_profile_name.set(new_name)
            self.update_profile_combo()
            self.load_profile_data(new_name) # Load the (empty) new profile data
            self.save_current_profile() # Immediately save the new (empty) profile
            messagebox.showinfo("New Profile", f"Profile '{new_name}' created.")


    def delete_selected_profile(self):
        """Deletes the currently selected profile."""
        profile_to_delete = self.current_profile_name.get()
        if profile_to_delete == "Default Profile" and len(self.all_profiles) == 1:
            messagebox.showwarning("Cannot Delete", "The 'Default Profile' cannot be deleted if it's the only profile.")
            return
        if profile_to_delete not in self.all_profiles:
            messagebox.showerror("Error", "No profile selected or profile not found for deletion.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{profile_to_delete}'? This cannot be undone."):
            del self.all_profiles[profile_to_delete]
            self.update_profile_combo() # Remove from combobox
            self._save_all_profiles_to_file(self.current_profile_name.get()) # Save changes

            # If the deleted profile was the active one, switch to another or default
            if profile_to_delete == self.current_profile_name.get():
                if self.all_profiles:
                    first_profile = list(self.all_profiles.keys())[0]
                    self.current_profile_name.set(first_profile)
                    self.load_profile_data(first_profile)
                else:
                    # Should not happen if "Default Profile" is always kept
                    self.all_profiles["Default Profile"] = self._get_default_profile_settings()
                    self.current_profile_name.set("Default Profile")
                    self.load_profile_data("Default Profile")
            
            messagebox.showinfo("Deleted", f"Profile '{profile_to_delete}' deleted.")


    def update_voltage_info_labels(self, event=None):
        nominal_voltage_str = self.voltage_entry.get()
        inferred_s = None

        try:
            nominal_voltage_float = float(nominal_voltage_str)
            # Try to infer S from nominal voltage
            inferred_s = self.NOMINAL_VOLTAGE_TO_SERIES_CELLS.get(int(round(nominal_voltage_float)))
            
            # If a common nominal voltage matches, hide the series cells input
            if inferred_s is not None:
                self.series_cells_label.grid_forget()
                self.series_cells_entry.grid_forget()
                # Update series_cells_entry with the inferred value, so it gets saved correctly
                self.series_cells_entry.delete(0, tk.END)
                self.series_cells_entry.insert(0, str(inferred_s))
            else:
                # If nominal voltage not found in map, show the series cells input
                self.series_cells_label.grid(row=3, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
                self.series_cells_entry.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
                self.min_voltage_info_label.config(text="Empty V: N/A")
                self.max_voltage_info_label.config(text="Full Charge V: N/A")
                return # Exit early, as we need S from manual input now

        except ValueError:
            # Handle cases where nominal voltage input is not a valid number
            inferred_s = None
            self.series_cells_label.grid(row=3, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
            self.series_cells_entry.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
            self.min_voltage_info_label.config(text="Empty V: N/A")
            self.max_voltage_info_label.config(text="Full Charge V: N/A")
            return # Exit early, as we need S from manual input now

        # Now, use the inferred_s or try to get it from the manual entry if it was visible
        series_cells = inferred_s
        if series_cells is None: # If not inferred, try to get from manual entry
            try:
                series_cells = int(self.series_cells_entry.get())
            except ValueError:
                series_cells = None

        if series_cells is not None and series_cells > 0:
            min_v = series_cells * self.CELL_VOLTAGE_EMPTY
            max_v = series_cells * self.CELL_VOLTAGE_FULL
            self.min_voltage_info_label.config(text=f"Empty V: {min_v:.1f} (0%)")
            self.max_voltage_info_label.config(text=f"Full Charge V: {max_v:.1f} (100%)")
        else:
            self.min_voltage_info_label.config(text="Empty V: N/A")
            self.max_voltage_info_label.config(text="Full Charge V: N/A")


    def toggle_charge_input(self):
        selected_method = self.charge_input_method.get()
        if selected_method == "percentage":
            self.current_percentage_label.grid(row=11, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
            self.current_percentage_entry.grid(row=11, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted
            self.current_voltage_label.grid_forget()
            self.current_voltage_entry.grid_forget()
        else: # selected_method == "voltage"
            self.current_percentage_label.grid_forget()
            self.current_percentage_entry.grid_forget()
            self.current_voltage_label.grid(row=11, column=0, sticky=tk.W, padx=5, pady=5) # Row shifted
            self.current_voltage_entry.grid(row=11, column=1, sticky=tk.E, padx=5, pady=5) # Row shifted

    def update_capacity_label(self, event=None):
        selected_type = self.capacity_type_combo.get()
        if selected_type == "Wh":
            self.capacity_label_text.set("Battery Capacity (Wh):")
        elif selected_type == "Ah":
            self.capacity_label_text.set("Battery Capacity (Ah):")

    def calculate_all(self):
        self.calculate_range()
        self.calculate_charge_time_and_remaining_range()
        self.update_breakdown()

    def get_derived_voltage_range_and_s(self):
        """Calculates min and max voltage and the series cell count based on user input (inferred or manual)."""
        series_cells = None
        nominal_voltage_str = self.voltage_entry.get()

        try:
            nominal_voltage_float = float(nominal_voltage_str)
            # Try to infer S from nominal voltage first
            series_cells = self.NOMINAL_VOLTAGE_TO_SERIES_CELLS.get(int(round(nominal_voltage_float)))
            
            if series_cells is None: # If not inferred, try to get from the manual entry
                series_cells = int(self.series_cells_entry.get())
                if series_cells <= 0:
                    messagebox.showerror("Input Error", "Number of Cells in Series (S) must be a positive integer.")
                    return None, None, None # min_v, max_v, S
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numbers for Nominal Voltage and, if prompted, Cells in Series (S).")
            return None, None, None

        if series_cells is None or series_cells <= 0:
            messagebox.showerror("Input Error", "Could not determine Cells in Series (S). Please ensure Nominal Voltage is a common value or manually enter Cells in Series (S).")
            return None, None, None

        min_voltage = series_cells * self.CELL_VOLTAGE_EMPTY
        max_voltage = series_cells * self.CELL_VOLTAGE_FULL
        return min_voltage, max_voltage, series_cells

    def get_current_battery_percentage(self):
        selected_method = self.charge_input_method.get()
        
        min_voltage, max_voltage, series_cells = self.get_derived_voltage_range_and_s()
        if min_voltage is None or max_voltage is None: # Error already handled by get_derived_voltage_range_and_s
            return None, None # Return None for both percentage and current_voltage

        if selected_method == "percentage":
            try:
                percent = float(self.current_percentage_entry.get())
                if not 0 <= percent <= 100:
                    messagebox.showerror("Input Error", "Current percentage must be between 0 and 100.")
                    return None, None
                
                # Estimate current voltage from percentage
                estimated_current_voltage = min_voltage + (percent / 100) * (max_voltage - min_voltage)
                return percent, estimated_current_voltage

            except ValueError:
                messagebox.showerror("Input Error", "Please enter a valid number for current percentage.")
                return None, None
        else: # selected_method == "voltage"
            try:
                current_voltage = float(self.current_voltage_entry.get())

                if not (min_voltage <= current_voltage <= max_voltage):
                    messagebox.showwarning("Input Warning", f"Current Voltage {current_voltage:.1f}V is outside the typical range ({min_voltage:.1f}V - {max_voltage:.1f}V) for your battery. Calculation might be inaccurate.")

                # Linear approximation of percentage from voltage
                voltage_range_diff = max_voltage - min_voltage
                if voltage_range_diff > 0:
                    percentage = ((current_voltage - min_voltage) / voltage_range_diff) * 100
                    percent = max(0, min(100, percentage)) # Clamp between 0 and 100
                else:
                    percent = 0 if current_voltage <= min_voltage else 100 # Handle edge case if range is zero or invalid
                    messagebox.showwarning("Warning", "Battery's calculated min and max voltage are the same or invalid for percentage calculation.")

                return percent, current_voltage
            except ValueError:
                messagebox.showerror("Input Error", "Please enter a valid number for current voltage.")
                return None, None


    def update_breakdown(self):
        nominal_voltage = self.voltage_entry.get()
        capacity_type = self.capacity_type_combo.get()
        capacity = self.capacity_entry.get()
        motor_wattage = self.motor_wattage_entry.get()
        wheel_diameter = self.wheel_diameter_entry.get() # Get wheel diameter for breakdown
        charge_rate = self.charge_rate_entry.get()

        self.breakdown_voltage_label.config(text=nominal_voltage)

        min_v, max_v, series_cells = self.get_derived_voltage_range_and_s()
        if series_cells is not None:
            self.breakdown_series_cells_label.config(text=f"{series_cells}S")
        else:
            self.breakdown_series_cells_label.config(text="N/A")

        if min_v is not None and max_v is not None:
            self.breakdown_min_max_voltage_label.config(text=f"{min_v:.1f}V - {max_v:.1f}V")
        else:
            self.breakdown_min_max_voltage_label.config(text="N/A")

        try:
            float_nominal_voltage = float(nominal_voltage)
            float_capacity = float(capacity)
            if capacity_type == "Ah":
                self.breakdown_ah_label.config(text=f"{float_capacity:.2f}")
                wh = float_capacity * float_nominal_voltage
                self.breakdown_wh_label.config(text=f"{wh:.2f}")
            else: # Wh
                self.breakdown_wh_label.config(text=f"{float_capacity:.2f}")
                ah = float_capacity / float_nominal_voltage if float_nominal_voltage > 0 else 0
                self.breakdown_ah_label.config(text=f"{ah:.2f}")
        except ValueError:
            self.breakdown_ah_label.config(text="N/A")
            self.breakdown_wh_label.config(text="N/A")
        except ZeroDivisionError:
            self.breakdown_ah_label.config(text="Div/0 Error")
            self.breakdown_wh_label.config(text="Div/0 Error")

        self.breakdown_motor_watts_label.config(text=motor_wattage)
        self.breakdown_wheel_diameter_label.config(text=f"{wheel_diameter} in") # Update breakdown label
        self.breakdown_charge_rate_label.config(text=charge_rate)

        current_percentage, actual_current_voltage = self.get_current_battery_percentage()
        if current_percentage is not None:
            self.breakdown_current_state_percent_label.config(text=f"{current_percentage:.2f}%")
            if actual_current_voltage is not None:
                self.breakdown_current_state_voltage_label.config(text=f"{actual_current_voltage:.2f}V")
            else:
                self.breakdown_current_state_voltage_label.config(text="N/A")
        else:
            self.breakdown_current_state_percent_label.config(text="N/A")
            self.breakdown_current_state_voltage_label.config(text="N/A")


    def calculate_range(self):
        try:
            nominal_voltage = float(self.voltage_entry.get()) # Nominal voltage
            capacity_type = self.capacity_type_combo.get()
            capacity = float(self.capacity_entry.get())
            driving_style = self.driving_style_combo.get()
            wheel_diameter = float(self.wheel_diameter_entry.get()) # New: Get wheel diameter
            
            if nominal_voltage <= 0 or capacity <= 0 or wheel_diameter <= 0:
                messagebox.showerror("Error", "Please enter valid positive numbers for nominal voltage, capacity, and wheel diameter.")
                return

            if capacity_type == "Wh":
                total_energy_wh = capacity
            else:  # capacity_type == "Ah"
                total_energy_wh = capacity * nominal_voltage # Convert Ah to Wh using nominal voltage

            # --- Calculate Adjusted Wh/mile based on Wheel Diameter and Driving Style ---
            interpolation_factor = (wheel_diameter - self.SMALL_WHEEL_REF) / (self.LARGE_WHEEL_REF - self.SMALL_WHEEL_REF)
            
            # Clamp factor between 0 and 1 to ensure it stays within our defined range
            interpolation_factor = max(0.0, min(1.0, interpolation_factor))

            base_wh_per_mile_small = self.SMALL_WHEEL_EFFICIENCY.get(driving_style)
            base_wh_per_mile_large = self.LARGE_WHEEL_EFFICIENCY.get(driving_style)

            if base_wh_per_mile_small is None or base_wh_per_mile_large is None:
                messagebox.showerror("Error", "Invalid driving style selected for efficiency lookup.")
                return

            adjusted_wh_per_mile = (base_wh_per_mile_small * (1 - interpolation_factor) +
                                   base_wh_per_mile_large * interpolation_factor)

            if adjusted_wh_per_mile <= 0:
                messagebox.showerror("Error", "Calculated efficiency (Wh/mile) must be greater than zero.")
                return

            # Calculate estimated range directly from total Wh and adjusted Wh/mile efficiency
            estimated_range = total_energy_wh / adjusted_wh_per_mile
            calculated_unit = "miles" # Assuming miles for range

            self.calculated_range_label.config(text=f"{estimated_range:.2f}")
            self.calculated_range_unit_label.config(text=calculated_unit)

            # Calculate miles per Wh and Ah based on the chosen efficiency
            miles_per_wh = 1 / adjusted_wh_per_mile
            self.miles_per_wh_label.config(text=f"{miles_per_wh:.2f}")

            miles_per_ah = nominal_voltage / adjusted_wh_per_mile if adjusted_wh_per_mile > 0 else 0
            self.miles_per_ah_label.config(text=f"{miles_per_ah:.2f}")

            # Store full charge range for remaining range calculation
            self.full_charge_range = estimated_range
            self.range_unit = calculated_unit

        except ValueError:
            messagebox.showerror("Error", "Invalid input. Please enter numeric values for all relevant fields.")
        except ZeroDivisionError:
            messagebox.showerror("Error", "Nominal voltage, capacity, wheel diameter, or efficiency cannot be zero.")
        except AttributeError: # Happens if full_charge_range is not yet set
            self.full_charge_range = 0
            self.range_unit = "miles"

    def calculate_charge_time_and_remaining_range(self):
        current_percentage, _ = self.get_current_battery_percentage() # We only need percentage here

        if current_percentage is None:
            self.charge_time_label.config(text="N/A")
            self.remaining_charge_percentage_label.config(text="N/A")
            self.remaining_range_label.config(text="N/A")
            return

        try:
            nominal_voltage = float(self.voltage_entry.get())
            capacity_type = self.capacity_type_combo.get()
            charge_rate = float(self.charge_rate_entry.get())
            capacity = float(self.capacity_entry.get())
            
            min_v, max_v, series_cells = self.get_derived_voltage_range_and_s() # Get S from here
            if series_cells is None: # Error handled by get_derived_voltage_range_and_s
                return


            capacity_ah = 0
            if capacity_type == "Wh":
                capacity_ah = capacity / nominal_voltage if nominal_voltage > 0 else 0
            else:
                capacity_ah = capacity

            if charge_rate <= 0:
                messagebox.showerror("Error", "Charger rate must be a positive number.")
                self.charge_time_label.config(text="N/A")
                self.remaining_charge_percentage_label.config(text="N/A")
                self.remaining_range_label.config(text="N/A")
                return

            remaining_capacity_ah_to_full = capacity_ah * (1 - (current_percentage / 100))
            estimated_charge_time = remaining_capacity_ah_to_full / charge_rate
            self.charge_time_label.config(text=f"{estimated_charge_time:.2f}")

            self.remaining_charge_percentage_label.config(text=f"{100 - current_percentage:.2f}%")

            if hasattr(self, 'full_charge_range'):
                remaining_range = self.full_charge_range * (current_percentage / 100)
                self.remaining_range_label.config(text=f"{remaining_range:.2f}")
                self.remaining_range_unit_label.config(text=self.range_unit)
            else:
                self.remaining_range_label.config(text="N/A")

        except ValueError:
            messagebox.showerror("Error", "Invalid input for charging information.")
            self.charge_time_label.config(text="N/A")
            self.remaining_charge_percentage_label.config(text="N/A")
            self.remaining_range_label.config(text="N/A")
        except ZeroDivisionError:
            messagebox.showerror("Error", "Nominal voltage or charge rate cannot be zero in these calculations.")
            self.charge_time_label.config(text="N/A")
            self.remaining_charge_percentage_label.config(text="N/A")
            self.remaining_range_label.config(text="N/A")

    def update_settings_on_close(self):
        # Save the current profile before closing
        self.save_current_profile() 
        self.master.destroy()

    def clear_fields(self, keep_profile_name=False):
        """Clears all input fields, and output labels.
           If keep_profile_name is True, the profile selection is not reset."""
        # Clear input entries
        self.voltage_entry.delete(0, tk.END)
        self.series_cells_entry.delete(0, tk.END) 
        self.capacity_entry.delete(0, tk.END)
        self.charge_rate_entry.delete(0, tk.END)
        self.current_percentage_entry.delete(0, tk.END)
        self.current_voltage_entry.delete(0, tk.END)
        self.motor_wattage_entry.delete(0, tk.END)
        self.wheel_diameter_entry.delete(0, tk.END) 
        
        # Reset comboboxes and radiobuttons to default values
        self.capacity_type_combo.set("Wh")
        self.driving_style_combo.set("Casual")
        self.charge_input_method.set("percentage") 
        
        # Update visibility and info labels based on cleared/default states
        self.toggle_charge_input() 
        self.update_capacity_label()
        self.update_voltage_info_labels()

        # Clear output labels
        self.calculated_range_label.config(text="")
        self.remaining_range_label.config(text="")
        self.remaining_charge_percentage_label.config(text="")
        self.charge_time_label.config(text="")
        self.miles_per_wh_label.config(text="")
        self.miles_per_ah_label.config(text="")
        self.breakdown_voltage_label.config(text="")
        self.breakdown_series_cells_label.config(text="") 
        self.breakdown_min_max_voltage_label.config(text="")
        self.breakdown_ah_label.config(text="")
        self.breakdown_wh_label.config(text="")
        self.breakdown_motor_watts_label.config(text="")
        self.breakdown_wheel_diameter_label.config(text="") 
        self.breakdown_charge_rate_label.config(text="")
        self.breakdown_current_state_percent_label.config(text="")
        self.breakdown_current_state_voltage_label.config(text="")


# --- CLI Functionality (Remains single-profile for simplicity) ---
def get_cli_input(prompt, default_value=None, type_cast=str, validation_func=None, error_message="Invalid input.", default_text_if_none="N/A"):
    while True:
        try:
            display_default = f" [{default_value if default_value is not None else default_text_if_none}]"
            user_input = input(f"{prompt}{display_default}: ").strip()

            # Handle empty input with default value
            if user_input == "" and default_value is not None:
                user_input = str(default_value) # Ensure default is string for type_cast
            elif user_input == "" and default_value is None: # If no default and empty, consider it None/empty
                return None

            value = type_cast(user_input)
            if validation_func and not validation_func(value):
                print(error_message)
                continue
            return value
        except ValueError:
            print(error_message)
        except KeyboardInterrupt:
            print("\nExiting CLI calculator.")
            sys.exit(0)

def run_cli_calculator():
    print("\n--- Battery Calculator (CLI Mode) ---")

    # Universal cell voltage properties for typical Li-ion e-bike batteries
    CELL_VOLTAGE_FULL_CLI = 4.2  # Volts per cell at 100% charge
    CELL_VOLTAGE_EMPTY_CLI = 3.0 # Volts per cell at 0% charge
    CELL_VOLTAGE_NOMINAL_CLI = 3.7 # Nominal Volts per cell (used for inferring S)

    # Map common nominal pack voltages to their typical number of cells in series (S)
    NOMINAL_VOLTAGE_TO_SERIES_CELLS_CLI = {
        36: 10,
        48: 13,
        52: 14,
        60: 16,
        72: 20,
    }
    
    # Reference Wheel Sizes for Wh/mile interpolation (CLI specific for self-containment)
    SMALL_WHEEL_REF_CLI = 10.0
    LARGE_WHEEL_REF_CLI = 27.5

    # Average Wh/mile efficiency based on driving style FOR SMALL AND LARGE WHEELS (CLI specific)
    # These values are recalibrated based on the user's provided examples.
    SMALL_WHEEL_EFFICIENCY_CLI = {
        "Eco": 33.28,       # Updated from Bike 1 (48V*10.4Ah / 15 miles = 33.28 Wh/mile)
        "Casual": 30.0,     # Kept original
        "Agressive": 45.0   # Kept original
    }
    LARGE_WHEEL_EFFICIENCY_CLI = {
        "Eco": 41.6,        # Updated from Bike 2 (52V*20Ah / 25 miles = 41.6 Wh/mile)
        "Casual": 65.0,     # Kept original
        "Agressive": 80.0   # Kept original
    }

    # Load settings for default values (CLI still uses the single-profile saving mechanism for simplicity)
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                # CLI only cares about the 'Default Profile' or the last active profile data
                # For simplicity in CLI, we'll extract the 'Default Profile' if it exists,
                # otherwise it will behave like the original single-profile CLI.
                loaded_data = json.load(f)
                profiles_data = loaded_data.get("profiles", {})
                last_active_profile_name = loaded_data.get("last_active_profile")

                if last_active_profile_name and last_active_profile_name in profiles_data:
                    settings = profiles_data.get(last_active_profile_name, {})
                elif "Default Profile" in profiles_data:
                    settings = profiles_data.get("Default Profile", {})
                else: # No profiles or no default/last active, use empty settings
                    settings = {}
        except Exception as e:
            print(f"Warning: Failed to load CLI settings: {e}")

    # Use settings for default values, converting to correct types if necessary
    # Provide sensible defaults if settings are not found
    default_voltage = settings.get('voltage', '')
    # Ensure default_voltage is convertable if not empty
    try: default_voltage = float(default_voltage) if default_voltage else None
    except ValueError: default_voltage = None

    default_series_cells = settings.get('series_cells', '')
    try: default_series_cells = int(default_series_cells) if default_series_cells else None
    except ValueError: default_series_cells = None

    default_capacity = settings.get('capacity', '')
    try: default_capacity = float(default_capacity) if default_capacity else None
    except ValueError: default_capacity = None

    default_charge_rate = settings.get('charge_rate', '')
    try: default_charge_rate = float(default_charge_rate) if default_charge_rate else None
    except ValueError: default_charge_rate = None

    default_motor_wattage = settings.get('motor_wattage', '')
    try: default_motor_wattage = float(default_motor_wattage) if default_motor_wattage else None
    except ValueError: default_motor_wattage = None

    default_wheel_diameter = settings.get('wheel_diameter', '')
    try: default_wheel_diameter = float(default_wheel_diameter) if default_wheel_diameter else None
    except ValueError: default_wheel_diameter = None

    default_current_percentage = settings.get('current_percentage', "0")
    try: default_current_percentage = float(default_current_percentage) if default_current_percentage else 0.0 # Default to 0.0 if cannot convert
    except ValueError: default_current_percentage = 0.0

    default_current_voltage = settings.get('current_voltage', '')
    try: default_current_voltage = float(default_current_voltage) if default_current_voltage else None
    except ValueError: default_current_voltage = None

    default_capacity_type = settings.get('capacity_type', 'Wh')
    default_driving_style = settings.get('driving_style', 'Casual')
    default_charge_input_method = settings.get('charge_input_method', 'percentage')

    # --- Input Gathering ---
    nominal_voltage = get_cli_input("Enter Battery Nominal Voltage (V, e.g., 48, 52)", default_voltage, float, 
                                    lambda x: x > 0, "Nominal voltage must be a positive number.")
    
    series_cells = None
    if nominal_voltage is not None:
        series_cells = NOMINAL_VOLTAGE_TO_SERIES_CELLS_CLI.get(int(round(nominal_voltage)))

    if series_cells is None:
        print(f"Nominal voltage {nominal_voltage}V not recognized in common types. Please enter Cells in Series (S).")
        series_cells = get_cli_input("Enter Number of Cells in Series (S)", default_series_cells, int, 
                                     lambda x: x > 0, "Number of series cells must be a positive integer.")
        if series_cells is None: # User didn't provide S when prompted
             print("Error: Cells in Series (S) is required for accurate calculations.")
             sys.exit(1)
    
    # Calculate min/max voltage based on series cells
    min_battery_voltage_for_calc = series_cells * CELL_VOLTAGE_EMPTY_CLI
    max_battery_voltage_for_calc = series_cells * CELL_VOLTAGE_FULL_CLI
    print(f"Calculated battery range based on {series_cells}S: Empty {min_battery_voltage_for_calc:.1f}V to Full {max_battery_voltage_for_calc:.1f}V.")

    capacity_type = get_cli_input("Enter Capacity Type (Wh/Ah)", default_capacity_type, str, 
                                lambda x: x.lower() in ["wh", "ah"], "Invalid capacity type. Please enter 'Wh' or 'Ah'.").lower()
    
    capacity = get_cli_input(f"Enter Battery Capacity ({capacity_type})", default_capacity, float, 
                             lambda x: x > 0, "Capacity must be a positive number.")
    
    charge_rate = get_cli_input("Enter Charger Rate (A)", default_charge_rate, float, 
                                lambda x: x > 0, "Charger rate must be a positive number.")
    
    charge_input_method = get_cli_input("Enter Battery State Input Method (percentage/voltage)", default_charge_input_method, str, 
                                        lambda x: x.lower() in ["percentage", "voltage"], "Invalid input method. Enter 'percentage' or 'voltage'.").lower()

    current_percentage = None
    current_voltage = None

    if charge_input_method == "percentage":
        current_percentage = get_cli_input("Enter Current Percentage (%)", default_current_percentage, float, 
                                           lambda x: 0 <= x <= 100, "Current percentage must be between 0 and 100.")
        if current_percentage is not None and max_battery_voltage_for_calc > min_battery_voltage_for_calc:
            current_voltage = min_battery_voltage_for_calc + (current_percentage / 100) * (max_battery_voltage_for_calc - min_battery_voltage_for_calc)
    else: # voltage
        current_voltage = get_cli_input("Enter Current Voltage (V)", default_current_voltage, float, 
                                       lambda x: x >= 0, "Current voltage cannot be negative.")
        if current_voltage is not None:
            if max_battery_voltage_for_calc <= min_battery_voltage_for_calc:
                print("Warning: Cannot calculate percentage from voltage (Calculated min/max voltage range is invalid).")
                current_percentage = None
            else:
                if not (min_battery_voltage_for_calc <= current_voltage <= max_battery_voltage_for_calc):
                    print(f"Warning: Current voltage {current_voltage:.1f}V is outside the typical calculated range [{min_battery_voltage_for_calc:.1f}V - {max_battery_voltage_for_calc:.1f}V].")
                
                percentage = ((current_voltage - min_battery_voltage_for_calc) / (max_battery_voltage_for_calc - min_battery_voltage_for_calc)) * 100
                current_percentage = max(0, min(100, percentage)) # Clamp

    motor_wattage = get_cli_input("Enter Motor Wattage (W)", default_motor_wattage, float, 
                                   lambda x: x > 0, "Motor wattage must be a positive number.")
    
    wheel_diameter = get_cli_input("Enter Wheel Diameter (inches)", default_wheel_diameter, float,
                                    lambda x: x > 0, "Wheel diameter must be a positive number.")

    driving_style = get_cli_input("Enter Driving Style (Agressive/Casual/Eco)", default_driving_style, str, 
                                   lambda x: x.lower() in ["agressive", "casual", "eco"], "Invalid driving style. Please enter 'Agressive', 'Casual', or 'Eco'.").capitalize() # Capitalize for consistency

    # Perform calculations
    total_energy_wh = 0
    total_capacity_ah = 0

    if capacity_type == "wh":
        total_energy_wh = capacity
        try:
            total_capacity_ah = total_energy_wh / nominal_voltage # Use nominal_voltage for this
        except ZeroDivisionError:
            total_capacity_ah = 0
    else:  # capacity_type == "ah"
        total_capacity_ah = capacity
        total_energy_wh = capacity * nominal_voltage # Use nominal_voltage for this

    # --- UPDATED RANGE CALCULATION WITH WHEEL DIAMETER ---
    interpolation_factor = (wheel_diameter - SMALL_WHEEL_REF_CLI) / (LARGE_WHEEL_REF_CLI - SMALL_WHEEL_REF_CLI)
    interpolation_factor = max(0.0, min(1.0, interpolation_factor)) # Clamp between 0 and 1

    base_wh_per_mile_small = SMALL_WHEEL_EFFICIENCY_CLI.get(driving_style)
    base_wh_per_mile_large = LARGE_WHEEL_EFFICIENCY_CLI.get(driving_style)

    if base_wh_per_mile_small is None or base_wh_per_mile_large is None:
        print("Error: Could not determine valid Wh/mile efficiency for the selected driving style.")
        sys.exit(1)

    adjusted_wh_per_mile = (base_wh_per_mile_small * (1 - interpolation_factor) +
                           base_wh_per_mile_large * interpolation_factor)

    if adjusted_wh_per_mile <= 0:
        print("Error: Calculated efficiency (Wh/mile) must be greater than zero.")
        sys.exit(1)

    estimated_range = total_energy_wh / adjusted_wh_per_mile
    calculated_unit = "miles" # Assuming miles for range

    miles_per_wh = 1 / adjusted_wh_per_mile
    miles_per_ah = nominal_voltage / adjusted_wh_per_mile if adjusted_wh_per_mile > 0 else 0

    remaining_capacity_ah_to_full = total_capacity_ah * (1 - (current_percentage / 100)) if current_percentage is not None else 0
    estimated_charge_time = remaining_capacity_ah_to_full / charge_rate if charge_rate > 0 else 0
    
    remaining_charge_percentage = 100 - current_percentage if current_percentage is not None else "N/A"
    remaining_range = estimated_range * (current_percentage / 100) if current_percentage is not None else "N/A"


    print("\n--- Results ---")
    print(f"Estimated Range: {estimated_range:.2f} {calculated_unit}")
    print(f"Remaining Range: {remaining_range:.2f} {calculated_unit}")
    print(f"Remaining Charge: {remaining_charge_percentage:.2f}%" if current_percentage is not None else "Remaining Charge: N/A")
    print(f"Estimated Charge Time: {estimated_charge_time:.2f} hours")
    print(f"Miles/Wh (Adjusted): {miles_per_wh:.2f}")
    print(f"Miles/Ah (Adjusted): {miles_per_ah:.2f}")

    print("\n--- Breakdown ---")
    print(f"Nominal Voltage: {nominal_voltage:.1f}V")
    print(f"Cells in Series (S): {series_cells}")
    print(f"Min/Max Voltage (Calculated 0%/100%): {min_battery_voltage_for_calc:.1f}V - {max_battery_voltage_for_calc:.1f}V")
    print(f"Ah: {total_capacity_ah:.2f}Ah")
    print(f"Wh: {total_energy_wh:.2f}Wh")
    print(f"Motor Watts: {motor_wattage:.2f}W")
    print(f"Wheel Diameter: {wheel_diameter:.1f} inches")
    print(f"Charge Rate: {charge_rate:.2f}A")
    print(f"Current State Percentage: {current_percentage:.2f}%" if current_percentage is not None else "Current State Percentage: N/A")
    print(f"Current State Voltage: {current_voltage:.2f}V" if current_voltage is not None else "Current State Voltage: N/A")
    print("\n🚲🔋🛴")
    print("Made by Adam of Gobytego") # Added attribution for CLI


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_calculator()
    else:
        # Check if a display is available for GUI
        if os.environ.get('DISPLAY') is None and sys.platform.startswith('linux'):
            print("Error: No display found. This application requires a graphical environment.")
            print("If you are using SSH, you may need to enable X11 forwarding, or run with the --cli flag.")
            sys.exit(1)

        root = tk.Tk()
        app = BatteryCalculatorGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.update_settings_on_close)
        root.mainloop()
