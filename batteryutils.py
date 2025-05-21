import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys

SETTINGS_FILE = "battery_calculator_settings.json"

class BatteryCalculatorGUI:
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
        ttk.Label(self.input_frame, text="Battery Voltage (V):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.voltage_entry = ttk.Entry(self.input_frame, width=15)
        self.voltage_entry.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("voltage"):
            self.voltage_entry.insert(0, self.settings["voltage"])

        ttk.Label(self.input_frame, text="Capacity Type:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.capacity_type_combo = ttk.Combobox(self.input_frame, values=["Wh", "Ah"], width=13)
        self.capacity_type_combo.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)
        self.capacity_type_combo.set(self.settings.get("capacity_type", "Wh"))
        self.capacity_type_combo.bind("<<ComboboxSelected>>", self.update_capacity_label)

        self.capacity_label_text = tk.StringVar()
        ttk.Label(self.input_frame, textvariable=self.capacity_label_text).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.capacity_entry = ttk.Entry(self.input_frame, width=15)
        self.capacity_entry.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("capacity"):
            self.capacity_entry.insert(0, self.settings["capacity"])
        self.update_capacity_label()

        # --- Charging Information ---
        ttk.Label(self.input_frame, text="--- Charging ---").grid(row=4, column=0, columnspan=2, pady=5)
        ttk.Label(self.input_frame, text="Charger Rate (A):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.charge_rate_entry = ttk.Entry(self.input_frame, width=15)
        self.charge_rate_entry.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("charge_rate"):
            self.charge_rate_entry.insert(0, self.settings["charge_rate"])

        ttk.Label(self.input_frame, text="Current Percentage (%):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.current_percentage_entry = ttk.Entry(self.input_frame, width=15)
        self.current_percentage_entry.grid(row=6, column=1, sticky=tk.E, padx=5, pady=5)
        self.current_percentage_entry.insert(0, "0")

        # --- Motor Information ---
        ttk.Label(self.input_frame, text="--- Motor Info ---").grid(row=7, column=0, columnspan=2, pady=5)
        ttk.Label(self.input_frame, text="Motor Wattage (W):").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.motor_wattage_entry = ttk.Entry(self.input_frame, width=15)
        self.motor_wattage_entry.grid(row=8, column=1, sticky=tk.E, padx=5, pady=5)
        if self.settings.get("motor_wattage"):
            self.motor_wattage_entry.insert(0, self.settings["motor_wattage"])

        ttk.Label(self.input_frame, text="Driving Style:").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
        self.driving_style_combo = ttk.Combobox(self.input_frame, values=["Agressive", "Casual", "Eco"], width=13)
        self.driving_style_combo.grid(row=9, column=1, sticky=tk.E, padx=5, pady=5)
        self.driving_style_combo.set(self.settings.get("driving_style", "Casual"))

        # --- Buttons ---
        calculate_button = ttk.Button(self.input_frame, text="Calculate", command=self.calculate_all)
        calculate_button.grid(row=10, column=0, columnspan=2, pady=10)

        save_button = ttk.Button(self.input_frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=11, column=0, columnspan=2, pady=5)

        self.clear_button = ttk.Button(self.input_frame, text="Clear", command=self.clear_fields)
        self.clear_button.grid(row=12, column=0, columnspan=2, pady=5)

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
        ttk.Label(self.results_frame, text="Voltage:").grid(row=8, column=0, sticky=tk.W, padx=5)
        self.breakdown_voltage_label = ttk.Label(self.results_frame, text="")
        self.breakdown_voltage_label.grid(row=8, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Ah:").grid(row=9, column=0, sticky=tk.W, padx=5)
        self.breakdown_ah_label = ttk.Label(self.results_frame, text="")
        self.breakdown_ah_label.grid(row=9, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Wh:").grid(row=10, column=0, sticky=tk.W, padx=5)
        self.breakdown_wh_label = ttk.Label(self.results_frame, text="")
        self.breakdown_wh_label.grid(row=10, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Motor Watts:").grid(row=11, column=0, sticky=tk.W, padx=5)
        self.breakdown_motor_watts_label = ttk.Label(self.results_frame, text="")
        self.breakdown_motor_watts_label.grid(row=11, column=1, sticky=tk.E, padx=5)

        ttk.Label(self.results_frame, text="Charge Rate:").grid(row=12, column=0, sticky=tk.W, padx=5)
        self.breakdown_charge_rate_label = ttk.Label(self.results_frame, text="")
        self.breakdown_charge_rate_label.grid(row=12, column=1, sticky=tk.E, padx=5)

        # --- Emojis ---
        emoji_label = ttk.Label(self.results_frame, text="🚲🔋🛴", font=("Arial", 30))
        emoji_label.grid(row=13, column=0, columnspan=2, pady=10)

        # --- Padding and Weight ---
        for i in range(14):
            self.results_frame.grid_rowconfigure(i, weight=1)
        self.results_frame.grid_columnconfigure(1, weight=1)
        self.input_frame.grid_columnconfigure(1, weight=1)

        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(0, weight=1)

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

    def update_breakdown(self):
        voltage = self.voltage_entry.get()
        capacity_type = self.capacity_type_combo.get()
        capacity = self.capacity_entry.get()
        motor_wattage = self.motor_wattage_entry.get()
        charge_rate = self.charge_rate_entry.get()

        self.breakdown_voltage_label.config(text=voltage)

        if capacity_type == "Ah":
            self.breakdown_ah_label.config(text=capacity)
            try:
                wh = float(capacity) * float(voltage)
                self.breakdown_wh_label.config(text=f"{wh:.2f}")
            except ValueError:
                self.breakdown_wh_label.config(text="N/A")
        else: # Wh
            self.breakdown_wh_label.config(text=capacity)
            try:
                ah = float(capacity) / float(voltage)
                self.breakdown_ah_label.config(text=f"{ah:.2f}")
            except ValueError:
                self.breakdown_wh_label.config(text="N/A")

        self.breakdown_motor_watts_label.config(text=motor_wattage)
        self.breakdown_charge_rate_label.config(text=charge_rate)

    def calculate_range(self):
        try:
            voltage = float(self.voltage_entry.get())
            capacity_type = self.capacity_type_combo.get()
            capacity = float(self.capacity_entry.get())
            motor_wattage = float(self.motor_wattage_entry.get())
            driving_style = self.driving_style_combo.get()

            if voltage <= 0 or capacity <= 0 or motor_wattage <= 0:
                messagebox.showerror("Error", "Please enter valid positive numbers for voltage, capacity, and motor wattage.")
                return

            if capacity_type == "Wh":
                total_energy_wh = capacity
                try:
                    total_capacity_ah = total_energy_wh / voltage
                except ZeroDivisionError:
                    total_capacity_ah = 0
            else:  # capacity_type == "Ah"
                total_capacity_ah = capacity
                total_energy_wh = capacity * voltage

            # Adjust power consumption based on driving style percentage
            if driving_style == "Agressive":
                power_consumption_w = motor_wattage * 1.0
            elif driving_style == "Casual":
                power_consumption_w = motor_wattage * 0.5
            elif driving_style == "Eco":
                power_consumption_w = motor_wattage * 0.25

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
            messagebox.showerror("Error", "Invalid input. Please enter numeric values.")
        except ZeroDivisionError:
            messagebox.showerror("Error", "Voltage cannot be zero.")
        except AttributeError:
            self.full_charge_range = 0
            self.range_unit = "miles"

    def calculate_charge_time_and_remaining_range(self):
        try:
            voltage = float(self.voltage_entry.get())
            capacity_type = self.capacity_type_combo.get()
            capacity_ah = 0
            if capacity_type == "Wh":
                capacity_ah = float(self.capacity_entry.get()) / voltage if voltage > 0 else 0
            else:
                capacity_ah = float(self.capacity_entry.get())

            charge_rate = float(self.charge_rate_entry.get())
            current_percentage = float(self.current_percentage_entry.get())

            if voltage <= 0 or capacity_ah <= 0 or charge_rate <= 0 or not 0 <= current_percentage <= 100:
                if charge_rate <= 0:
                    messagebox.showerror("Error", "Charger rate must be a positive number.")
                elif not 0 <= current_percentage <= 100:
                    messagebox.showerror("Error", "Current percentage must be between 0 and 100.")
                return

            remaining_capacity_ah = capacity_ah * (1 - (current_percentage / 100))
            if charge_rate > 0:
                estimated_charge_time = remaining_capacity_ah / charge_rate
                self.charge_time_label.config(text=f"{estimated_charge_time:.2f}")
            else:
                self.charge_time_label.config(text="N/A")

            self.remaining_charge_percentage_label.config(text=f"{100 - current_percentage:.2f}%")

            if hasattr(self, 'full_charge_range'):
                remaining_range = self.full_charge_range * (current_percentage / 100)
                self.remaining_range_label.config(text=f"{remaining_range:.2f}")
                self.remaining_range_unit_label.config(text=self.range_unit)
            else:
                self.remaining_range_label.config(text="N/A")

        except ValueError:
            messagebox.showerror("Error", "Invalid input for charging information.")
        except ZeroDivisionError:
            messagebox.showerror("Error", "Voltage or charge rate cannot be zero in these calculations.")

    def save_settings(self):
        try:
            voltage = self.voltage_entry.get()
            capacity_type = self.capacity_type_combo.get()
            capacity = self.capacity_entry.get()
            motor_wattage = self.motor_wattage_entry.get()
            driving_style = self.driving_style_combo.get()
            charge_rate = self.charge_rate_entry.get()

            settings = {
                "voltage": voltage,
                "capacity_type": capacity_type,
                "capacity": capacity,
                "motor_wattage": motor_wattage,
                "driving_style": driving_style,
                "charge_rate": charge_rate,
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
        self.capacity_type_combo.set("Wh")
        self.capacity_entry.delete(0, tk.END)
        self.charge_rate_entry.delete(0, tk.END)
        self.current_percentage_entry.delete(0, tk.END)
        self.motor_wattage_entry.delete(0, tk.END)
        self.driving_style_combo.set("Casual")
        self.calculated_range_label.config(text="")
        self.remaining_range_label.config(text="")
        self.remaining_charge_percentage_label.config(text="")
        self.charge_time_label.config(text="")
        self.miles_per_wh_label.config(text="")
        self.miles_per_ah_label.config(text="")
        self.breakdown_voltage_label.config(text="")
        self.breakdown_ah_label.config(text="")
        self.breakdown_wh_label.config(text="")
        self.breakdown_motor_watts_label.config(text="")
        self.breakdown_charge_rate_label.config(text="")

# --- CLI Functionality ---
def run_cli_calculator():
    print("--- Battery Calculator (CLI Mode) ---")
    
    # Load settings for default values
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load settings for CLI: {e}")

    while True:
        try:
            voltage_str = input(f"Enter Battery Voltage (V) [{settings.get('voltage', 'N/A')}]: ") or settings.get('voltage', '')
            voltage = float(voltage_str)
            if voltage <= 0:
                print("Voltage must be a positive number.")
                continue

            capacity_type = input(f"Enter Capacity Type (Wh/Ah) [{settings.get('capacity_type', 'Wh')}]: ").strip() or settings.get('capacity_type', 'Wh')
            if capacity_type.lower() not in ["wh", "ah"]:
                print("Invalid capacity type. Please enter 'Wh' or 'Ah'.")
                continue
            
            capacity_str = input(f"Enter Battery Capacity ({capacity_type}) [{settings.get('capacity', 'N/A')}]: ") or settings.get('capacity', '')
            capacity = float(capacity_str)
            if capacity <= 0:
                print("Capacity must be a positive number.")
                continue

            charge_rate_str = input(f"Enter Charger Rate (A) [{settings.get('charge_rate', 'N/A')}]: ") or settings.get('charge_rate', '')
            charge_rate = float(charge_rate_str)
            if charge_rate <= 0:
                print("Charger rate must be a positive number.")
                continue

            current_percentage_str = input("Enter Current Percentage (%) [0]: ") or "0"
            current_percentage = float(current_percentage_str)
            if not 0 <= current_percentage <= 100:
                print("Current percentage must be between 0 and 100.")
                continue

            motor_wattage_str = input(f"Enter Motor Wattage (W) [{settings.get('motor_wattage', 'N/A')}]: ") or settings.get('motor_wattage', '')
            motor_wattage = float(motor_wattage_str)
            if motor_wattage <= 0:
                print("Motor wattage must be a positive number.")
                continue

            driving_style = input(f"Enter Driving Style (Agressive/Casual/Eco) [{settings.get('driving_style', 'Casual')}]: ").strip() or settings.get('driving_style', 'Casual')
            if driving_style.lower() not in ["agressive", "casual", "eco"]:
                print("Invalid driving style. Please enter 'Agressive', 'Casual', or 'Eco'.")
                continue
            
            # Convert to internal representation for consistency with GUI logic
            if driving_style.lower() == "agressive":
                driving_style = "Agressive"
            elif driving_style.lower() == "casual":
                driving_style = "Casual"
            elif driving_style.lower() == "eco":
                driving_style = "Eco"

            break # Exit loop if all inputs are valid

        except ValueError:
            print("Invalid input. Please enter numeric values where required.")
        except KeyboardInterrupt:
            print("\nExiting CLI calculator.")
            sys.exit(0)

    # Perform calculations (re-using logic from GUI class for consistency)
    total_energy_wh = 0
    total_capacity_ah = 0

    if capacity_type.lower() == "wh":
        total_energy_wh = capacity
        try:
            total_capacity_ah = total_energy_wh / voltage
        except ZeroDivisionError:
            total_capacity_ah = 0
    else:  # capacity_type == "Ah"
        total_capacity_ah = capacity
        total_energy_wh = capacity * voltage

    # Adjust power consumption based on driving style percentage
    power_consumption_w = 0
    if driving_style == "Agressive":
        power_consumption_w = motor_wattage * 1.0
    elif driving_style == "Casual":
        power_consumption_w = motor_wattage * 0.5
    elif driving_style == "Eco":
        power_consumption_w = motor_wattage * 0.25

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

    remaining_capacity_ah = total_capacity_ah * (1 - (current_percentage / 100))
    estimated_charge_time = remaining_capacity_ah / charge_rate if charge_rate > 0 else 0
    remaining_charge_percentage = 100 - current_percentage
    remaining_range = estimated_range * (current_percentage / 100)

    print("\n--- Results ---")
    print(f"Estimated Range: {estimated_range:.2f} {calculated_unit}")
    print(f"Remaining Range: {remaining_range:.2f} {calculated_unit}")
    print(f"Remaining Charge: {remaining_charge_percentage:.2f}%")
    print(f"Estimated Charge Time: {estimated_charge_time:.2f} hours")
    print(f"Miles/Wh: {miles_per_wh:.2f}")
    print(f"Miles/Ah: {miles_per_ah:.2f}")

    print("\n--- Breakdown ---")
    print(f"Voltage: {voltage:.2f}V")
    print(f"Ah: {total_capacity_ah:.2f}Ah")
    print(f"Wh: {total_energy_wh:.2f}Wh")
    print(f"Motor Watts: {motor_wattage:.2f}W")
    print(f"Charge Rate: {charge_rate:.2f}A")
    print("\n🚲🔋🛴")

if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_calculator()
    else:
        if 'DISPLAY' not in os.environ:
            print("Error: No display found. This application requires a graphical environment.")
            print("If you are using SSH, you may need to enable X11 forwarding, or run with the --cli flag.")
            sys.exit(1)

        root = tk.Tk()
        app = BatteryCalculatorGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.update_settings_on_close)
        root.mainloop()
