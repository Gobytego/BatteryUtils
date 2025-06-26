import sys
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
    QTextEdit, QRadioButton, QFrame, QGroupBox, QInputDialog, QFileDialog, QButtonGroup,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDateTimeEdit
)
from PyQt6.QtCore import Qt, QTimer, QDateTime

# Changed settings file name
SETTINGS_FILE = "BatteryUtils_Settings.json"

class BatteryCalculatorGUI(QWidget):
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

    MAX_PROFILES = 10 # Maximum number of profiles allowed (Increased from 3 to 10)

    def __init__(self):
        super().__init__()
        # Changed window title to reflect "BatteryUtils" and version number
        self.setWindowTitle("BatteryUtils v1.06.03")
        self.setGeometry(100, 100, 1200, 750) # x, y, width, height for the window, adjusted for three columns

        # Store all profiles loaded from the settings file
        self.all_profiles = {}
        # Stores the name of the currently active profile
        self.current_profile_name = "Default Profile"

        # New variables for logged efficiency override
        self.use_logged_efficiency = False
        self.logged_wh_per_mile_average = 0.0

        # New flag to suppress QMessageBox during initial load
        self.is_initializing = True 

        # Initialize labels that are cleared early to avoid AttributeError
        # These need to exist before clear_fields is called in load_profile_data
        self.calculated_range_label = QLabel("")
        self.remaining_range_label = QLabel("")
        self.remaining_charge_percentage_label = QLabel("")
        self.charge_time_label = QLabel("")
        self.miles_per_wh_label = QLabel("")
        self.miles_per_ah_label = QLabel("")
        self.percentage_after_charge_label = QLabel("")
        self.range_to_cutoff_label = QLabel("")
        self.charge_time_from_cutoff_label = QLabel("")
        self.current_state_percent_result_label = QLabel("")
        self.current_state_voltage_result_label = QLabel("")
        self.results_charge_duration_label = QLabel("")
        self.calculated_range_unit_label = QLabel("miles") # Also explicitly initialize these
        self.remaining_range_unit_label = QLabel("miles")
        self.range_to_cutoff_unit_label = QLabel("miles")

        # Initialize breakdown labels to avoid AttributeError
        self.breakdown_voltage_label = QLabel("")
        self.breakdown_series_cells_label = QLabel("")
        self.breakdown_min_max_voltage_label = QLabel("")
        self.breakdown_ah_label = QLabel("N/A")
        self.breakdown_wh_label = QLabel("N/A")
        self.breakdown_motor_watts_label = QLabel("")
        self.breakdown_wheel_diameter_label = QLabel("")
        self.breakdown_charge_rate_label = QLabel("")
        self.breakdown_preferred_cutoff_label = QLabel("")
        self.breakdown_preferred_cutoff_voltage_label = QLabel("")
        self.efficiency_source_label = QLabel("Predicted") # Also initialized here as it's modified early

        # New label for the dynamically updated "Range to cutoff of XX%:" text
        self.range_to_cutoff_title_label = QLabel("Range to cutoff of:")

        # NEW: Labels for Last Ride Results in Breakdown
        self.breakdown_last_ride_date_label = QLabel("N/A")
        self.breakdown_last_ride_distance_label = QLabel("N/A")
        self.breakdown_last_ride_wh_label = QLabel("N/A")
        self.breakdown_last_ride_wh_per_mile_label = QLabel("N/A")
        
        # Instance variable to hold the last ride data for persistence
        self.last_ride_data = {}


        self.init_ui()

        # Load all profiles and then initialize the combo box
        self.load_all_profiles()
        self.update_profile_combo()
        # Load data for the initial profile (either last active or default)
        self.load_profile_data(self.current_profile_name)

        # Set initialization flag to False after all initial loading is complete
        self.is_initializing = False

    def init_ui(self):
        # Main Layout for the entire window
        main_v_layout = QVBoxLayout(self) # Top-level layout is vertical to hold tabs

        self.tab_widget = QTabWidget()
        main_v_layout.addWidget(self.tab_widget)

        # --- Tab 1: Battery Calculator ---
        self.calculator_tab = QWidget()
        # This QHBoxLayout will hold the three main columns: Input, Results, Breakdown
        self.calculator_tab_main_h_layout = QHBoxLayout(self.calculator_tab) 

        # --- Column 1: Input Section ---
        self.input_frame = QFrame(self.calculator_tab)
        self.input_layout = QGridLayout(self.input_frame)
        self.input_frame.setLayout(self.input_layout)
        self.input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.input_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.calculator_tab_main_h_layout.addWidget(self.input_frame, 2) # Add to main horizontal layout, changed from 1 to 2

        # --- Column 2: Results Section ---
        self.results_display_frame = QFrame(self.calculator_tab)
        self.results_display_layout = QVBoxLayout(self.results_display_frame) # Vertical layout inside this frame
        self.results_display_frame.setLayout(self.results_display_layout)
        self.results_display_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.results_display_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.calculator_tab_main_h_layout.addWidget(self.results_display_frame, 2) # Add to main horizontal layout, changed from 1 to 2

        # --- Column 3: Breakdown Section ---
        self.breakdown_display_frame = QFrame(self.calculator_tab)
        self.breakdown_display_layout = QVBoxLayout(self.breakdown_display_frame) # Vertical layout inside this frame
        self.breakdown_display_frame.setLayout(self.breakdown_display_layout)
        self.breakdown_display_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.breakdown_display_frame.setFrameShadow(QFrame.Shadow.Raised)
        # Adjusted stretch factor for the breakdown column to make it narrower
        self.calculator_tab_main_h_layout.addWidget(self.breakdown_display_frame, 1) # Changed from 0.5 to 1

        # Add the calculator tab to the main tab widget
        self.tab_widget.addTab(self.calculator_tab, "Battery Calculator")

        # --- Tab 2: Ride Log (Existing content) ---
        self.ride_log_tab = QWidget()
        self.ride_log_main_layout = QVBoxLayout(self.ride_log_tab)
        self.init_ride_log_ui() # Call method to build ride log UI
        self.tab_widget.addTab(self.ride_log_tab, "Ride Log")

        # --- Profile Management Section (moved into input_frame) ---
        self.profile_group_box = QGroupBox("--- Profile Management ---")
        self.profile_layout = QGridLayout(self.profile_group_box)

        self.profile_layout.addWidget(QLabel("Select Profile:"), 0, 0)
        self.profile_combo = QComboBox()
        self.profile_layout.addWidget(self.profile_combo, 0, 1, 1, 2) # Span 2 columns
        self.profile_combo.currentTextChanged.connect(self.on_profile_selection)

        self.profile_buttons_layout = QHBoxLayout()
        self.btn_new_profile = QPushButton("New")
        self.btn_save_profile = QPushButton("Save")
        self.btn_load_profile = QPushButton("Load")
        self.btn_delete_profile = QPushButton("Delete")

        self.btn_new_profile.clicked.connect(self.create_new_profile)
        self.btn_save_profile.clicked.connect(self.save_current_profile)
        self.btn_load_profile.clicked.connect(lambda: self.load_profile_data(self.profile_combo.currentText()))
        self.btn_delete_profile.clicked.connect(self.delete_selected_profile)

        self.profile_buttons_layout.addWidget(self.btn_new_profile)
        self.profile_buttons_layout.addWidget(self.btn_save_profile)
        self.profile_buttons_layout.addWidget(self.btn_load_profile)
        self.profile_buttons_layout.addWidget(self.btn_delete_profile)
        self.profile_layout.addLayout(self.profile_buttons_layout, 1, 0, 1, 3) # Span 3 columns

        self.input_layout.addWidget(self.profile_group_box, 0, 0, 1, 2) # Add profile box to input frame, span 2 columns

        # --- Battery Information ---
        self.battery_info_group_box = QGroupBox("--- Battery Info ---")
        self.battery_info_layout = QGridLayout(self.battery_info_group_box)

        self.battery_info_layout.addWidget(QLabel("Nominal Voltage (V):"), 0, 0)
        self.voltage_entry = QLineEdit()
        self.voltage_entry.textChanged.connect(self.update_voltage_info_labels)
        self.voltage_entry.setPlaceholderText("e.g., 48, 52")
        self.battery_info_layout.addWidget(self.voltage_entry, 0, 1)

        # Cells in Series (S) - initially hidden, shown if nominal voltage is unknown
        self.series_cells_label = QLabel("Cells in Series (S):")
        self.series_cells_entry = QLineEdit()
        self.series_cells_entry.textChanged.connect(self.update_voltage_info_labels)
        self.series_cells_entry.setPlaceholderText("e.g., 13, 14")

        # Info labels for min/max voltage based on series cells
        self.max_voltage_info_label = QLabel("Full Charge V: N/A")
        self.battery_info_layout.addWidget(self.max_voltage_info_label, 2, 0, 1, 2)
        self.min_voltage_info_label = QLabel("Empty V: N/A")
        self.battery_info_layout.addWidget(self.min_voltage_info_label, 3, 0, 1, 2)

        # Initial call to set visibility and labels
        self.update_voltage_info_labels()

        self.battery_info_layout.addWidget(QLabel("Capacity Type:"), 4, 0)
        self.capacity_type_combo = QComboBox()
        self.capacity_type_combo.addItems(["Wh", "Ah"])
        self.capacity_type_combo.currentTextChanged.connect(self.update_capacity_label)
        self.capacity_type_combo.setCurrentText("Wh") # Default for new profiles
        self.battery_info_layout.addWidget(self.capacity_type_combo, 4, 1)

        self.capacity_label = QLabel("Battery Capacity (Wh):") # Placeholder, text updated by update_capacity_label
        self.battery_info_layout.addWidget(self.capacity_label, 5, 0)
        self.capacity_entry = QLineEdit()
        self.battery_info_layout.addWidget(self.capacity_entry, 5, 1)
        self.update_capacity_label() # Initial call to set correct label

        self.input_layout.addWidget(self.battery_info_group_box, 1, 0, 1, 2)

        # --- Charging Information ---
        self.charging_group_box = QGroupBox("--- Charging ---")
        self.charging_layout = QGridLayout(self.charging_group_box)

        self.charging_layout.addWidget(QLabel("Charger Rate (A):"), 0, 0)
        self.charge_rate_entry = QLineEdit()
        self.charging_layout.addWidget(self.charge_rate_entry, 0, 1)

        self.charging_layout.addWidget(QLabel("Charge Duration (hours):"), 1, 0)
        self.charging_duration_combo = QComboBox()
        self.charging_duration_combo.addItems([""] + [f"{i*0.5:.1f} hours" for i in range(1, 25)]) # 0.5 to 12.0 hours
        self.charging_layout.addWidget(self.charging_duration_combo, 1, 1)
        self.charging_duration_combo.setCurrentText("") # No default selected

        # Current Battery State Input Choice
        self.charge_input_method_group = QButtonGroup(self) # Group for radio buttons
        self.percent_radio = QRadioButton("Current Percentage (%)")
        self.voltage_radio = QRadioButton("Current Voltage (V)")
        self.charge_input_method_group.addButton(self.percent_radio, 0) # ID 0 for percentage
        self.charge_input_method_group.addButton(self.voltage_radio, 1) # ID 1 for voltage

        self.percent_radio.toggled.connect(self.toggle_charge_input)
        self.voltage_radio.toggled.connect(self.toggle_charge_input)

        radio_h_layout = QHBoxLayout()
        radio_h_layout.addWidget(self.percent_radio)
        radio_h_layout.addWidget(self.voltage_radio)
        self.charging_layout.addLayout(radio_h_layout, 2, 0, 1, 2)

        self.current_percentage_label = QLabel("Current Percentage (%):")
        self.current_percentage_entry = QLineEdit("0")
        self.charging_layout.addWidget(self.current_percentage_label, 3, 0)
        self.charging_layout.addWidget(self.current_percentage_entry, 3, 1)

        self.current_voltage_label = QLabel("Current Voltage (V):")
        self.current_voltage_entry = QLineEdit("")
        # These will be added to layout in toggle_charge_input if voltage is selected

        self.percent_radio.setChecked(True) # Default for new profiles

        # NEW: Preferred Low Battery Cutoff
        self.charging_layout.addWidget(QLabel("Preferred Cutoff (%):"), 4, 0)
        self.preferred_cutoff_entry = QLineEdit("25") # Default to 25%
        self.preferred_cutoff_entry.textChanged.connect(self.calculate_all) # Recalculate on cutoff change
        self.charging_layout.addWidget(self.preferred_cutoff_entry, 4, 1)


        self.input_layout.addWidget(self.charging_group_box, 2, 0, 1, 2)

        # --- Motor and Bike Information ---
        self.motor_bike_group_box = QGroupBox("--- Motor/Bike Info ---")
        self.motor_bike_layout = QGridLayout(self.motor_bike_group_box)

        self.motor_bike_layout.addWidget(QLabel("Motor Wattage (W):"), 0, 0)
        self.motor_wattage_entry = QLineEdit()
        self.motor_bike_layout.addWidget(self.motor_wattage_entry, 0, 1)

        self.motor_bike_layout.addWidget(QLabel("Wheel Diameter (in):"), 1, 0)
        self.wheel_diameter_entry = QLineEdit()
        self.wheel_diameter_entry.textChanged.connect(self.calculate_all) # Recalculate if wheel diameter changes
        self.motor_bike_layout.addWidget(self.wheel_diameter_entry, 1, 1)

        self.motor_bike_layout.addWidget(QLabel("Driving Style:"), 2, 0)
        self.driving_style_combo = QComboBox()
        self.driving_style_combo.addItems(["Agressive", "Casual", "Eco"])
        self.driving_style_combo.currentTextChanged.connect(self.calculate_all) # Recalculate if driving style changes
        self.driving_style_combo.setCurrentText("Casual") # Default for new profiles
        self.motor_bike_layout.addWidget(self.driving_style_combo, 2, 1)

        self.input_layout.addWidget(self.motor_bike_group_box, 3, 0, 1, 2)

        # --- Buttons (at the bottom of Input Column) ---
        self.buttons_h_layout = QHBoxLayout()
        calculate_button = QPushButton("Calculate")
        calculate_button.clicked.connect(self.calculate_all)
        calculate_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #4CAF50; /* Green */"
            "   color: white;"
            "   padding: 10px 20px;"
            "   border-radius: 8px;"
            "   font-size: 16px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #45a049;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #3e8e41;"
            "}"
        )
        self.buttons_h_layout.addWidget(calculate_button)

        self.clear_button = QPushButton("Clear Fields")
        self.clear_button.clicked.connect(self.clear_fields)
        self.buttons_h_layout.addWidget(self.clear_button)

        self.export_breakdown_button = QPushButton("Export Breakdown")
        self.export_breakdown_button.clicked.connect(self.export_breakdown_to_file)
        self.buttons_h_layout.addWidget(self.export_breakdown_button)

        self.input_layout.addLayout(self.buttons_h_layout, 4, 0, 1, 2)


        # --- Output Labels (Results Column) ---
        # Main results container uses QVBoxLayout
        # This will hold multiple QGroupBoxes

        # 1. Range Group Box
        self.range_group_box = QGroupBox("-- Range --")
        self.range_layout = QGridLayout(self.range_group_box)
        self.results_display_layout.addWidget(self.range_group_box)

        self.range_layout.addWidget(QLabel("Estimated Full Range:"), 0, 0)
        self.range_layout.addWidget(self.calculated_range_label, 0, 1)
        self.range_layout.addWidget(self.calculated_range_unit_label, 0, 2)

        self.range_layout.addWidget(QLabel("Remaining Range:"), 1, 0)
        self.range_layout.addWidget(self.remaining_range_label, 1, 1)
        self.range_layout.addWidget(self.remaining_range_unit_label, 1, 2)

        # Updated label for Range to Cutoff
        # Using self.range_to_cutoff_title_label created in __init__
        self.range_layout.addWidget(self.range_to_cutoff_title_label, 2, 0) # Use the new dynamic label
        self.range_layout.addWidget(self.range_to_cutoff_label, 2, 1)
        self.range_layout.addWidget(self.range_to_cutoff_unit_label, 2, 2)


        # 2. State Group Box
        self.state_group_box = QGroupBox("-- State --")
        self.state_layout = QGridLayout(self.state_group_box)
        self.results_display_layout.addWidget(self.state_group_box)

        self.state_layout.addWidget(QLabel("Current %:"), 0, 0)
        self.state_layout.addWidget(self.current_state_percent_result_label, 0, 1)
        self.state_layout.addWidget(QLabel("%"), 0, 2)

        self.state_layout.addWidget(QLabel("Current V:"), 1, 0)
        self.state_layout.addWidget(self.current_state_voltage_result_label, 1, 1)
        self.state_layout.addWidget(QLabel("V"), 1, 2)

        # 3. Charge Group Box
        self.charge_group_box = QGroupBox("-- Charge --")
        self.charge_layout = QGridLayout(self.charge_group_box)
        self.results_display_layout.addWidget(self.charge_group_box)

        self.charge_layout.addWidget(QLabel("Remaining Charge to 100%:"), 0, 0)
        self.charge_layout.addWidget(self.remaining_charge_percentage_label, 0, 1)
        self.charge_layout.addWidget(QLabel("%"), 0, 2)

        self.charge_layout.addWidget(QLabel("Estimated Charge Time to 100%:"), 1, 0)
        self.charge_layout.addWidget(self.charge_time_label, 1, 1)

        self.charge_layout.addWidget(QLabel("Charge Duration:"), 2, 0)
        self.charge_layout.addWidget(self.results_charge_duration_label, 2, 1)

        self.charge_layout.addWidget(QLabel("Percentage after set charge duration:"), 3, 0)
        self.charge_layout.addWidget(self.percentage_after_charge_label, 3, 1)
        self.charge_layout.addWidget(QLabel("%"), 3, 2)

        # 4. Other Group Box
        self.other_group_box = QGroupBox("-- Other --")
        self.other_layout = QGridLayout(self.other_group_box)
        self.results_display_layout.addWidget(self.other_group_box)

        self.other_layout.addWidget(QLabel("Miles/Wh:"), 0, 0)
        self.other_layout.addWidget(self.miles_per_wh_label, 0, 1)

        self.other_layout.addWidget(QLabel("Miles/Ah:"), 1, 0)
        self.other_layout.addWidget(self.miles_per_ah_label, 1, 1)

        self.other_layout.addWidget(QLabel("Efficiency Source:"), 2, 0)
        self.efficiency_source_label.setStyleSheet("font-style: italic; color: #555;")
        self.other_layout.addWidget(self.efficiency_source_label, 2, 1, 1, 2)

        self.reset_efficiency_button = QPushButton("Reset Efficiency")
        self.reset_efficiency_button.clicked.connect(self.reset_efficiency_source)
        self.reset_efficiency_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #f0ad4e; /* Orange */"
            "   color: white;"
            "   padding: 5px 10px;"
            "   border-radius: 5px;"
            "   font-size: 12px;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #ec971f;"
            "}"
        )
        self.other_layout.addWidget(self.reset_efficiency_button, 3, 0, 1, 3, Qt.AlignmentFlag.AlignRight)


        # --- Breakdown Column (placed in breakdown_display_layout) ---
        self.breakdown_group_box = QGroupBox("--- Breakdown ---")
        self.breakdown_group_layout = QGridLayout(self.breakdown_group_box) # Layout for content WITHIN the breakdown group box

        self.breakdown_group_layout.addWidget(QLabel("Nominal Voltage:"), 0, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_voltage_label, 0, 1)

        self.breakdown_group_layout.addWidget(QLabel("Cells in Series (S):"), 1, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_series_cells_label, 1, 1)

        self.breakdown_group_layout.addWidget(QLabel("Min/Max Voltage (Calculated):"), 2, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_min_max_voltage_label, 2, 1)

        self.breakdown_group_layout.addWidget(QLabel("Ah:"), 3, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_ah_label, 3, 1)

        self.breakdown_group_layout.addWidget(QLabel("Wh:"), 4, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_wh_label, 4, 1)

        self.breakdown_group_layout.addWidget(QLabel("Motor Watts:"), 5, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_motor_watts_label, 5, 1)

        self.breakdown_group_layout.addWidget(QLabel("Wheel Diameter:"), 6, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_wheel_diameter_label, 6, 1)

        self.breakdown_group_layout.addWidget(QLabel("Charge Rate:"), 7, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_charge_rate_label, 7, 1)
        
        self.breakdown_group_layout.addWidget(QLabel("Preferred Cutoff %:"), 8, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_preferred_cutoff_label, 8, 1)

        self.breakdown_group_layout.addWidget(QLabel("Preferred Cutoff V:"), 9, 0)
        self.breakdown_group_layout.addWidget(self.breakdown_preferred_cutoff_voltage_label, 9, 1)

        # Add the breakdown group box to its display frame
        self.breakdown_display_layout.addWidget(self.breakdown_group_box)

        # NEW: Last Logged Ride Group Box (in Breakdown Column)
        self.last_ride_group_box = QGroupBox("--- Last Logged Ride ---")
        self.last_ride_layout = QGridLayout(self.last_ride_group_box)

        self.last_ride_layout.addWidget(QLabel("Date:"), 0, 0)
        self.last_ride_layout.addWidget(self.breakdown_last_ride_date_label, 0, 1)

        self.last_ride_layout.addWidget(QLabel("Distance:"), 1, 0)
        self.last_ride_layout.addWidget(self.breakdown_last_ride_distance_label, 1, 1)

        self.last_ride_layout.addWidget(QLabel("Wh Consumed:"), 2, 0)
        self.last_ride_layout.addWidget(self.breakdown_last_ride_wh_label, 2, 1)

        self.last_ride_layout.addWidget(QLabel("Wh/mile:"), 3, 0)
        self.last_ride_layout.addWidget(self.breakdown_last_ride_wh_per_mile_label, 3, 1)

        # Move the apply efficiency button into this group box for better organization
        self.apply_logged_efficiency_button = QPushButton("Apply Logged Efficiency to Calculator")
        self.apply_logged_efficiency_button.clicked.connect(self.apply_logged_efficiency_to_calculator)
        self.apply_logged_efficiency_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #007bff; /* Bootstrap primary blue */"
            "   color: white;"
            "   padding: 8px 15px;"
            "   border-radius: 6px;"
            "   font-size: 14px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #0069d9;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #0062cc;"
            "}"
        )
        self.last_ride_layout.addWidget(self.apply_logged_efficiency_button, 4, 0, 1, 2) # Span two columns

        self.breakdown_display_layout.addWidget(self.last_ride_group_box)


        # --- Attribution (at the bottom of the Results Column) ---
        attribution_label = QLabel("Made by Adam of Gobytego")
        attribution_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        attribution_label.setStyleSheet("font-style: italic; font-size: 10pt;")
        self.results_display_layout.addWidget(attribution_label) # Moved to results column, at the bottom of the QVBoxLayout


    def init_ride_log_ui(self):
        """Initializes the UI elements for the Ride Log tab."""
        # Input fields for a new ride entry
        input_group_box = QGroupBox("Log New Ride")
        input_layout = QGridLayout(input_group_box)

        input_layout.addWidget(QLabel("Date:"), 0, 0)
        self.ride_date_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.ride_date_edit.setCalendarPopup(True)
        self.ride_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        input_layout.addWidget(self.ride_date_edit, 0, 1)

        input_layout.addWidget(QLabel("Distance (miles):"), 1, 0)
        self.ride_distance_entry = QLineEdit()
        self.ride_distance_entry.setPlaceholderText("e.g., 15.5")
        input_layout.addWidget(self.ride_distance_entry, 1, 1)

        # Start Battery State
        input_layout.addWidget(QLabel("Start Battery State:"), 2, 0)
        self.ride_start_state_type_combo = QComboBox()
        self.ride_start_state_type_combo.addItems(["Percentage (%)", "Voltage (V)"])
        input_layout.addWidget(self.ride_start_state_type_combo, 2, 1)
        
        self.ride_start_value_entry = QLineEdit()
        self.ride_start_value_entry.setPlaceholderText("e.g., 100 or 54.6")
        input_layout.addWidget(self.ride_start_value_entry, 3, 1)

        # End Battery State
        input_layout.addWidget(QLabel("End Battery State:"), 4, 0)
        self.ride_end_state_type_combo = QComboBox()
        self.ride_end_state_type_combo.addItems(["Percentage (%)", "Voltage (V)"])
        input_layout.addWidget(self.ride_end_state_type_combo, 4, 1)

        self.ride_end_value_entry = QLineEdit()
        self.ride_end_value_entry.setPlaceholderText("e.g., 40 or 44.0")
        input_layout.addWidget(self.ride_end_value_entry, 5, 1)
        
        # NEW: Riding Style for Logged Ride
        input_layout.addWidget(QLabel("Riding Style:"), 6, 0)
        self.ride_driving_style_combo = QComboBox()
        self.ride_driving_style_combo.addItems(["Agressive", "Casual", "Eco"])
        self.ride_driving_style_combo.setCurrentText("Casual")
        input_layout.addWidget(self.ride_driving_style_combo, 6, 1)

        input_layout.addWidget(QLabel("Notes (Optional):"), 7, 0) # Shifted to row 7
        self.ride_notes_entry = QLineEdit()
        input_layout.addWidget(self.ride_notes_entry, 7, 1)

        log_ride_button = QPushButton("Log Ride")
        log_ride_button.clicked.connect(self.log_ride)
        log_ride_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #1a73e8; /* Blue */"
            "   color: white;"
            "   padding: 8px 15px;"
            "   border-radius: 6px;"
            "   font-size: 14px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #186bdc;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #1560c0;"
            "}"
        )
        clear_log_fields_button = QPushButton("Clear Ride Fields")
        clear_log_fields_button.clicked.connect(self.clear_ride_log_fields)

        ride_log_buttons_layout = QHBoxLayout()
        ride_log_buttons_layout.addWidget(log_ride_button)
        ride_log_buttons_layout.addWidget(clear_log_fields_button)
        input_layout.addLayout(ride_log_buttons_layout, 8, 0, 1, 2) # Shifted to row 8


        # Table to display logged rides
        self.ride_log_table = QTableWidget()
        self.ride_log_table.setColumnCount(8) # Increased to 8 for "Riding Style"
        self.ride_log_table.setHorizontalHeaderLabels([
            "Date", "Distance (miles)", "Start (%)", "End (%)", "Wh Consumed", "Wh/mile", "Riding Style", "Notes" # Added "Riding Style"
        ])
        # Changed resize mode from Stretch to Interactive
        self.ride_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.ride_log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows) # Select whole rows

        delete_ride_button = QPushButton("Delete Selected Ride(s)")
        delete_ride_button.clicked.connect(self.delete_selected_rides)
        delete_ride_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #d9534f; /* Red */"
            "   color: white;"
            "   padding: 8px 15px;"
            "   border-radius: 6px;"
            "   font-size: 14px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #c9302c;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #ac2925;"
            "}"
        )
        
        # NEW: Export and Import Ride Log Buttons
        self.export_ride_log_button = QPushButton("Export Ride Log")
        self.export_ride_log_button.clicked.connect(self.export_ride_log_to_file)
        self.export_ride_log_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #28a745; /* Green */"
            "   color: white;"
            "   padding: 8px 15px;"
            "   border-radius: 6px;"
            "   font-size: 14px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #218838;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #1e7e34;"
            "}"
        )

        self.import_ride_log_button = QPushButton("Import Ride Log")
        self.import_ride_log_button.clicked.connect(self.import_ride_log_from_file)
        self.import_ride_log_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #17a2b8; /* Cyan */"
            "   color: white;"
            "   padding: 8px 15px;"
            "   border-radius: 6px;"
            "   font-size: 14px;"
            "   font-weight: bold;"
            "   border: none;"
            "}"
            "QPushButton:hover {"
            "   background-color: #138496;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #117a8b;"
            "}"
        )

        ride_log_export_import_layout = QHBoxLayout()
        ride_log_export_import_layout.addWidget(self.export_ride_log_button)
        ride_log_export_import_layout.addWidget(self.import_ride_log_button)


        # Average efficiency display (This group box remains in Ride Log tab)
        average_efficiency_group_box = QGroupBox("Average Efficiency from Logged Rides")
        average_efficiency_layout = QVBoxLayout(average_efficiency_group_box)
        self.average_wh_per_mile_label = QLabel("Average Wh/mile: N/A")
        self.average_miles_per_wh_label = QLabel("Average Miles/Wh: N/A")
        average_efficiency_layout.addWidget(self.average_wh_per_mile_label)
        average_efficiency_layout.addWidget(self.average_miles_per_wh_label)
        # The apply_logged_efficiency_button is now in the Breakdown Column, removed from here
        # average_efficiency_layout.addWidget(self.apply_logged_efficiency_button)


        self.ride_log_main_layout.addWidget(input_group_box)
        self.ride_log_main_layout.addWidget(self.ride_log_table)
        self.ride_log_main_layout.addWidget(delete_ride_button)
        self.ride_log_main_layout.addLayout(ride_log_export_import_layout) # Add the new layout for export/import
        self.ride_log_main_layout.addWidget(average_efficiency_group_box) # Still keep this group box for displaying averages


    def closeEvent(self, event):
        """Overrides the close event to save settings before exiting."""
        self.save_current_profile()
        event.accept()

    def load_all_profiles(self):
        """Loads all profiles from the settings file."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    self.all_profiles = data.get("profiles", {})
                    last_active = data.get("last_active_profile")

                    if not self.all_profiles: # If settings file is empty or only profiles are empty
                        self.all_profiles["Default Profile"] = self._get_default_profile_settings()
                        self.current_profile_name = "Default Profile"
                    elif last_active and last_active in self.all_profiles:
                        self.current_profile_name = last_active
                    else: # If there are profiles but no last_active or last_active is invalid, pick the first one
                        self.current_profile_name = list(self.all_profiles.keys())[0]

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load settings: {e}\nCreating a new default profile.")
                self.all_profiles = {"Default Profile": self._get_default_profile_settings()}
                self.current_profile_name = "Default Profile"
        else:
            self.all_profiles = {"Default Profile": self._get_default_profile_settings()}
            self.current_profile_name = "Default Profile"

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
            "driving_style": "Casual",
            "preferred_cutoff_percentage": "25", # NEW: Default cutoff
            "ride_log": [], # New entry for ride log data
            "last_ride_data": {} # NEW: Default for last ride data
        }

    def update_profile_combo(self):
        """Updates the profile selection combobox with current profile names."""
        self.profile_combo.clear()
        self.profile_combo.addItems(list(self.all_profiles.keys()))
        self.profile_combo.setCurrentText(self.current_profile_name)

    def load_profile_data(self, profile_name):
        """Loads the settings for the given profile name into the GUI fields."""
        if profile_name not in self.all_profiles:
            QMessageBox.critical(self, "Error", f"Profile '{profile_name}' not found.")
            return

        self.current_profile_name = profile_name # Update current active profile
        self.profile_combo.setCurrentText(profile_name) # Update combobox display

        settings = self.all_profiles[profile_name]
        self.clear_fields(keep_profile_name=True) # Clear current display but keep profile name

        # Populate fields from the loaded settings for the Calculator tab
        self.voltage_entry.setText(settings.get("voltage", ""))
        self.series_cells_entry.setText(settings.get("series_cells", ""))
        self.capacity_type_combo.setCurrentText(settings.get("capacity_type", "Wh"))
        self.capacity_entry.setText(settings.get("capacity", ""))
        self.charge_rate_entry.setText(settings.get("charge_rate", ""))
        self.charging_duration_combo.setCurrentText(settings.get("charging_duration_hours", ""))
        self.current_percentage_entry.setText(settings.get("current_percentage", "0"))
        self.current_voltage_entry.setText(settings.get("current_voltage", ""))
        self.preferred_cutoff_entry.setText(settings.get("preferred_cutoff_percentage", "25")) # NEW: Load cutoff
        
        # Set radio button based on loaded method
        charge_method = settings.get("charge_input_method", "percentage")
        if charge_method == "percentage":
            self.percent_radio.setChecked(True)
        else:
            self.voltage_radio.setChecked(True)

        self.motor_wattage_entry.setText(settings.get("motor_wattage", ""))
        self.wheel_diameter_entry.setText(settings.get("wheel_diameter", ""))
        self.driving_style_combo.setCurrentText(settings.get("driving_style", "Casual"))

        # Trigger updates after loading
        self.update_capacity_label()
        self.toggle_charge_input()
        self.update_voltage_info_labels()

        # Reset logged efficiency state for the new profile
        self.reset_efficiency_source(show_message=False) # Do not show message on profile load

        # Update the ride log table for the Ride Log tab
        self.update_ride_log_table()
        self.calculate_average_efficiency()

        # NEW: Load and display last ride data
        self.last_ride_data = settings.get("last_ride_data", {})
        self.update_last_ride_display()


    def on_profile_selection(self, profile_name):
        """Callback when a new profile is selected from the combobox."""
        # This signal fires even when programmatically setting the text,
        # so add a check to prevent unnecessary reloads if already loaded.
        if self.current_profile_name != profile_name:
            self.load_profile_data(profile_name)

    def save_current_profile(self):
        """Saves the current GUI field values into the active profile."""
        profile_name = self.current_profile_name
        current_settings = {
            "voltage": self.voltage_entry.text(),
            "series_cells": self.series_cells_entry.text() if self.series_cells_entry.isVisible() else "",
            "capacity_type": self.capacity_type_combo.currentText(),
            "capacity": self.capacity_entry.text(),
            "charge_rate": self.charge_rate_entry.text(),
            "charging_duration_hours": self.charging_duration_combo.currentText(),
            "current_percentage": self.current_percentage_entry.text(),
            "current_voltage": self.current_voltage_entry.text(),
            "charge_input_method": "percentage" if self.percent_radio.isChecked() else "voltage",
            "motor_wattage": self.motor_wattage_entry.text(),
            "wheel_diameter": self.wheel_diameter_entry.text(),
            "driving_style": self.driving_style_combo.currentText(),
            "preferred_cutoff_percentage": self.preferred_cutoff_entry.text(), # NEW: Save cutoff
            "ride_log": self.all_profiles.get(profile_name, {}).get("ride_log", []), # Preserve existing log
            "last_ride_data": self.last_ride_data # NEW: Save last ride data
        }
        self.all_profiles[profile_name] = current_settings
        self._save_all_profiles_to_file(profile_name)
        QMessageBox.information(self, "Success", f"Profile '{profile_name}' saved successfully!")

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
            QMessageBox.critical(self, "Error", f"Failed to save all profiles: {e}")

    def create_new_profile(self):
        """Prompts for a new profile name and creates it."""
        if len(self.all_profiles) >= self.MAX_PROFILES:
            QMessageBox.warning(self, "Profile Limit", f"You can only have up to {self.MAX_PROFILES} profiles.")
            return

        new_name, ok = QInputDialog.getText(self, "New Profile", "Enter a name for the new profile:")
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.critical(self, "Invalid Name", "Profile name cannot be empty.")
                return
            if new_name in self.all_profiles:
                QMessageBox.critical(self, "Duplicate Name", f"Profile '{new_name}' already exists. Please choose a different name.")
                return

            self.all_profiles[new_name] = self._get_default_profile_settings()
            self.current_profile_name = new_name
            self.update_profile_combo()
            self.load_profile_data(new_name) # Load the (empty) new profile data
            self._save_all_profiles_to_file(self.current_profile_name) # Immediately save the new (empty) profile
            QMessageBox.information(self, "New Profile", f"Profile '{new_name}' created.")

    def delete_selected_profile(self):
        """Deletes the currently selected profile."""
        profile_to_delete = self.current_profile_name
        if profile_to_delete == "Default Profile" and len(self.all_profiles) == 1:
            QMessageBox.warning(self, "Cannot Delete", "The 'Default Profile' cannot be deleted if it's the only profile.")
            return
        if profile_to_delete not in self.all_profiles:
            QMessageBox.critical(self, "Error", "No profile selected or profile not found for deletion.")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete profile '{profile_to_delete}'? This cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            del self.all_profiles[profile_to_delete]
            self.update_profile_combo()
            
            # If the deleted profile was the active one, switch to another or default
            if self.all_profiles:
                first_profile = list(self.all_profiles.keys())[0]
                self.current_profile_name = first_profile
                self.load_profile_data(first_profile)
            else:
                self.all_profiles["Default Profile"] = self._get_default_profile_settings()
                self.current_profile_name = "Default Profile"
                self.load_profile_data("Default Profile")
            
            self._save_all_profiles_to_file(self.current_profile_name) # Save changes
            QMessageBox.information(self, "Deleted", f"Profile '{profile_to_delete}' deleted.")

    def update_voltage_info_labels(self):
        nominal_voltage_str = self.voltage_entry.text()
        inferred_s = None
        
        # Temporarily remove and re-add series_cells widgets for proper layout management
        # This is a common PyQt pattern for conditionally showing/hiding widgets in a grid
        # Check if parent is set before removing, to prevent errors on initial setup
        if self.series_cells_label.parent() == self.battery_info_group_box:
            self.battery_info_layout.removeWidget(self.series_cells_label)
            self.battery_info_layout.removeWidget(self.series_cells_entry)
        self.series_cells_label.hide()
        self.series_cells_entry.hide()

        try:
            nominal_voltage_float = float(nominal_voltage_str)
            inferred_s = self.NOMINAL_VOLTAGE_TO_SERIES_CELLS.get(int(round(nominal_voltage_float)))
            
            if inferred_s is not None:
                self.series_cells_entry.setText(str(inferred_s))
                # Do not show series cells input if inferred
            else:
                # Show if nominal voltage not found in map
                self.battery_info_layout.addWidget(self.series_cells_label, 1, 0) # Place at row 1, col 0
                self.battery_info_layout.addWidget(self.series_cells_entry, 1, 1) # Place at row 1, col 1
                self.series_cells_label.show()
                self.series_cells_entry.show()
                self.min_voltage_info_label.setText("Empty V: N/A")
                self.max_voltage_info_label.setText("Full Charge V: N/A")
                return None, None, None # Explicitly return None for unpacking

        except ValueError:
            inferred_s = None
            # Show if nominal voltage input is not a valid number
            self.battery_info_layout.addWidget(self.series_cells_label, 1, 0)
            self.battery_info_layout.addWidget(self.series_cells_entry, 1, 1)
            self.series_cells_label.show()
            self.series_cells_entry.show()
            self.min_voltage_info_label.setText("Empty V: N/A")
            self.max_voltage_info_label.setText("Full Charge V: N/A")
            return None, None, None # Explicitly return None for unpacking

        series_cells = inferred_s
        if series_cells is None:
            try:
                series_cells = int(self.series_cells_entry.text())
            except ValueError:
                series_cells = None

        if series_cells is not None and series_cells > 0:
            min_v = series_cells * self.CELL_VOLTAGE_EMPTY
            max_v = series_cells * self.CELL_VOLTAGE_FULL
            self.min_voltage_info_label.setText(f"Empty V: {min_v:.1f} (0%)")
            self.max_voltage_info_label.setText(f"Full Charge V: {max_v:.1f} (100%)")
            return min_v, max_v, series_cells # Return valid values
        else:
            self.min_voltage_info_label.setText("Empty V: N/A")
            self.max_voltage_info_label.setText("N/A")
            return None, None, None # Explicitly return None for unpacking

    def toggle_charge_input(self):
        # Remove widgets from layout before potentially re-adding them
        # Check if parent is set before removing
        if self.current_percentage_label.parent() == self.charging_group_box:
            self.charging_layout.removeWidget(self.current_percentage_label)
            self.charging_layout.removeWidget(self.current_percentage_entry)
        if self.current_voltage_label.parent() == self.charging_group_box:
            self.charging_layout.removeWidget(self.current_voltage_label)
            self.charging_layout.removeWidget(self.current_voltage_entry)

        # Hide all to reset
        self.current_percentage_label.hide()
        self.current_percentage_entry.hide()
        self.current_voltage_label.hide()
        self.current_voltage_entry.hide()

        # Add based on checked state
        if self.percent_radio.isChecked():
            self.charging_layout.addWidget(self.current_percentage_label, 3, 0)
            self.charging_layout.addWidget(self.current_percentage_entry, 3, 1)
            self.current_percentage_label.show()
            self.current_percentage_entry.show()
        else: # Voltage radio is checked
            self.charging_layout.addWidget(self.current_voltage_label, 3, 0)
            self.charging_layout.addWidget(self.current_voltage_entry, 3, 1)
            self.current_voltage_label.show()
            self.current_voltage_entry.show()
        
        # Ensure layout updates correctly after visibility changes
        self.charging_group_box.adjustSize()
        self.input_frame.adjustSize()


    def update_capacity_label(self):
        selected_type = self.capacity_type_combo.currentText()
        if selected_type == "Wh":
            self.capacity_label.setText("Battery Capacity (Wh):")
        elif selected_type == "Ah":
            self.capacity_label.setText("Battery Capacity (Ah):")

    def format_time_to_hours_minutes(self, decimal_hours):
        """Converts a float representing hours into a formatted 'X hours Y min' string."""
        if decimal_hours is None or decimal_hours < 0:
            return "N/A"
        
        total_minutes = round(decimal_hours * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0 and minutes > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} {minutes} min"
        elif hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''}"
        elif minutes > 0:
            return f"{minutes} min"
        else:
            return "0 min"


    def calculate_all(self):
        # Update breakdown first to show current input values, even if calculations fail
        self.update_breakdown()

        # Always attempt to calculate estimated range
        self.calculate_range()
        
        # Calculate time to full charge and remaining range/percentage based on current state
        self.calculate_charge_time_and_remaining_range()
        
        # NEW: Calculate range to cutoff and charge time from cutoff
        self.calculate_cutoff_metrics()

        # Get inputs for optional percentage after charge calculation
        charger_rate_str = self.charge_rate_entry.text()
        charging_duration_str = self.charging_duration_combo.currentText()
        
        # Only attempt "percentage after charge" calculation if both inputs are present
        if charging_duration_str and charger_rate_str:
            try:
                duration_hours = float(charging_duration_str.split(" ")[0])
                self.calculate_percentage_after_charge(duration_hours)
                # Update the new results_charge_duration_label with formatted time
                self.results_charge_duration_label.setText(self.format_time_to_hours_minutes(duration_hours))
            except ValueError:
                if not self.is_initializing: # Suppress during initialization
                    QMessageBox.warning(self, "Input Error", "Invalid charging duration format. Please select from the dropdown or clear it to disable this calculation.")
                self.percentage_after_charge_label.setText("N/A")
                self.results_charge_duration_label.setText("N/A")
        else:
            self.percentage_after_charge_label.setText("") # Clear this if no duration is set or charger rate is missing
            self.results_charge_duration_label.setText("")


    def get_derived_voltage_range_and_s(self):
        """Calculates min and max voltage and the series cell count based on user input (inferred or manual).
           Does NOT show messageboxes directly; returns None for invalid inputs."""
        series_cells = None
        nominal_voltage_str = self.voltage_entry.text()

        try:
            nominal_voltage_float = float(nominal_voltage_str)
            inferred_s = self.NOMINAL_VOLTAGE_TO_SERIES_CELLS.get(int(round(nominal_voltage_float)))
            
            if inferred_s is not None:
                self.series_cells_entry.setText(str(inferred_s))
                # Do not show series cells input if inferred
            else:
                # Show if nominal voltage not found in map
                self.battery_info_layout.addWidget(self.series_cells_label, 1, 0) # Place at row 1, col 0
                self.battery_info_layout.addWidget(self.series_cells_entry, 1, 1) # Place at row 1, col 1
                self.series_cells_label.show()
                self.series_cells_entry.show()
                self.min_voltage_info_label.setText("Empty V: N/A")
                self.max_voltage_info_label.setText("Full Charge V: N/A")
                return None, None, None # Explicitly return the tuple

        except ValueError:
            inferred_s = None
            # Show if nominal voltage input is not a valid number
            self.battery_info_layout.addWidget(self.series_cells_label, 1, 0)
            self.battery_info_layout.addWidget(self.series_cells_entry, 1, 1)
            self.series_cells_label.show()
            self.series_cells_entry.show()
            self.min_voltage_info_label.setText("Empty V: N/A")
            self.max_voltage_info_label.setText("Full Charge V: N/A")
            return None, None, None # Explicitly return the tuple

        series_cells = inferred_s
        if series_cells is None:
            try:
                series_cells = int(self.series_cells_entry.text())
            except ValueError:
                series_cells = None

        if series_cells is not None and series_cells > 0:
            min_v = series_cells * self.CELL_VOLTAGE_EMPTY
            max_v = series_cells * self.CELL_VOLTAGE_FULL
            self.min_voltage_info_label.setText(f"Empty V: {min_v:.1f} (0%)")
            self.max_voltage_info_label.setText(f"Full Charge V: {max_v:.1f} (100%)")
            return min_v, max_v, series_cells # Return valid values
        else:
            self.min_voltage_info_label.setText("Empty V: N/A")
            self.max_voltage_info_label.setText("N/A")
            return None, None, None


    def get_current_battery_percentage(self, voltage_override=None, nominal_voltage_override=None, capacity_override=None, capacity_type_override=None):
        """
        Determines current battery percentage and voltage based on user's input method (or provided overrides).
        This is a helper for both calculator tab and ride log.
        Returns (percentage, voltage) or (None, None) for invalid inputs.
        """
        # Get battery info from current profile (or use overrides if provided for ride logging)
        nominal_voltage_str = nominal_voltage_override if nominal_voltage_override is not None else self.voltage_entry.text()
        capacity_str = capacity_override if capacity_override is not None else self.capacity_entry.text()
        capacity_type = capacity_type_override if capacity_type_override is not None else self.capacity_type_combo.currentText()

        min_voltage, max_voltage, series_cells = self.get_derived_voltage_range_and_s()
        if min_voltage is None or max_voltage is None or series_cells is None:
            return None, None # Cannot proceed without valid battery range info

        if voltage_override is not None: # If a specific voltage is passed (e.g., from ride log)
            current_voltage = voltage_override
            try:
                # Calculate percentage from voltage
                voltage_range_diff = max_voltage - min_voltage
                if voltage_range_diff > 0:
                    percentage = ((current_voltage - min_voltage) / voltage_range_diff) * 100
                    percent = max(0.0, min(100.0, percentage)) # Clamp between 0 and 100
                else:
                    percent = 0.0 if current_voltage <= min_voltage else 100.0 # Handle edge case if range is zero or invalid
                return percent, current_voltage
            except ValueError:
                return None, None # Invalid voltage input
        elif self.percent_radio.isChecked() and voltage_override is None: # Standard calculator tab, percentage input
            try:
                percent = float(self.current_percentage_entry.text())
                if not 0 <= percent <= 100:
                    return None, None # Percentage out of range
                
                # Estimate current voltage from percentage
                estimated_current_voltage = min_voltage + (percent / 100) * (max_voltage - min_voltage)
                return percent, estimated_current_voltage

            except ValueError:
                return None, None # Invalid percentage input
        elif self.voltage_radio.isChecked() and voltage_override is None: # Standard calculator tab, voltage input
            try:
                current_voltage = float(self.current_voltage_entry.text())

                voltage_range_diff = max_voltage - min_voltage
                if voltage_range_diff > 0:
                    percentage = ((current_voltage - min_voltage) / voltage_range_diff) * 100
                    percent = max(0.0, min(100.0, percentage)) # Clamp between 0 and 100
                else:
                    percent = 0.0 if current_voltage <= min_voltage else 100.0 # Handle edge case if range is zero or invalid

                return percent, current_voltage
            except ValueError:
                return None, None # Invalid voltage input
        else:
            return None, None # Fallback for unknown state


    def calculate_percentage_after_charge(self, duration_hours):
        """Calculates the estimated battery percentage after a specified charging duration."""
        self.percentage_after_charge_label.setText("") # Clear previous result at the start

        try:
            nominal_voltage_str = self.voltage_entry.text()
            capacity_type = self.capacity_type_combo.currentText()
            capacity_str = self.capacity_entry.text()
            charge_rate_str = self.charge_rate_entry.text()

            # Convert inputs safely
            nominal_voltage = float(nominal_voltage_str) if nominal_voltage_str else 0.0
            capacity = float(capacity_str) if capacity_str else 0.0
            charge_rate = float(charge_rate_str) if charge_rate_str else 0.0

            if nominal_voltage <= 0 or capacity <= 0 or charge_rate <= 0:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress this specific message as it can be repetitive during initial load
                return

            total_capacity_wh = capacity if capacity_type == "Wh" else capacity * nominal_voltage
            total_capacity_ah = total_capacity_wh / nominal_voltage if nominal_voltage > 0 else 0

            if total_capacity_ah <= 0:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress repetitive message
                return

            current_percentage, _ = self.get_current_battery_percentage()
            if current_percentage is None:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress repetitive message
                return

            current_ah = total_capacity_ah * (current_percentage / 100)
            ah_charged_in_duration = charge_rate * duration_hours
            new_ah = current_ah + ah_charged_in_duration
            new_percentage = (new_ah / total_capacity_ah) * 100
            new_percentage = min(100.0, new_percentage) # Cap at 100%

            self.percentage_after_charge_label.setText(f"{new_percentage:.2f}") # Removed % here, added in init_ui

        except ValueError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
        except ZeroDivisionError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message

    def calculate_cutoff_metrics(self):
        """Calculates range to preferred cutoff and charge time from preferred cutoff."""
        self.range_to_cutoff_label.setText("")
        self.charge_time_from_cutoff_label.setText("")

        try:
            preferred_cutoff_str = self.preferred_cutoff_entry.text()
            preferred_cutoff_percentage = float(preferred_cutoff_str) if preferred_cutoff_str else 0.0

            # Update the display label for "Range to cutoff of XX%"
            if 0 <= preferred_cutoff_percentage <= 100:
                self.range_to_cutoff_title_label.setText(f"Range to cutoff of {preferred_cutoff_percentage:.0f}%:")
            else:
                self.range_to_cutoff_title_label.setText("Range to cutoff (Invalid %):") # Indicate error on the label itself


            if not (0 <= preferred_cutoff_percentage <= 100):
                if not self.is_initializing:
                    QMessageBox.warning(self, "Input Error", "Preferred Cutoff Percentage must be between 0 and 100.")
                self.range_to_cutoff_label.setText("N/A")
                self.charge_time_from_cutoff_label.setText("N/A")
                return

            current_percentage, _ = self.get_current_battery_percentage()
            if current_percentage is None:
                # Error message already handled by get_current_battery_percentage or other checks
                self.range_to_cutoff_label.setText("N/A")
                self.charge_time_from_cutoff_label.setText("N/A")
                return

            # Ensure current percentage is greater than cutoff for a meaningful range to cutoff calculation
            if current_percentage <= preferred_cutoff_percentage:
                self.range_to_cutoff_label.setText("N/A (At/Below Cutoff)")
            else:
                # Calculate range to cutoff
                nominal_voltage_str = self.voltage_entry.text()
                capacity_type = self.capacity_type_combo.currentText()
                capacity_str = self.capacity_entry.text()
                
                nominal_voltage = float(nominal_voltage_str) if nominal_voltage_str else 0.0
                capacity = float(capacity_str) if capacity_str else 0.0

                if nominal_voltage <= 0 or capacity <= 0:
                    if not self.is_initializing:
                        pass
                    self.range_to_cutoff_label.setText("N/A")
                    return
                
                total_energy_wh = capacity if capacity_type == "Wh" else capacity * nominal_voltage

                # Retrieve adjusted_wh_per_mile (from calculate_range, which updates self.efficiency_source_label)
                # It's better to ensure calculate_range has already run and populated full_charge_range and adjusted_wh_per_mile
                # If calculate_range fails, full_charge_range will be 0 or N/A
                if not hasattr(self, 'full_charge_range') or self.full_charge_range <= 0:
                    pass
                    self.range_to_cutoff_label.setText("N/A")
                    return
                
                # Calculate the percentage of battery capacity between current and cutoff
                percent_difference = current_percentage - preferred_cutoff_percentage
                
                # Calculate the Wh available in that percentage range
                wh_available_to_cutoff = total_energy_wh * (percent_difference / 100)

                # Use the same efficiency as the main range calculation
                # adjusted_wh_per_mile is obtained from calculate_range's logic
                # We need to ensure we have a valid adjusted_wh_per_mile here.
                # If calculate_range populated self.miles_per_wh_label, we can derive it.
                try:
                    miles_per_wh = float(self.miles_per_wh_label.text()) # Get the value already displayed
                    adjusted_wh_per_mile = 1 / miles_per_wh if miles_per_wh > 0 else 0
                except ValueError:
                    adjusted_wh_per_mile = 0

                if adjusted_wh_per_mile > 0:
                    range_to_cutoff = wh_available_to_cutoff / adjusted_wh_per_mile
                    self.range_to_cutoff_label.setText(f"{range_to_cutoff:.2f}")
                else:
                    self.range_to_cutoff_label.setText("N/A (Efficiency Error)")


            # Calculate charge time from cutoff
            charge_rate_str = self.charge_rate_entry.text()
            charge_rate = float(charge_rate_str) if charge_rate_str else 0.0

            if nominal_voltage <= 0 or capacity <= 0 or charge_rate <= 0:
                if not self.is_initializing:
                    pass
                self.charge_time_from_cutoff_label.setText("N/A")
                return

            total_capacity_wh = capacity if capacity_type == "Wh" else capacity * nominal_voltage
            total_capacity_ah = total_capacity_wh / nominal_voltage if nominal_voltage > 0 else 0

            if total_capacity_ah <= 0:
                if not self.is_initializing:
                    pass
                self.charge_time_from_cutoff_label.setText("N/A")
                return

            ah_to_charge_from_cutoff = total_capacity_ah * ((100 - preferred_cutoff_percentage) / 100)
            if charge_rate > 0:
                charge_time_from_cutoff = ah_to_charge_from_cutoff / charge_rate
                self.charge_time_from_cutoff_label.setText(self.format_time_to_hours_minutes(charge_time_from_cutoff))
            else:
                self.charge_time_from_cutoff_label.setText("N/A (Charger Rate is zero)")


        except ValueError:
            if not self.is_initializing:
                pass
            self.range_to_cutoff_label.setText("N/A")
            self.charge_time_from_cutoff_label.setText("N/A")
        except ZeroDivisionError:
            if not self.is_initializing:
                pass
            self.range_to_cutoff_label.setText("N/A")
            self.charge_time_from_cutoff_label.setText("N/A")
        except Exception as e:
            if not self.is_initializing:
                QMessageBox.critical(self, "Internal Error", f"An unexpected error occurred during cutoff calculation: {e}")
            self.range_to_cutoff_label.setText("Error")
            self.charge_time_from_cutoff_label.setText("Error")

    def update_breakdown(self):
        """Updates the breakdown section of the GUI with current input values and calculated derived values."""
        # Get raw input values
        nominal_voltage = self.voltage_entry.text()
        capacity_type = self.capacity_type_combo.currentText()
        capacity = self.capacity_entry.text()
        motor_wattage = self.motor_wattage_entry.text()
        wheel_diameter = self.wheel_diameter_entry.text()
        charge_rate = self.charge_rate_entry.text()
        preferred_cutoff = self.preferred_cutoff_entry.text()

        # Update labels with raw input values
        self.breakdown_voltage_label.setText(nominal_voltage)
        self.breakdown_motor_watts_label.setText(motor_wattage)
        self.breakdown_wheel_diameter_label.setText(f"{wheel_diameter} in" if wheel_diameter else "N/A")
        self.breakdown_charge_rate_label.setText(charge_rate)
        self.breakdown_preferred_cutoff_label.setText(f"{preferred_cutoff}%" if preferred_cutoff else "N/A")


        # Calculate and update derived values for breakdown
        min_v, max_v, series_cells = self.get_derived_voltage_range_and_s()
        # Ensure that min_v, max_v, and series_cells are not None before using them
        if series_cells is not None:
            self.breakdown_series_cells_label.setText(f"{series_cells}S")
        else:
            self.breakdown_series_cells_label.setText("N/A")

        if min_v is not None and max_v is not None:
            self.breakdown_min_max_voltage_label.setText(f"{min_v:.1f}V - {max_v:.1f}V")
        else:
            self.breakdown_min_max_voltage_label.setText("N/A")

        try:
            float_nominal_voltage = float(nominal_voltage) if nominal_voltage else 0.0
            float_capacity = float(capacity) if capacity else 0.0

            if capacity_type == "Ah":
                self.breakdown_ah_label.setText(f"{float_capacity:.2f}")
                wh = float_capacity * float_nominal_voltage if float_nominal_voltage > 0 else 0
                self.breakdown_wh_label.setText(f"{wh:.2f}")
            else: # Wh
                self.breakdown_wh_label.setText(f"{float_capacity:.2f}")
                ah = float_capacity / float_nominal_voltage if float_nominal_voltage > 0 else 0
                self.breakdown_ah_label.setText(f"{ah:.2f}")
        except ValueError:
            self.breakdown_ah_label.setText("N/A")
            self.breakdown_wh_label.setText("N/A")
        except ZeroDivisionError:
            self.breakdown_ah_label.setText("Div/0 Error")
            self.breakdown_wh_label.setText("Div/0 Error")

        current_percentage, actual_current_voltage = self.get_current_battery_percentage()
        if current_percentage is not None:
            # Update results section labels (removed from breakdown)
            self.current_state_percent_result_label.setText(f"{current_percentage:.2f}") # Only number, unit handled by label
            if actual_current_voltage is not None:
                self.current_state_voltage_result_label.setText(f"{actual_current_voltage:.2f}") # Only number for results, unit handled by label
            else:
                self.current_state_voltage_result_label.setText("N/A")
        else:
            self.current_state_percent_result_label.setText("N/A")
            self.current_state_voltage_result_label.setText("N/A")


        # Calculate and display preferred cutoff voltage
        if preferred_cutoff and min_v is not None and max_v is not None and (max_v - min_v) > 0:
            try:
                preferred_cutoff_percentage = float(preferred_cutoff)
                if 0 <= preferred_cutoff_percentage <= 100:
                    preferred_cutoff_voltage = min_v + (preferred_cutoff_percentage / 100) * (max_v - min_v)
                    self.breakdown_preferred_cutoff_voltage_label.setText(f"{preferred_cutoff_voltage:.2f}V")
                else:
                    self.breakdown_preferred_cutoff_voltage_label.setText("N/A (Invalid %)")
            except ValueError:
                self.breakdown_preferred_cutoff_voltage_label.setText("N/A")
        else:
            self.breakdown_preferred_cutoff_voltage_label.setText("N/A")

    def calculate_range(self):
        """Calculates and displays the estimated range of the vehicle."""
        # Always clear previous results at the start of calculation
        self.calculated_range_label.setText("")
        self.miles_per_wh_label.setText("")
        self.miles_per_ah_label.setText("")
        self.full_charge_range = 0 # Reset in case of error
        self.range_unit = "miles" # Reset to default unit

        try:
            nominal_voltage_str = self.voltage_entry.text()
            capacity_type = self.capacity_type_combo.currentText()
            capacity_str = self.capacity_entry.text()
            driving_style = self.driving_style_combo.currentText()
            wheel_diameter_str = self.wheel_diameter_entry.text()

            nominal_voltage = float(nominal_voltage_str) if nominal_voltage_str else 0.0
            capacity = float(capacity_str) if capacity_str else 0.0
            wheel_diameter = float(wheel_diameter_str) if wheel_diameter_str else 0.0
            
            if nominal_voltage <= 0 or capacity <= 0 or wheel_diameter <= 0:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress repetitive message
                # Update efficiency source to indicate an issue
                self.efficiency_source_label.setText("Error")
                return

            if capacity_type == "Wh":
                total_energy_wh = capacity
            else:  # capacity_type == "Ah"
                total_energy_wh = capacity * nominal_voltage

            # --- Determine adjusted_wh_per_mile based on source ---
            adjusted_wh_per_mile = 0.0
            if self.use_logged_efficiency and self.logged_wh_per_mile_average > 0:
                adjusted_wh_per_mile = self.logged_wh_per_mile_average
                self.efficiency_source_label.setText("Logged") # More concise
            else:
                # Calculate Adjusted Wh/mile based on Wheel Diameter and Driving Style (Predicted)
                interpolation_factor = (wheel_diameter - self.SMALL_WHEEL_REF) / (self.LARGE_WHEEL_REF - self.SMALL_WHEEL_REF)
                
                # Clamp factor between 0 and 1 to ensure it stays within our defined range
                interpolation_factor = max(0.0, min(1.0, interpolation_factor))

                base_wh_per_mile_small = self.SMALL_WHEEL_EFFICIENCY.get(driving_style)
                base_wh_per_mile_large = self.LARGE_WHEEL_EFFICIENCY.get(driving_style)

                if base_wh_per_mile_small is None or base_wh_per_mile_large is None:
                    if not self.is_initializing: # Suppress during initialization
                        QMessageBox.critical(self, "Error", "Invalid driving style selected for efficiency lookup in range calculation.")
                    self.efficiency_source_label.setText("Error")
                    return

                adjusted_wh_per_mile = (base_wh_per_mile_small * (1 - interpolation_factor) +
                                       base_wh_per_mile_large * interpolation_factor)
                self.efficiency_source_label.setText("Predicted")


            if adjusted_wh_per_mile <= 0:
                if not self.is_initializing: # Suppress during initialization
                    QMessageBox.critical(self, "Error", "Calculated efficiency (Wh/mile) must be greater than zero for range calculation.")
                self.efficiency_source_label.setText("Error")
                return

            estimated_range = total_energy_wh / adjusted_wh_per_mile
            calculated_unit = "miles"

            self.calculated_range_label.setText(f"{estimated_range:.2f}")
            self.calculated_range_unit_label.setText(calculated_unit)

            miles_per_wh = 1 / adjusted_wh_per_mile
            self.miles_per_wh_label.setText(f"{miles_per_wh:.2f}")

            miles_per_ah = nominal_voltage / adjusted_wh_per_mile if adjusted_wh_per_mile > 0 else 0
            self.miles_per_ah_label.setText(f"{miles_per_ah:.2f}")

            self.full_charge_range = estimated_range
            self.range_unit = calculated_unit

        except ValueError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
            self.efficiency_source_label.setText("Error")
        except ZeroDivisionError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
            self.efficiency_source_label.setText("Error")
        except Exception as e: # Catch any other unexpected errors
            if not self.is_initializing: # Suppress during initialization
                QMessageBox.critical(self, "Internal Error", f"An unexpected error occurred during range calculation: {e}")
            self.efficiency_source_label.setText("Error")

    def calculate_charge_time_and_remaining_range(self):
        """Calculates and displays remaining charge, range, and estimated time to full charge."""
        # Always clear previous results at the start
        self.charge_time_label.setText("")
        self.remaining_charge_percentage_label.setText("")
        self.remaining_range_label.setText("")

        current_percentage, current_voltage_val = self.get_current_battery_percentage()
        
        # Display warning if current battery state is invalid, then return from this function only
        if current_percentage is None:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
            return

        try:
            nominal_voltage_str = self.voltage_entry.text()
            capacity_type = self.capacity_type_combo.currentText()
            charge_rate_str = self.charge_rate_entry.text()
            capacity_str = self.capacity_entry.text()

            nominal_voltage = float(nominal_voltage_str) if nominal_voltage_str else 0.0
            charge_rate = float(charge_rate_str) if charge_rate_str else 0.0
            capacity = float(capacity_str) if capacity_str else 0.0
            
            # Check for invalid primary inputs that can prevent this entire calculation
            if nominal_voltage <= 0 or capacity <= 0 or charge_rate <= 0:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress repetitive message
                return

            capacity_ah = 0
            if capacity_type == "Wh":
                capacity_ah = capacity / nominal_voltage if nominal_voltage > 0 else 0
            else:
                capacity_ah = capacity

            # Ensure capacity_ah is valid before proceeding
            if capacity_ah <= 0:
                if not self.is_initializing: # Suppress during initialization
                    pass # Suppress repetitive message
                return

            remaining_capacity_ah_to_full = capacity_ah * (1 - (current_percentage / 100))
            estimated_charge_time = remaining_capacity_ah_to_full / charge_rate
            self.charge_time_label.setText(self.format_time_to_hours_minutes(estimated_charge_time))

            self.remaining_charge_percentage_label.setText(f"{100 - current_percentage:.2f}") # Removed % here, added in init_ui

            if hasattr(self, 'full_charge_range') and self.full_charge_range > 0:
                remaining_range = self.full_charge_range * (current_percentage / 100)
                self.remaining_range_label.setText(f"{remaining_range:.2f}")
                self.remaining_range_unit_label.setText(self.range_unit)
            else:
                self.remaining_range_label.setText("N/A (Full charge range not available or zero)")

        except ValueError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
        except ZeroDivisionError:
            if not self.is_initializing: # Suppress during initialization
                pass # Suppress repetitive message
        except Exception as e:
            if not self.is_initializing: # Suppress during initialization
                QMessageBox.critical(self, "Internal Error", f"An unexpected error occurred during charge time calculation: {e}")

    def clear_fields(self, keep_profile_name=False):
        """Clears all input fields, and output labels.
           If keep_profile_name is True, the profile selection is not reset."""
        # Clear input entries
        self.voltage_entry.clear()
        self.series_cells_entry.clear()
        self.capacity_entry.clear()
        self.charge_rate_entry.clear()
        self.charging_duration_combo.setCurrentText("")
        self.current_percentage_entry.setText("0") # Reset to 0
        self.current_voltage_entry.clear()
        self.motor_wattage_entry.clear()
        self.wheel_diameter_entry.clear()
        self.preferred_cutoff_entry.setText("25") # NEW: Reset cutoff to default
        
        # Reset comboboxes and radiobuttons to default values
        self.capacity_type_combo.setCurrentText("Wh")
        self.driving_style_combo.setCurrentText("Casual")
        self.percent_radio.setChecked(True) # Set percentage radio button

        # Update visibility and info labels based on cleared/default states
        self.toggle_charge_input()
        self.update_capacity_label()
        self.update_voltage_info_labels()

        # Clear output labels (now safe as they are initialized in __init__)
        self.calculated_range_label.setText("")
        self.remaining_range_label.setText("")
        self.remaining_charge_percentage_label.setText("")
        self.charge_time_label.setText("")
        self.miles_per_wh_label.setText("")
        self.miles_per_ah_label.setText("")
        self.percentage_after_charge_label.setText("")
        self.range_to_cutoff_label.setText("")
        self.charge_time_from_cutoff_label.setText("")
        self.current_state_percent_result_label.setText("")
        self.current_state_voltage_result_label.setText("")
        self.results_charge_duration_label.setText("")
        # Reset the dynamic label as well
        self.range_to_cutoff_title_label.setText("Range to cutoff of:")


        self.breakdown_voltage_label.setText("")
        self.breakdown_series_cells_label.setText("")
        self.breakdown_min_max_voltage_label.setText("")
        self.breakdown_ah_label.setText("N/A") # Reset to N/A
        self.breakdown_wh_label.setText("N/A") # Reset to N/A
        self.breakdown_motor_watts_label.setText("")
        self.breakdown_wheel_diameter_label.setText("")
        self.breakdown_charge_rate_label.setText("")
        self.breakdown_preferred_cutoff_label.setText("") # NEW: Clear breakdown cutoff
        self.breakdown_preferred_cutoff_voltage_label.setText("") # NEW: Clear breakdown cutoff voltage
        self.efficiency_source_label.setText("Predicted") # Reset efficiency source
        self.reset_efficiency_source(show_message=False) # Reset the internal flag too, without a message
        
        # Clear ride log fields and table on the ride log tab as well
        self.clear_ride_log_fields()
        self.update_ride_log_table() # This will clear it if no data is loaded
        self.calculate_average_efficiency() # This will reset the average label

        # NEW: Clear last ride display
        self.last_ride_data = {} # Clear the stored data
        self.update_last_ride_display()


    def export_breakdown_to_file(self):
        """Exports the current breakdown information to a text file."""
        breakdown_text = "--- Vehicle Breakdown ---\n"
        breakdown_text += f"Nominal Voltage: {self.breakdown_voltage_label.text()}\n"
        breakdown_text += f"Cells in Series: {self.breakdown_series_cells_label.text()}\n"
        breakdown_text += f"Min/Max Voltage (Calculated): {self.breakdown_min_max_voltage_label.text()}\n"
        breakdown_text += f"Ah: {self.breakdown_ah_label.text()}\n"
        breakdown_text += f"Wh: {self.breakdown_wh_label.text()}\n"
        breakdown_text += f"Motor Watts: {self.breakdown_motor_watts_label.text()}\n"
        breakdown_text += f"  Wheel Diameter: {self.breakdown_wheel_diameter_label.text()}\n"
        breakdown_text += f"Charge Rate: {self.breakdown_charge_rate_label.text()}\n"
        breakdown_text += f"Preferred Cutoff %: {self.breakdown_preferred_cutoff_label.text()}\n" # NEW: Add cutoff to export
        breakdown_text += f"Preferred Cutoff V: {self.breakdown_preferred_cutoff_voltage_label.text()}\n" # NEW: Add cutoff voltage to export
        breakdown_text += f"Efficiency Source: {self.efficiency_source_label.text()}\n" # Include efficiency source

        # Add results section values to the export for completeness, especially moved ones
        breakdown_text += "\n--- Current Results (Summary) ---\n"
        breakdown_text += f"Estimated Full Range: {self.calculated_range_label.text()} {self.calculated_range_unit_label.text()}\n"
        breakdown_text += f"Remaining Range: {self.remaining_range_label.text()} {self.remaining_range_unit_label.text()}\n"
        # Use the dynamic label's text for export
        breakdown_text += f"{self.range_to_cutoff_title_label.text().replace(':', '')}: {self.range_to_cutoff_label.text()} {self.range_to_cutoff_unit_label.text()}\n"
        breakdown_text += f"Current %: {self.current_state_percent_result_label.text()}%\n" # Added % directly here
        breakdown_text += f"Current V: {self.current_state_voltage_result_label.text()}V\n" # Added V directly here
        breakdown_text += f"Remaining Charge to 100%: {self.remaining_charge_percentage_label.text()}%\n" # Added % directly here
        breakdown_text += f"Estimated Charge Time to 100%: {self.charge_time_label.text()}\n"
        breakdown_text += f"Charge Duration: {self.results_charge_duration_label.text()}\n"
        breakdown_text += f"Percentage after set charge duration: {self.percentage_after_charge_label.text()}%\n" # Added % directly here
        breakdown_text += f"Miles/Wh: {self.miles_per_wh_label.text()}\n"
        breakdown_text += f"Miles/Ah: {self.miles_per_ah_label.text()}\n"
        breakdown_text += f"Efficiency Source: {self.efficiency_source_label.text()}\n"

        # NEW: Add last ride details to export
        if self.last_ride_data:
            breakdown_text += "\n--- Last Logged Ride ---\n"
            breakdown_text += f"Last Ride Date: {self.last_ride_data.get('date', 'N/A')}\n"
            breakdown_text += f"Last Ride Distance: {self.last_ride_data.get('distance_miles', 'N/A')} miles\n"
            breakdown_text += f"Last Ride Wh Consumed: {self.last_ride_data.get('wh_consumed', 'N/A')} Wh\n"
            breakdown_text += f"Last Ride Wh/mile: {self.last_ride_data.get('wh_per_mile', 'N/A')} Wh/mile\n"


        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Vehicle Breakdown", "", "Text files (*.txt);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(breakdown_text)
                QMessageBox.information(self, "Export Successful", f"Breakdown saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save breakdown: {e}")
        else:
            QMessageBox.information(self, "Export Cancelled", "Breakdown export cancelled.")

    def log_ride(self):
        """Logs a new ride entry based on the inputs in the Ride Log tab."""
        ride_date = self.ride_date_edit.dateTime().toString("yyyy-MM-dd HH:mm")
        
        try:
            distance_miles = float(self.ride_distance_entry.text())
            if distance_miles <= 0:
                QMessageBox.warning(self, "Input Error", "Distance must be a positive number.")
                return

            start_state_type = "percentage" if self.ride_start_state_type_combo.currentText() == "Percentage (%)" else "voltage"
            start_value = float(self.ride_start_value_entry.text())

            end_state_type = "percentage" if self.ride_end_state_type_combo.currentText() == "Percentage (%)" else "voltage"
            end_value = float(self.ride_end_value_entry.text())

            logged_driving_style = self.ride_driving_style_combo.currentText() # Get new riding style input

            notes = self.ride_notes_entry.text().strip()

            # Get battery full capacity from the current profile on the Calculator tab
            nominal_voltage_str = self.voltage_entry.text()
            capacity_type = self.capacity_type_combo.currentText()
            capacity_str = self.capacity_entry.text()

            nominal_voltage = float(nominal_voltage_str) if nominal_voltage_str else 0.0
            battery_capacity = float(capacity_str) if capacity_str else 0.0

            if nominal_voltage <= 0 or battery_capacity <= 0:
                QMessageBox.warning(self, "Battery Info Missing", "Please enter valid Nominal Voltage and Battery Capacity in the 'Battery Calculator' tab before logging a ride.")
                return

            total_battery_wh = battery_capacity if capacity_type == "Wh" else battery_capacity * nominal_voltage
            
            # Convert start/end values to percentages (if voltage, use current battery info)
            min_v, max_v, series_cells = self.get_derived_voltage_range_and_s()
            if min_v is None or max_v is None or (max_v - min_v) <= 0: # Ensure valid voltage range for conversion
                QMessageBox.warning(self, "Battery Info Error", "Could not derive min/max voltage from Battery Calculator tab or voltage range is invalid. Please check voltage and series cells inputs.")
                return

            start_percent = 0.0
            if start_state_type == "percentage":
                if not (0 <= start_value <= 100):
                    QMessageBox.warning(self, "Input Error", "Start percentage must be between 0 and 100.")
                    return
                start_percent = start_value
            else: # voltage
                if not (min_v <= start_value <= max_v):
                    QMessageBox.warning(self, "Input Error", f"Start voltage ({start_value}V) is outside expected range ({min_v:.1f}V - {max_v:.1f}V).")
                    return
                start_percent = ((start_value - min_v) / (max_v - min_v)) * 100

            end_percent = 0.0
            if end_state_type == "percentage":
                if not (0 <= end_value <= 100):
                    QMessageBox.warning(self, "Input Error", "End percentage must be between 0 and 100.")
                    return
                end_percent = end_value
            else: # voltage
                if not (min_v <= end_value <= max_v):
                    QMessageBox.warning(self, "Input Error", f"End voltage ({end_value}V) is outside expected range ({min_v:.1f}V - {max_v:.1f}V).")
                    return
                end_percent = ((end_value - min_v) / (max_v - min_v)) * 100
            
            if end_percent >= start_percent:
                QMessageBox.warning(self, "Input Error", "End battery state must be lower than start battery state for a consumed ride.")
                return

            # Calculate Wh consumed for this ride
            wh_consumed = total_battery_wh * ((start_percent - end_percent) / 100)
            
            if wh_consumed <= 0:
                 QMessageBox.warning(self, "Calculation Error", "Calculated Wh consumed is zero or negative. Check start/end battery states or battery capacity.")
                 return

            # Calculate Wh/mile for this specific ride
            wh_per_mile = wh_consumed / distance_miles

            # Add ride data to the current profile's ride_log
            ride_data = {
                "date": ride_date,
                "distance_miles": distance_miles,
                "start_state_type": start_state_type,
                "start_value": start_value,
                "end_state_type": end_state_type,
                "end_value": end_value,
                "start_percent": round(start_percent, 2), # Store calculated percentages for display
                "end_percent": round(end_percent, 2),
                "wh_consumed": round(wh_consumed, 2),
                "wh_per_mile": round(wh_per_mile, 2), # Store for easy display/calculation
                "riding_style": logged_driving_style, # NEW: Store riding style
                "notes": notes
            }
            
            # Ensure 'ride_log' exists for the current profile
            if "ride_log" not in self.all_profiles[self.current_profile_name]:
                self.all_profiles[self.current_profile_name]["ride_log"] = []
            
            self.all_profiles[self.current_profile_name]["ride_log"].append(ride_data)
            
            # CRITICAL FIX: Update last_ride_data within the profile's dictionary explicitly
            self.all_profiles[self.current_profile_name]["last_ride_data"] = ride_data
            self.last_ride_data = ride_data # Also keep the instance variable updated for immediate display
            
            self.update_last_ride_display() # Update display with the new last ride data

            # Update the table and save the profiles
            self.update_ride_log_table()
            self.calculate_average_efficiency()
            self._save_all_profiles_to_file(self.current_profile_name) # This now saves the updated all_profiles

            self.clear_ride_log_fields() # Clear input fields after successful log
            QMessageBox.information(self, "Ride Logged", "Ride successfully logged!")

        except ValueError:
            QMessageBox.critical(self, "Input Error", "Please enter valid numeric values for Distance and Battery States.")
        except ZeroDivisionError:
            QMessageBox.critical(self, "Error Logging Ride", "Division by zero. Check battery capacity or voltage range in Calculator tab.")
        except Exception as e:
            QMessageBox.critical(self, "Error Logging Ride", f"An unexpected error occurred: {e}")

    def clear_ride_log_fields(self):
        """Clears the input fields for a new ride entry."""
        self.ride_date_edit.setDateTime(QDateTime.currentDateTime())
        self.ride_distance_entry.clear()
        self.ride_start_value_entry.clear()
        self.ride_end_value_entry.clear()
        self.ride_notes_entry.clear()
        self.ride_start_state_type_combo.setCurrentIndex(0) # Reset to Percentage
        self.ride_end_state_type_combo.setCurrentIndex(0) # Reset to Percentage
        self.ride_driving_style_combo.setCurrentText("Casual") # Reset riding style to default

    def update_ride_log_table(self):
        """Populates the QTableWidget with ride data from the current profile."""
        self.ride_log_table.setRowCount(0) # Clear existing rows
        current_profile_log = self.all_profiles.get(self.current_profile_name, {}).get("ride_log", [])

        self.ride_log_table.setRowCount(len(current_profile_log))
        for row_idx, ride in enumerate(current_profile_log):
            self.ride_log_table.setItem(row_idx, 0, QTableWidgetItem(ride.get("date", "N/A")))
            self.ride_log_table.setItem(row_idx, 1, QTableWidgetItem(f"{ride.get('distance_miles', 0):.2f}"))
            self.ride_log_table.setItem(row_idx, 2, QTableWidgetItem(f"{ride.get('start_percent', 0):.2f}%"))
            self.ride_log_table.setItem(row_idx, 3, QTableWidgetItem(f"{ride.get('end_percent', 0):.2f}%"))
            self.ride_log_table.setItem(row_idx, 4, QTableWidgetItem(f"{ride.get('wh_consumed', 0):.2f}"))
            self.ride_log_table.setItem(row_idx, 5, QTableWidgetItem(f"{ride.get('wh_per_mile', 0):.2f}"))
            self.ride_log_table.setItem(row_idx, 6, QTableWidgetItem(ride.get("riding_style", "N/A"))) # NEW: Set Riding Style
            self.ride_log_table.setItem(row_idx, 7, QTableWidgetItem(ride.get("notes", ""))) # Shifted to column 7

        # Adjust column widths to content
        self.ride_log_table.resizeColumnsToContents()

    def delete_selected_rides(self):
        """Deletes the selected ride(s) from the current profile's log."""
        selected_rows = sorted(set(index.row() for index in self.ride_log_table.selectedIndexes()), reverse=True)
        
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select at least one ride to delete.")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete {len(selected_rows)} selected ride(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            current_log = self.all_profiles[self.current_profile_name].get("ride_log", [])
            for row_idx in selected_rows:
                if 0 <= row_idx < len(current_log):
                    current_log.pop(row_idx)
            
            self.all_profiles[self.current_profile_name]["ride_log"] = current_log
            self.update_ride_log_table()
            self.calculate_average_efficiency()
            
            # Logic to correctly update last_ride_data after deletion
            if current_log:
                self.last_ride_data = current_log[-1] # The last remaining ride
            else:
                self.last_ride_data = {} # No rides left

            # Ensure the profile's saved data is also updated
            self.all_profiles[self.current_profile_name]["last_ride_data"] = self.last_ride_data
            self.update_last_ride_display() # Update display after logic
            
            self._save_all_profiles_to_file(self.current_profile_name)
            QMessageBox.information(self, "Deleted", f"{len(selected_rows)} ride(s) deleted.")

    def calculate_average_efficiency(self):
        """Calculates the average Wh/mile and Miles/Wh from all logged rides in the current profile."""
        current_profile_log = self.all_profiles.get(self.current_profile_name, {}).get("ride_log", [])
        
        total_wh_consumed = 0.0
        total_distance_miles = 0.0

        for ride in current_profile_log:
            try:
                wh = float(ride.get("wh_consumed", 0))
                dist = float(ride.get("distance_miles", 0))
                total_wh_consumed += wh
                total_distance_miles += dist
            except (ValueError, TypeError):
                # Skip invalid entries, but could log a warning if needed
                continue

        if total_distance_miles > 0:
            average_wh_per_mile = total_wh_consumed / total_distance_miles
            average_miles_per_wh = 1 / average_wh_per_mile
            self.average_wh_per_mile_label.setText(f"Average Wh/mile: {average_wh_per_mile:.2f}")
            self.average_miles_per_wh_label.setText(f"Average Miles/Wh: {average_miles_per_wh:.2f}")
            self.logged_wh_per_mile_average = average_wh_per_mile # Store for apply function
        else:
            self.average_wh_per_mile_label.setText("Average Wh/mile: N/A (No rides logged or invalid data)")
            self.average_miles_per_wh_label.setText("Average Miles/Wh: N/A (No rides logged or invalid data)")
            self.logged_wh_per_mile_average = 0.0 # Reset stored average

    def apply_logged_efficiency_to_calculator(self):
        """Applies the calculated average Wh/mile from the ride log to the calculator tab."""
        if self.logged_wh_per_mile_average > 0:
            self.use_logged_efficiency = True
            QMessageBox.information(self, "Efficiency Applied",
                                    f"Average efficiency ({self.logged_wh_per_mile_average:.2f} Wh/mile) from logged rides will now be used for range calculations on the Battery Calculator tab.")
            self.calculate_all() # Recalculate range with the new efficiency
        else:
            QMessageBox.warning(self, "No Logged Data",
                                "No valid logged ride data available to calculate an average efficiency. Please log some rides first.")
            self.use_logged_efficiency = False
            self.efficiency_source_label.setText("Predicted") # Ensure label reflects this

    def reset_efficiency_source(self, show_message=True):
        """Resets the calculator to use predicted efficiency (based on driving style/wheel diameter).
           'show_message' controls whether a QMessageBox is displayed."""
        self.use_logged_efficiency = False
        self.logged_wh_per_mile_average = 0.0
        self.efficiency_source_label.setText("Predicted")
        self.calculate_all() # Recalculate range with predicted efficiency
        if show_message:
            QMessageBox.information(self, "Efficiency Reset", "Calculator is now using predicted efficiency based on driving style.")

    def update_last_ride_display(self):
        """Updates the labels in the 'Last Logged Ride' section of the Breakdown column."""
        if self.last_ride_data:
            self.breakdown_last_ride_date_label.setText(self.last_ride_data.get('date', 'N/A'))
            self.breakdown_last_ride_distance_label.setText(f"{self.last_ride_data.get('distance_miles', 0):.2f} miles")
            self.breakdown_last_ride_wh_label.setText(f"{self.last_ride_data.get('wh_consumed', 0):.2f} Wh")
            self.breakdown_last_ride_wh_per_mile_label.setText(f"{self.last_ride_data.get('wh_per_mile', 0):.2f} Wh/mile")
        else:
            self.breakdown_last_ride_date_label.setText("N/A")
            self.breakdown_last_ride_distance_label.setText("N/A")
            self.breakdown_last_ride_wh_label.setText("N/A")
            self.breakdown_last_ride_wh_per_mile_label.setText("N/A")

    def export_ride_log_to_file(self):
        """Exports the current profile's ride log to a JSON file."""
        current_log = self.all_profiles.get(self.current_profile_name, {}).get("ride_log", [])
        if not current_log:
            QMessageBox.information(self, "Export Ride Log", "No ride log data to export for the current profile.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Ride Log", f"{self.current_profile_name}_ride_log.json", "JSON files (*.json);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(current_log, f, indent=4)
                QMessageBox.information(self, "Export Successful", f"Ride log exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export ride log: {e}")
        else:
            QMessageBox.information(self, "Export Cancelled", "Ride log export cancelled.")

    def import_ride_log_from_file(self):
        """Imports ride log data from a JSON file and appends it to the current profile's log."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Ride Log", "", "JSON files (*.json);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    imported_log = json.load(f)
                
                if not isinstance(imported_log, list):
                    QMessageBox.critical(self, "Import Error", "Invalid file format. The file should contain a JSON list of ride entries.")
                    return

                # Basic validation for imported data structure
                for ride_entry in imported_log:
                    # Check for mandatory keys needed for calculations and display
                    mandatory_keys = ["date", "distance_miles", "start_percent", "end_percent", "wh_consumed", "wh_per_mile", "riding_style"]
                    if not isinstance(ride_entry, dict) or not all(key in ride_entry for key in mandatory_keys):
                        # Attempt to gracefully handle missing keys by setting defaults if possible
                        ride_entry.setdefault("date", "N/A")
                        ride_entry.setdefault("distance_miles", 0.0)
                        ride_entry.setdefault("start_percent", 0.0)
                        ride_entry.setdefault("end_percent", 0.0)
                        ride_entry.setdefault("wh_consumed", 0.0)
                        ride_entry.setdefault("wh_per_mile", 0.0)
                        ride_entry.setdefault("riding_style", "N/A")
                        ride_entry.setdefault("notes", "") # Also ensure notes field is present

                        # For older entries that might not have start_state_type/start_value/end_state_type/end_value
                        # Try to infer if possible, or set a default. This requires more context, so for now,
                        # just ensure they exist to prevent errors if logic relies on them.
                        ride_entry.setdefault("start_state_type", "percentage")
                        ride_entry.setdefault("start_value", ride_entry.get("start_percent", 0.0))
                        ride_entry.setdefault("end_state_type", "percentage")
                        ride_entry.setdefault("end_value", ride_entry.get("end_percent", 0.0))

                        QMessageBox.warning(self, "Import Warning", "Some imported entries might be missing expected fields. Defaults have been applied where possible.")
                        # No `break` here, continue to try and import other valid entries
                
                current_profile_log = self.all_profiles.get(self.current_profile_name, {}).get("ride_log", [])
                current_profile_log.extend(imported_log) # Append new rides

                # Update the ride_log in the current profile
                self.all_profiles[self.current_profile_name]["ride_log"] = current_profile_log
                
                # Update last_ride_data if new rides were imported
                if current_profile_log: # Check if log has any rides after import
                    self.last_ride_data = current_profile_log[-1] # Set last ride to the very last one after import
                else:
                    self.last_ride_data = {} # No rides in log

                # Ensure the profile's saved data is also updated
                self.all_profiles[self.current_profile_name]["last_ride_data"] = self.last_ride_data

                self.update_ride_log_table()
                self.calculate_average_efficiency()
                self.update_last_ride_display() # Refresh last ride display
                self._save_all_profiles_to_file(self.current_profile_name) # Save the updated profile

                QMessageBox.information(self, "Import Successful", f"Ride log imported from:\n{file_path}")

            except FileNotFoundError:
                QMessageBox.critical(self, "Import Error", "File not found.")
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Import Error", "Invalid JSON format in the selected file.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"An unexpected error occurred during import: {e}")
        else:
            QMessageBox.information(self, "Import Cancelled", "Ride log import cancelled.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BatteryCalculatorGUI()
    window.show()
    sys.exit(app.exec())
