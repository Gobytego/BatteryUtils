import tkinter as tk
from tkinter import ttk, messagebox
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

    def __init__(self, master):
        self.master = master
        master.title("Battery Calculator")

        self.load_settings()

        # --- Input Frame ---
        self.input_frame = ttk.Frame(master)
        self.input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="new")

        # --- Results and Breakdown Frame ---
        self.results_frame = ttk.Frame(master)
        self.results_frame.grid(row=0, column=1, padx=10, pady=10, sticky="new")

        # --- Battery Information ---
        ttk.Label(self.input_frame, text="--- Battery Info ---").grid(row=0, column=0, columnspan=2, pady=5)
        ttk.Label(self.input_frame, text="Nominal Voltage (V):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.voltage_entry = ttk.Entry(self.input_frame, width=15)
        self.voltage_entry.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        self.voltage_entry.bind("<FocusOut>", self.update_voltage_info_labels)
        self.voltage_entry.bind("<KeyRelease>", self.update_voltage_info_labels) # Update as user types
        if self.settings.get("voltage"):
            self.voltage_entry.insert(0, self.settings["voltage"])

        # Cells in Series (S) - initially hidden, shown if nominal voltage is unknown
        self.series_cells_label = ttk.Label(self.input_frame, text="Cells in Series (S):")
        self.series_cells_entry = ttk.Entry(self.input_frame, width=15)
        self.series_cells_entry.bind("<FocusOut>", self.update_voltage_info_labels)
        self.series_cells_entry.bind("<KeyRelease>", self.update_voltage_info_labels)
        if self.settings.get("series_cells"): # Load if previously saved
            self.series_cells_entry.insert(0, self.settings["series_cells"])

        # Info labels for min/max voltage based on series cells
        self.max_voltage_info_label = ttk.Label(self.input_frame, text="Full Charge V: N/A")
        self.max_voltage_info_label.grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.min_voltage_info_label = ttk.Label(self.input_frame, text="Empty V: N/A")
        self.min_voltage_info_label.grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Initial call to set visibility and labels
        self.update_voltage_info_labels()

        ttk.Label(self.input_frame, text="Capacity Type:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.capacity_type_combo = ttk.Combobox(self.input_frame, values=["Wh", "Ah"], width=13)
        self.capacity_type_combo.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)
        self.capacity_type_combo.set(self.settings.get("capacity_type", "Wh"))
        self.capacity_type_combo.bind("<<ComboboxSelected>>", self.update_capacity_label)

        self.capacity_label_text = tk.StringVar()
        ttk.Label(self.input_frame, textvariable=self.capacity_label_text).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.capacity_entry = ttk.Entry(self.input_frame, width=15)
        self.capacity_entry.grid(row=6, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("capacity"):
            self.capacity_entry.insert(0, self.settings["capacity"])
        self.update_capacity_label()


        # --- Charging Information ---
        ttk.Label(self.input_frame, text="--- Charging ---").grid(row=7, column=0, columnspan=2, pady=5)
        ttk.Label(self.input_frame, text="Charger Rate (A):").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.charge_rate_entry = ttk.Entry(self.input_frame, width=15)
        self.charge_rate_entry.grid(row=8, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("charge_rate"):
            self.charge_rate_entry.insert(0, self.settings["charge_rate"])

        # --- Current Battery State Input Choice ---
        self.charge_input_method = tk.StringVar(value=self.settings.get("charge_input_method", "percentage"))

        self.radio_frame = ttk.Frame(self.input_frame)
        self.radio_frame.grid(row=9, column=0, columnspan=2, pady=5)

        self.percent_radio = ttk.Radiobutton(self.radio_frame, text="Current Percentage (%)", variable=self.charge_input_method, value="percentage", command=self.toggle_charge_input)
        self.percent_radio.pack(side=tk.LEFT, padx=5)

        self.voltage_radio = ttk.Radiobutton(self.radio_frame, text="Current Voltage (V)", variable=self.charge_input_method, value="voltage", command=self.toggle_charge_input)
        self.voltage_radio.pack(side=tk.LEFT, padx=5)

        self.current_percentage_label = ttk.Label(self.input_frame, text="Current Percentage (%):")
        self.current_percentage_label.grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
        self.current_percentage_entry = ttk.Entry(self.input_frame, width=15)
        self.current_percentage_entry.grid(row=10, column=1, sticky=tk.E, padx=5, pady=5)
        self.current_percentage_entry.insert(0, self.settings.get("current_percentage", "0"))

        self.current_voltage_label = ttk.Label(self.input_frame, text="Current Voltage (V):")
        self.current_voltage_entry = ttk.Entry(self.input_frame, width=15)
        self.current_voltage_entry.insert(0, self.settings.get("current_voltage", ""))

        self.toggle_charge_input() # Call to set initial state based on loaded settings

        # --- Motor Information ---
        ttk.Label(self.input_frame, text="--- Motor Info ---").grid(row=11, column=0, columnspan=2, pady=5)
        ttk.Label(self.input_frame, text="Motor Wattage (W):").grid(row=12, column=0, sticky=tk.W, padx=5, pady=5)
        self.motor_wattage_entry = ttk.Entry(self.input_frame, width=15)
        self.motor_wattage_entry.grid(row=12, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("motor_wattage"):
            self.motor_wattage_entry.insert(0, self.settings["motor_wattage"])

        ttk.Label(self.input_frame, text="Driving Style:").grid(row=13, column=0, sticky=tk.W, padx=5, pady=5)
        self.driving_style_combo = ttk.Combobox(self.input_frame, values=["Agressive", "Casual", "Eco"], width=13)
        self.driving_style_combo.grid(row=13, column=1, sticky=tk.E, padx=5, pady=5)
        self.driving_style_combo.set(self.settings.get("driving_style", "Casual"))

        # --- Buttons ---
        calculate_button = ttk.Button(self.input_frame, text="Calculate", command=self.calculate_all)
        calculate_button.grid(row=14, column=0, columnspan=2, pady=10)

        save_button = ttk.Button(self.input_frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=15, column=0, columnspan=2, pady=5)

        self.clear_button = ttk.Button(self.input_frame, text="Clear", command=self.clear_fields)
        self.clear_button.grid(row=16, column=0, columnspan=2, pady=5)

        # --- Output Labels ---
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

        ttk.Label(self.results_frame, text="Miles/Wh:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.miles_per_wh_label = ttk.Label(self.results_frame, text="")
        self.miles_per_wh_label.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)

        ttk.Label(self.results_frame, text="Miles/Ah:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
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

        ttk.Label(self.results_frame, text="Charge Rate:").grid(row=14, column=0, sticky=tk.W, padx=5)
        self.breakdown_charge_rate_label = ttk.Label(self.results_frame, text="")
        self.breakdown_charge_rate_label.grid(row=14, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Current State %:").grid(row=15, column=0, sticky=tk.W, padx=5)
        self.breakdown_current_state_percent_label = ttk.Label(self.results_frame, text="")
        self.breakdown_current_state_percent_label.grid(row=15, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Current State V:").grid(row=16, column=0, sticky=tk.W, padx=5)
        self.breakdown_current_state_voltage_label = ttk.Label(self.results_frame, text="")
        self.breakdown_current_state_voltage_label.grid(row=16, column=1, sticky=tk.E, padx=5)

        # --- Emojis ---
        emoji_label = ttk.Label(self.results_frame, text="🚲🔋🛴", font=("Arial", 30))
        emoji_label.grid(row=17, column=0, columnspan=2, pady=10)

        # --- Padding and Weight ---
        for i in range(18):
            self.results_frame.grid_rowconfigure(i, weight=1)
        self.results_frame.grid_columnconfigure(1, weight=1)
        self.input_frame.grid_columnconfigure(1, weight=1)

        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(0, weight=1)

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
                self.series_cells_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
                self.series_cells_entry.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)
                self.min_voltage_info_label.config(text="Empty V: N/A")
                self.max_voltage_info_label.config(text="Full Charge V: N/A")
                return # Exit early, as we need S from manual input now

        except ValueError:
            # Handle cases where nominal voltage input is not a valid number
            inferred_s = None
            self.series_cells_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            self.series_cells_entry.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)
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
            self.current_percentage_label.grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
            self.current_percentage_entry.grid(row=10, column=1, sticky=tk.E, padx=5, pady=5)
            self.current_voltage_label.grid_forget()
            self.current_voltage_entry.grid_forget()
        else: # selected_method == "voltage"
            self.current_percentage_label.grid_forget()
            self.current_percentage_entry.grid_forget()
            self.current_voltage_label.grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
            self.current_voltage_entry.grid(row=10, column=1, sticky=tk.E, padx=5, pady=5)

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
            motor_wattage = float(self.motor_wattage_entry.get())
            driving_style = self.driving_style_combo.get()
            
            min_v, max_v, series_cells = self.get_derived_voltage_range_and_s() # Get S from here
            if series_cells is None: # Error handled by get_derived_voltage_range_and_s
                return

            if nominal_voltage <= 0 or capacity <= 0 or motor_wattage <= 0:
                messagebox.showerror("Error", "Please enter valid positive numbers for nominal voltage, capacity, and motor wattage.")
                return

            if capacity_type == "Wh":
                total_energy_wh = capacity
                try:
                    total_capacity_ah = total_energy_wh / nominal_voltage # Use nominal voltage for Ah calculation
                except ZeroDivisionError:
                    total_capacity_ah = 0
            else:  # capacity_type == "Ah"
                total_capacity_ah = capacity
                total_energy_wh = capacity * nominal_voltage # Use nominal voltage for Wh calculation

            # Adjust power consumption based on driving style percentage
            if driving_style == "Agressive":
                power_consumption_w = motor_wattage * 1.0
            elif driving_style == "Casual":
                power_consumption_w = motor_wattage * 0.5
            elif driving_style == "Eco":
                power_consumption_w = motor_wattage * 0.25
            else:
                power_consumption_w = motor_wattage * 0.5 # Default to casual if somehow not selected

            # Calculate estimated runtime in hours at 100% battery
            if power_consumption_w > 0:
                estimated_runtime_full_charge = total_energy_wh / power_consumption_w
            else:
                messagebox.showerror("Error", "Motor wattage must be greater than zero for power consumption.")
                return

            # TEMPORARY EMPIRICAL ADJUSTMENT (based on previous findings)
            estimated_runtime_full_charge /= 2

            # Calibrated miles/hour equivalents based on your feedback
            if driving_style == "Agressive":
                estimated_range = estimated_runtime_full_charge * 18.0
                calculated_unit = "miles"
            elif driving_style == "Casual":
                estimated_range = estimated_runtime_full_charge * 13.5
                calculated_unit = "miles"
            elif driving_style == "Eco":
                estimated_range = estimated_runtime_full_charge * 9.0
                calculated_unit = "miles"
            else:
                estimated_range = 0
                calculated_unit = "unknown"

            self.calculated_range_label.config(text=f"{estimated_range:.2f}")
            self.calculated_range_unit_label.config(text=calculated_unit)

            # Calculate miles per Wh and Ah
            if total_energy_wh > 0:
                miles_per_wh = estimated_range / total_energy_wh
                self.miles_per_wh_label.config(text=f"{miles_per_wh:.2f}")
            else:
                self.miles_per_wh_label.config(text="N/A")

            if total_capacity_ah > 0:
                miles_per_ah = estimated_range / total_capacity_ah
                self.miles_per_ah_label.config(text=f"{miles_per_ah:.2f}")
            else:
                self.miles_per_ah_label.config(text="N/A")

            # Store full charge range for remaining range calculation
            self.full_charge_range = estimated_range
            self.range_unit = calculated_unit

        except ValueError:
            messagebox.showerror("Error", "Invalid input. Please enter numeric values for all relevant fields.")
        except ZeroDivisionError:
            messagebox.showerror("Error", "Nominal voltage, capacity, or motor wattage cannot be zero.")
        except AttributeError:
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

    def save_settings(self):
        try:
            voltage = self.voltage_entry.get()
            # Only save series_cells if it's currently visible/populated (meaning it was manually entered or inferred)
            series_cells = self.series_cells_entry.get() if self.series_cells_entry.winfo_ismapped() else ""
            capacity_type = self.capacity_type_combo.get()
            capacity = self.capacity_entry.get()
            motor_wattage = self.motor_wattage_entry.get()
            driving_style = self.driving_style_combo.get()
            charge_rate = self.charge_rate_entry.get()
            current_percentage = self.current_percentage_entry.get()
            current_voltage = self.current_voltage_entry.get()
            charge_input_method = self.charge_input_method.get()


            settings = {
                "voltage": voltage,
                "series_cells": series_cells,
                "capacity_type": capacity_type,
                "capacity": capacity,
                "motor_wattage": motor_wattage,
                "driving_style": driving_style,
                "charge_rate": charge_rate,
                "current_percentage": current_percentage,
                "current_voltage": current_voltage,
                "charge_input_method": charge_input_method,
            }

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_settings(self):
        self.settings = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load settings: {e}")

    def update_settings_on_close(self):
        self.save_settings()
        self.master.destroy()

    def clear_fields(self):
        self.voltage_entry.delete(0, tk.END)
        self.series_cells_entry.delete(0, tk.END) # Clear new field content
        self.capacity_type_combo.set("Wh")
        self.capacity_entry.delete(0, tk.END)
        self.charge_rate_entry.delete(0, tk.END)
        self.current_percentage_entry.delete(0, tk.END)
        self.current_voltage_entry.delete(0, tk.END)
        self.motor_wattage_entry.delete(0, tk.END)
        self.driving_style_combo.set("Casual")
        self.charge_input_method.set("percentage") # Reset to default
        self.toggle_charge_input() # Update visibility
        self.update_voltage_info_labels() # Re-evaluate and potentially hide series_cells_entry

        self.calculated_range_label.config(text="")
        self.remaining_range_label.config(text="")
        self.remaining_charge_percentage_label.config(text="")
        self.charge_time_label.config(text="")
        self.miles_per_wh_label.config(text="")
        self.miles_per_ah_label.config(text="")
        self.breakdown_voltage_label.config(text="")
        self.breakdown_series_cells_label.config(text="") # New breakdown label
        self.breakdown_min_max_voltage_label.config(text="")
        self.breakdown_ah_label.config(text="")
        self.breakdown_wh_label.config(text="")
        self.breakdown_motor_watts_label.config(text="")
        self.breakdown_charge_rate_label.config(text="")
        self.breakdown_current_state_percent_label.config(text="")
        self.breakdown_current_state_voltage_label.config(text="")


# --- CLI Functionality ---
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

    # Load settings for default values
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load settings for CLI: {e}")

    # Use settings for default values, converting to correct types if necessary
    default_voltage = settings.get('voltage')
    default_series_cells = settings.get('series_cells') # New default
    default_capacity = settings.get('capacity')
    default_charge_rate = settings.get('charge_rate')
    default_motor_wattage = settings.get('motor_wattage')
    default_current_percentage = settings.get('current_percentage', "0")
    default_current_voltage = settings.get('current_voltage')
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

    # Adjust power consumption based on driving style percentage
    power_consumption_w = 0
    if driving_style == "Agressive":
        power_consumption_w = motor_wattage * 1.0
    elif driving_style == "Casual":
        power_consumption_w = motor_wattage * 0.5
    elif driving_style == "Eco":
        power_consumption_w = motor_wattage * 0.25
    else:
        power_consumption_w = motor_wattage * 0.5

    estimated_runtime_full_charge = 0
    if power_consumption_w > 0:
        estimated_runtime_full_charge = total_energy_wh / power_consumption_w
    
    estimated_runtime_full_charge /= 2 # Empirical adjustment

    estimated_range = 0
    calculated_unit = "miles"
    if driving_style == "Agressive":
        estimated_range = estimated_runtime_full_charge * 18.0
    elif driving_style == "Casual":
        estimated_range = estimated_runtime_full_charge * 13.5
    elif driving_style == "Eco":
        estimated_range = estimated_runtime_full_charge * 9.0

    miles_per_wh = estimated_range / total_energy_wh if total_energy_wh > 0 else 0
    miles_per_ah = estimated_range / total_capacity_ah if total_capacity_ah > 0 else 0

    remaining_capacity_ah_to_full = total_capacity_ah * (1 - (current_percentage / 100)) if current_percentage is not None else 0
    estimated_charge_time = remaining_capacity_ah_to_full / charge_rate if charge_rate > 0 else 0
    
    remaining_charge_percentage = 100 - current_percentage if current_percentage is not None else "N/A"
    remaining_range = estimated_range * (current_percentage / 100) if current_percentage is not None else "N/A"


    print("\n--- Results ---")
    print(f"Estimated Range: {estimated_range:.2f} {calculated_unit}")
    print(f"Remaining Range: {remaining_range:.2f} {calculated_unit}")
    print(f"Remaining Charge: {remaining_charge_percentage:.2f}%" if current_percentage is not None else "Remaining Charge: N/A")
    print(f"Estimated Charge Time: {estimated_charge_time:.2f} hours")
    print(f"Miles/Wh: {miles_per_wh:.2f}")
    print(f"Miles/Ah: {miles_per_ah:.2f}")

    print("\n--- Breakdown ---")
    print(f"Nominal Voltage: {nominal_voltage:.1f}V")
    print(f"Cells in Series (S): {series_cells}")
    print(f"Min/Max Voltage (Calculated 0%/100%): {min_battery_voltage_for_calc:.1f}V - {max_battery_voltage_for_calc:.1f}V")
    print(f"Ah: {total_capacity_ah:.2f}Ah")
    print(f"Wh: {total_energy_wh:.2f}Wh")
    print(f"Motor Watts: {motor_wattage:.2f}W")
    print(f"Charge Rate: {charge_rate:.2f}A")
    print(f"Current State Percentage: {current_percentage:.2f}%" if current_percentage is not None else "Current State Percentage: N/A")
    print(f"Current State Voltage: {current_voltage:.2f}V" if current_voltage is not None else "Current State Voltage: N/A")
    print("\n🚲🔋🛴")

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
