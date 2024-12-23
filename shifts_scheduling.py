import os
import time
import json
from collections import defaultdict
from typing import Dict, List

import pandas as pd
from ortools.linear_solver import pywraplp

from config import MIN_SHIFT_HOURS, MAX_SHIFT_HOURS, MIN_REST_HOURS, \
    ROLE_OT_PROHIBITED, MIN_STAFF_PER_HOUR, SOLVE_TIME_LIMIT, SOLVER, DEBUG, \
    MAX_DAYS_PER_WEEK, RELATIVE_MIP_GAP, MAX_SHIFTS_PER_DAY, W1


class Model:
    '''
    Schedule Shifts Class
    '''

    def __init__(self, demand_df: pd.DataFrame,
                 staff_df: pd.DataFrame):

        # Format inputs
        demand_df['date_time'] = pd.to_datetime(demand_df['date_time'])
        demand_df['bus_day'] = demand_df['date_time'].dt.date
        demand_df['week'] = (
            (demand_df['date_time'] - demand_df['date_time'].min()).dt.days // 7) + 1

        self.M = len(staff_df)
        self.demand_dict = demand_df.set_index('date_time')['demand'].to_dict()
        self.demand_df = demand_df
        self.staff_df = staff_df

    def schedule_shifts(self, timeout=SOLVE_TIME_LIMIT) -> Dict:
        '''
        Schedule Shifts main function
        Returns metrics and a CSV with the optimised schedule
        '''

        # Create the solver
        solver = pywraplp.Solver.CreateSolver(SOLVER)

        if not solver:
            print('Solver not created.')
            raise ValueError('Solver could not be created')

        # Dictionaries for decision variables
        x_start = defaultdict(dict)
        x = defaultdict(dict)
        x_ot = defaultdict(dict)
        x_day = defaultdict(dict)
        y1 = {}
        y2 = {}

        self.add_variables(solver, x_start, x, x_ot, y1, y2, x_day)
        self.add_constraints(solver, x_start, x, x_ot, y1, y2, x_day)

        # --
        # Objective function:
        # Maximise (AVG) Demand Coverage (scheduled hours/ demand per hour)
        # and Minimise the Ratio of OT hours to scheduled hours
        #  --> minimise number of staff short (y) + number of over time hours (x_ot)
        solver.Minimize(
            sum(
                (W1*(y1[dt]+2*y2[dt]) + (1-W1)*sum(x_ot[i][dt]
                 for i in range(self.M))) / self.demand_dict[dt]
                for dt in self.demand_dict if self.demand_dict[dt]
            )
        )

        metrics = self.solve(solver, x_start, x, x_ot, timeout)
        return metrics

    def add_variables(
            self, solver,
            x_start, x, x_ot, y1, y2, x_day
    ) -> None:
        '''
        Add variables to model
        '''

        for i in range(self.M):
            for j, dt in enumerate(self.demand_df['date_time']):

                # Variable >> x_start = 1 if staff i starts shift at dt
                x_start[i][dt] = solver.IntVar(0, 1, f'x_start{i}_{j}')
                #  shift must end in the same business day
                if pd.to_datetime((dt + pd.Timedelta(hours=MIN_SHIFT_HOURS))).date() > self.demand_df.iloc[j]['bus_day']:
                    x_start[i][dt].SetBounds(0, 0)

                # Variable >>  x = 1 if staff i is working during dt
                x[i][dt] = solver.BoolVar(f'x{i}_{j}')

                # Variable >>  x_ot = 1 if staff i is working overtime during dt
                x_ot[i][dt] = solver.NumVar(0, 1, f'x_ot{i}_{j}')

                # set bounds of x_ot:
                # ex, Staff with “Branch Manager” roles cannot work overtime hours
                # can't work overtime in the first MIN_SHIFT_HOURS of the day
                if self.staff_df.iloc[i]['role'] in ROLE_OT_PROHIBITED \
                        or dt.hour < MIN_SHIFT_HOURS:
                    x_ot[i][dt].SetBounds(0, 0)

                # last staff member
                if i == (self.M - 1):
                    # Variable >>  y = number of staff short in hour dt
                    #  y1 at most 1 staff, y2 more than 1 staff
                    y1[dt] = solver.IntVar(
                        0,
                        1,
                        f'y1_{j}'
                    )

                    y2[dt] = solver.IntVar(
                        0,
                        max(0, self.demand_dict[dt] -
                            min(self.M, MIN_STAFF_PER_HOUR-1)),
                        f'y2_{j}'
                    )
            # create a variable for each unique business day
            # x_day = 1 if staff i is working during some hours on this business day
            for d, bus_day in enumerate(self.demand_df['bus_day'].unique().tolist()):
                x_day[i][pd.to_datetime(bus_day)] = solver.BoolVar(
                    f'x_day{i}_{d}')
                x_day[i][pd.to_datetime(bus_day)].SetBranchingPriority(1)

    def add_constraints(
            self, solver,
            x_start, x, x_ot, y1, y2, x_day
    ) -> None:
        '''
        Builds all the constraints and adds to the model
        '''

        for i in range(self.M):

            last_seen_date = None

            for j, dt in enumerate(self.demand_dict):

                bus_day = pd.to_datetime(self.demand_df.iloc[j]['bus_day'])
                bus_eod = pd.to_datetime(bus_day + pd.Timedelta(hours=23))

                # Constraint >> If x=1, then x_start must be 1 in the past 12 hours
                # to link x_start with x
                past_dts = self.get_subset_dts(
                    min_dt=max(bus_day, dt -
                               pd.Timedelta(hours=MAX_SHIFT_HOURS - 1)),
                    max_dt=dt,
                    max_length=MAX_SHIFT_HOURS
                )
                solver.Add(
                    x[i][dt] <= sum(x_start[i][p_dt] for p_dt in past_dts),
                    name=f"past{i}_{j}"
                )

                # Constraint >> rest based on regular shift
                # x_start = 0 for next MIN_SHIFT_HOURS + MIN_REST_HOURS if x_start = 0 in dt
                # satisfies: the same staff must rest (not work a shift) for at least 4hrs
                # between any two consecutive shifts
                rest_dts = self.get_subset_dts(
                    min_dt=dt + pd.Timedelta(hours=1),
                    max_dt=dt +
                    pd.Timedelta(hours=MIN_SHIFT_HOURS + MIN_REST_HOURS - 1),
                    max_length=MIN_SHIFT_HOURS + MIN_REST_HOURS - 1
                )
                solver.Add(
                    sum(x_start[i][rest_dt] for rest_dt in rest_dts) <= len(
                        rest_dts) * (1 - x_start[i][dt]),
                    name=f"rest{i}_{j}"
                )

                # Constraint >> Each shift must last at least 9hrs
                shift_dts = self.get_subset_dts(
                    min_dt=dt,
                    max_dt=dt + pd.Timedelta(hours=MIN_SHIFT_HOURS - 1),
                    max_length=MIN_SHIFT_HOURS
                )
                solver.Add(
                    sum(x[i][s_dt] for s_dt in shift_dts) >= len(
                        shift_dts) * x_start[i][dt],
                    name=f"min_shift{i}_{j}"
                )

                # loop over potential overtime hours
                potential_overtime_dts = self.get_subset_dts(
                    min_dt=max(shift_dts) + pd.Timedelta(hours=1),
                    max_dt=min(bus_eod, max(
                        shift_dts) + pd.Timedelta(hours=MAX_SHIFT_HOURS - MIN_SHIFT_HOURS + 1)),
                    max_length=MAX_SHIFT_HOURS - MIN_SHIFT_HOURS + 1
                )
                additional_rest_dts = self.get_subset_dts(
                    min_dt=max(rest_dts) + pd.Timedelta(hours=1),
                    max_dt=max(rest_dts) + pd.Timedelta(hours=MIN_REST_HOURS),
                    max_length=MIN_REST_HOURS
                ) if len(rest_dts) else []

                for o, overtime_dt in enumerate(potential_overtime_dts):
                    # Constraint >> ensure consecutive hours are scheduled
                    solver.Add(
                        1 + x[i][overtime_dt + pd.Timedelta(hours=-1)]
                        >= x_start[i][dt] + x[i][overtime_dt],
                        name=f"consecutive{i}_{j}_o{o}"
                    )
                    # Constraint >> set overtime hours
                    solver.Add(
                        1 + x_ot[i][overtime_dt]
                        >= x_start[i][dt] + x[i][overtime_dt],
                        name=f"ot{i}_{j}_o{o}"
                    )
                    # Constraint >> set an additional rest hour if OT is used
                    if len(additional_rest_dts) >= (o + 1):
                        solver.Add(
                            1 - x_ot[i][overtime_dt]
                            >= x_start[i][additional_rest_dts[o]],
                            name=f"rest{i}_{j}_o{o}"
                        )

                # Constraint >> A staff member can only work 1 shift per business day
                other_starts = self.get_subset_dts(
                    min_dt=bus_day,
                    max_dt=bus_eod
                )
                solver.Add(
                    sum(x_start[i][o_start]
                        for o_start in other_starts) <= MAX_SHIFTS_PER_DAY,
                    name=f"max_per_day{i}_{j}"
                )

                # Constraint >> link x with x_day (per day)
                if bus_day != last_seen_date and len(self.demand_df['bus_day'].unique()) > MAX_DAYS_PER_WEEK:
                    day_dts = self.get_subset_dts(
                        min_dt=bus_day,
                        max_dt=bus_eod
                    )
                    solver.Add(
                        sum(x[i][d_dt] for d_dt in day_dts) <= len(
                            day_dts) * x_day[i][bus_day],
                        name=f"day_link{i}_{j}"
                    )
                    last_seen_date = bus_day

                # last staff
                if i == (self.M - 1):
                    # Constraint >>: to check demand coverage DC
                    # satisfies: At any given hour, there must be at least 2 staff members
                    # working a shift at the branch
                    solver.Add(
                        sum(x[s][dt] for s in range(self.M)) +
                        y1[dt] + y2[dt] >= self.demand_dict[dt],
                        name=f"dc{j}"
                    )

            # Constraint >>: Each staff member must have exactly 1 day-off per week
            for w in self.demand_df['week'].unique().tolist():
                week_days = self.demand_df.loc[self.demand_df['week'] == w]['bus_day'].unique(
                )
                if len(week_days) > MAX_DAYS_PER_WEEK:
                    solver.Add(
                        sum(x_day[i][pd.to_datetime(w_d)]
                            for w_d in week_days) <= MAX_DAYS_PER_WEEK,
                        name=f"max_per_week{i}_{w}"
                    )

    def solve(
            self, solver, x_start, x, x_ot, timeout
    ) -> Dict:
        '''
        Solve the problem and returns solution
        Outputs final metrics:
        the values of the two objective metrics, WDC and WOR,
        that the optimized shifts achieve.
        In addition, the total labor cost of the optimized schedule.
        The cost is the pay per staff including overtime.

        Weekly Demand Coverage (WDC) (Maximize):
        this is the average demand coverage per hour across all operation hours of the week.
        This is equal to
        WDC = average(DC for hour h for all hours across all weekly operation hours)

        Weekly Overtime Rate (WOR) (Minimize):
        the ratio between total overtime hours and the total scheduled hours for all staff members.
        This is equal to
        WOR = sum(OH for all staff across the week) / sum(SH for all staff across the week)
        '''

        # write problem out for debugging
        if DEBUG:
            with open(os.path.join("output", "model.lp"), "w") as f:
                f.write(solver.ExportModelAsLpFormat(obfuscated=False))
            solver.EnableOutput()

        start_timer = time.perf_counter()
        solver.set_time_limit(timeout)
        solver.SetNumThreads(8)

        # note: this is being ignored for some reason
        solver.RELATIVE_MIP_GAP = RELATIVE_MIP_GAP

        status = solver.Solve()
        print('Solve time:',
              round(time.perf_counter() - start_timer, 2))

        # --
        # Check the result
        columns = ['staff_id', 'start_date_time', 'end_date_time']
        rows = []
        demand_coverage = defaultdict(float)
        total_cost = 0

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):

            print("status",
                  "optimal" if status == pywraplp.Solver.OPTIMAL else "feasible")

            for i in range(self.M):
                wage = self.staff_df.iloc[i]['hourly_wage']
                ot_wage = self.staff_df.iloc[i]['overtime_hourly_wage']

                for dt in self.demand_dict:

                    total_cost += max(wage * x[i][dt].solution_value(),
                                      ot_wage * x_ot[i][dt].solution_value())

                    # start of a shift
                    if x_start[i][dt].solution_value():
                        shift_dts = self.get_subset_dts(
                            min_dt=dt,
                            max_dt=dt +
                            pd.Timedelta(hours=MAX_SHIFT_HOURS - 1),
                            max_length=MAX_SHIFT_HOURS
                        )
                        end_dt = max([_dt for _dt in shift_dts if x[i][_dt].solution_value() == 1]) \
                            + pd.Timedelta(hours=1)
                        rows.append(
                            {
                                'staff_id': str(self.staff_df.iloc[i]['staff_id']),
                                'start_date_time': str(dt),
                                'end_date_time': str(end_dt)
                            }
                        )

                    demand_coverage[dt] += x[i][dt].solution_value() / self.demand_dict[dt] \
                        if self.demand_dict[dt] else 0

        else:
            print('The problem does not have an optimal solution.')

        # write csv
        os.system("mkdir -p output")
        csv_file = os.path.join("output", "shift.csv")
        pd.DataFrame(rows, columns=columns).to_csv(csv_file)

        total_sh = sum(x[i][dt].solution_value()
                       for i in range(self.M) for dt in self.demand_dict)
        metrics = {
            'csv_file': csv_file,
            'WDC': round(sum(demand_coverage.values()) / len(demand_coverage), 4) if demand_coverage else 0,
            'WOR': round(sum(x_ot[i][dt].solution_value() for i in range(self.M) for dt in self.demand_dict)
                         / total_sh, 4) if total_sh else 0
            if demand_coverage else 0,
            'total_cost': round(float(total_cost), 2),
            'solver_status': "optimal" if status == pywraplp.Solver.OPTIMAL else "feasible",
            'shifts': rows
        }

        # write metrics as json
        json_file = os.path.join("output", "metrics.json")
        with open(json_file, "w") as f:
            json.dump(metrics, f, indent=4)

        return metrics

    def get_subset_dts(
            self, min_dt, max_dt,
            max_length=None
    ) -> List:
        '''
        Utility function to subset date-times based on the min/max datetime
        '''
        subset_dts = [
            _dt for _dt in self.demand_dict if min_dt <= _dt <= max_dt]

        # check length of subset
        if max_length:
            assert len(subset_dts) <= max_length
        return subset_dts


if __name__ == '__main__':

    # In the future, argparse can be used to pass the data in from the command line
    demand_file = os.path.join("data", "demand.csv")
    staff_file = os.path.join("data", "staff.csv")

    if not os.path.isfile(demand_file) or not os.path.isfile(staff_file):
        raise ValueError("Missing input csvs!")

    model = Model(demand_df=pd.read_csv(demand_file),
                  staff_df=pd.read_csv(staff_file))
    metrics = model.schedule_shifts()

    print(metrics)
