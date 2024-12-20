import unittest

import pandas as pd
from config import MIN_SHIFT_HOURS, MAX_SHIFT_HOURS, MAX_DAYS_PER_WEEK
from shifts_scheduling import Model


class TestSolution(unittest.TestCase):

    def setUp(self) -> None:

        self.wage = 9.63
        self.ot_wage = 14.44
        self.staff_df = pd.DataFrame(
            [
                {
                    'staff_id': 101, 'role': 'Manager',
                    'hourly_wage': self.wage, 'overtime_hourly_wage': self.ot_wage
                }
            ]
        )

    def test_simple(self):
        '''
	    one day, one staff, no OT
        '''

        staff_df = self.staff_df

        # change role, to prevent OT
        staff_df['role'] = 'Branch Manager'

        demand_df = pd.DataFrame(
            [
                {
                    'date_time': pd.to_datetime('2025-01-01') + pd.Timedelta(hours=h),
                    'demand': 3 if h < 10 else 2  # check hours with higher DC ratio are selected
                }
                for h in range(24)
            ]
        )

        model = Model(demand_df, staff_df)
        results = model.schedule_shifts()
        self.assertEqual(results['WDC'], 0.1875)
        self.assertEqual(results['WOR'], 0)
        self.assertEqual(results['total_cost'], MIN_SHIFT_HOURS * self.wage)

        shifts_df = pd.DataFrame(results['shifts'])

        self.assertEqual(len(shifts_df), 1)
        start_dt = pd.to_datetime(shifts_df['start_date_time'].min())
        end_dt = pd.to_datetime(shifts_df['end_date_time'].max())
        self.assertGreaterEqual(start_dt, pd.to_datetime('2025-01-01 10:00:00'))

        self.assertEqual((end_dt - start_dt).total_seconds() / 3600,
                         MIN_SHIFT_HOURS)

    def test_simple_with_ot(self):
        '''
	    one day, one staff, with OT
        '''

        staff_df = self.staff_df
        demand_df = pd.DataFrame(
            [
                {
                    'date_time': pd.to_datetime('2025-01-01') + pd.Timedelta(hours=h),
                    'demand': 3
                }
                for h in range(24)
            ]
        )

        model = Model(demand_df, staff_df)
        results = model.schedule_shifts()
        self.assertEqual(results['WDC'], 0.1667)
        self.assertEqual(results['WOR'], (MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) / MAX_SHIFT_HOURS)
        self.assertEqual(results['total_cost'],
                         MIN_SHIFT_HOURS * self.wage + (MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) * self.ot_wage)

        shifts_df = pd.DataFrame(results['shifts'])

        self.assertEqual(len(shifts_df), 1)
        start_dt = pd.to_datetime(shifts_df['start_date_time'].min())
        end_dt = pd.to_datetime(shifts_df['end_date_time'].max())

        self.assertEqual((end_dt - start_dt).total_seconds() / 3600,
                         MAX_SHIFT_HOURS)

    def test_simple_with_multi_days(self):
        '''
	    2 days, one staff, with OT
        '''

        staff_df = self.staff_df
        demand_df = pd.DataFrame(
            [
                {
                    'date_time': pd.to_datetime('2025-01-01') + pd.Timedelta(hours=h),
                    'demand': 3
                }
                for h in range(48)
            ]
        )

        model = Model(demand_df, staff_df)
        results = model.schedule_shifts()

        num_days = 2
        self.assertEqual(results['WDC'], 0.1667)
        self.assertEqual(results['WOR'], (MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) / MAX_SHIFT_HOURS)
        self.assertEqual(results['total_cost'],
                         num_days * (MIN_SHIFT_HOURS * self.wage
                                     + (MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) * self.ot_wage))

        shifts_df = pd.DataFrame(results['shifts'])

        self.assertEqual(len(shifts_df), num_days)
        for idx, row in shifts_df.iterrows():
            start_dt = pd.to_datetime(row['start_date_time'])
            end_dt = pd.to_datetime(row['end_date_time'])

            self.assertEqual((end_dt - start_dt).total_seconds() / 3600,
                             MAX_SHIFT_HOURS)

    def test_simple_week(self):
        '''
	    1 week, one staff, with OT
        '''
        staff_df = self.staff_df
        demand_df = pd.DataFrame(
            [
                {
                    'date_time': pd.to_datetime('2025-01-01') + pd.Timedelta(hours=h),
                    'demand': 3
                }
                for h in range(168)
            ]
        )
        model = Model(demand_df, staff_df)
        results = model.schedule_shifts(timeout=10_000)

        # allocates 1/3 of the demand for half of the hours each day
        # for 6/7 days of week
        self.assertEqual(results['WDC'],
                         round((1 / 3) * (MAX_SHIFT_HOURS / 24) * MAX_DAYS_PER_WEEK / 7, 4))
        self.assertEqual(results['WOR'],
                         round((MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) / MAX_SHIFT_HOURS, 4))
        self.assertEqual(
            results['total_cost'],
            MAX_DAYS_PER_WEEK * (
                    MIN_SHIFT_HOURS * self.wage
                    + (MAX_SHIFT_HOURS - MIN_SHIFT_HOURS) * self.ot_wage)
        )

        shifts_df = pd.DataFrame(results['shifts'])

        self.assertEqual(len(shifts_df), MAX_DAYS_PER_WEEK)
        for idx, row in shifts_df.iterrows():
            start_dt = pd.to_datetime(row['start_date_time'])
            end_dt = pd.to_datetime(row['end_date_time'])

            self.assertEqual((end_dt - start_dt).total_seconds() / 3600,
                             MAX_SHIFT_HOURS)
