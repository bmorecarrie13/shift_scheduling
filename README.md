# Shift Scheduling Optimization Model

## Overview
This project provides a Python-based optimization model for scheduling staff shifts while maximizing demand coverage and minimizing overtime rates. It uses Google OR-Tools' Mixed-Integer Programming (MIP) solver to handle complex constraints and optimize the scheduling process. The primary goal is to achieve efficient workforce allocation while adhering to business rules such as shift durations, rest periods, and demand coverage.

---

## Features
- Ensures demand coverage for each hour of operation.
- Enforces minimum and maximum shift lengths.
- Manages staff rest periods between shifts.
- Supports overtime policies and role-based constraints.
- Balances weekly workload with constraints on maximum shifts per day and days per week.
- Outputs optimized schedules in CSV format.

---

## Objective Functions
1. **Weekly Demand Coverage (WDC)**:
   - Maximize the average demand coverage per hour across all operational hours of the week.

2. **Weekly Overtime Rate (WOR)**:
   - Minimize the ratio of total overtime hours to total scheduled hours.


---

## Input Files
1. **Demand Data (`demand.csv`)**:
   - Columns:
     - `date_time`: The datetime of demand.
     - `demand`: Expected demand at the given datetime.

2. **Staff Data (`staff.csv`)**:
   - Columns:
     - `staff_id`: Unique identifier for each staff member.
     - `role`: Staff role (used for overtime eligibility).
     - `hourly_wage`: Regular hourly wage.
     - `overtime_hourly_wage`: Overtime hourly wage.

---

## Constraints
### 1. **Shift Start Constraints**:
- A staff member can only work during an hour if they have started a shift within the past `MAX_SHIFT_HOURS`.

### 2. **Rest Periods**:
- Staff must rest for at least `MIN_REST_HOURS` between consecutive shifts.
- Rest periods extend if overtime is involved.

### 3. **Minimum Shift Hours**:
- Each shift must last at least `MIN_SHIFT_HOURS`.

### 4. **Overtime**:
- Only eligible roles can work overtime.
- Overtime starts after `overtime_hours_start` hours in a shift.

### 5. **Daily and Weekly Limits**:
- Maximum `MAX_SHIFTS_PER_DAY` per staff member.
- Maximum `MAX_DAYS_PER_WEEK` per staff member.

### 6. **Demand Coverage**:
- At least `MIN_STAFF_PER_HOUR` staff must be scheduled during any hour.
- Additional staff are assigned if demand exceeds `MIN_STAFF_PER_HOUR`.

---

## Code Structure
### **`Model` Class**
- **`__init__()`**:
  - Initializes demand and staff data.
  - Prepares demand dictionary and other inputs.

- **`schedule_shifts()`**:
  - Main function to set up and solve the optimization problem.
  - Defines decision variables, constraints, and objective function.

- **`add_variables()`**:
  - Defines decision variables:
    - `x_start[i][t]`: Binary variable indicating if staff `i` starts a shift at time `t`.
    - `x[i][t]`: Binary variable indicating if staff `i` is working at time `t`.
    - `x_ot[i][t]`: Binary variable indicating if staff `i` is working overtime at time `t`.
    - `y1[t]`: Integer variable for demand shortage at time `t`, up to 1.
    - `y2[t]`: Integer variable for demand shortage at time `t`, over 1 (to prioritise a demand shortfall of 1 in more hours than over more than 1 for a single hour).

- **`add_constraints()`**:
  - Implements all constraints described above.

- **`solve()`**:
  - Solves the optimization problem.
  - Outputs metrics (WDC, WOR, total cost) and schedules in CSV format.

---

## Outputs
1. **Metrics**:
   - `WDC`: Weekly Demand Coverage.
   - `WOR`: Weekly Overtime Rate.
   - `total_cost`: Total labor cost, including overtime.

2. **Schedule File (`shift.csv`)**:
   - Columns:
     - `staff_id`: ID of the staff member.
     - `start_date_time`: Start time of the shift.
     - `end_date_time`: End time of the shift.

---

## Usage

**Important: Assumes you have python3 installed!**

1. **Set Up Virtual Environment**:
   Create and activate a virtual environment to isolate dependencies:
   ```bash
   python3 -m venv env
   source env/bin/activate  # On Windows: .\env\Scripts\activate
   ```

2. **Install Dependencies**:
   Use the `requirements.txt` file to install the necessary dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Prepare Input Files**:
   - Place `demand.csv` and `staff.csv` in the `data` directory.
   - In the **future**, `ARGPARSE` will be installed and you can pass a file path in from the command line.

4. **Run the Model**:
   Execute the script:
   ```bash
   python3 shifts_scheduling.py
   ```

5. **View Outputs**:
   - Check `output/shift.csv` for the optimized schedule.
   - Metrics are printed to the console and stored in `output/metrics.json`.

---

## Makefile

### Usage:
- **Set up the environment**:
  ```bash
  make setup
  ```
- **Run the script**:
  ```bash
  make run
  ```
- **Clean up**:
  ```bash
  make clean
  ```
- **Run Unit Tests**:
  ```bash
  make test
  ```
---

## Customization
- Modify constants in the `config` module to adjust constraints and solver behavior:
  - `MIN_SHIFT_HOURS`, `MAX_SHIFT_HOURS`
  - `MIN_REST_HOURS`, `MAX_SHIFTS_PER_DAY`, etc.

---

## Limitations
- The model assumes that all input data is preprocessed and clean.
- Scalability depends on the size of demand and staff datasets; larger datasets may require longer solve times or higher computational resources.

---

## References
- Google OR-Tools Documentation: [https://developers.google.com/optimization](https://developers.google.com/optimization)

