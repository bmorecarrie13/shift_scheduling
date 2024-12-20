'''
Configurations
'''

MIN_STAFF_PER_HOUR = 2

MIN_REST_HOURS = 4

MIN_SHIFT_HOURS = 9

MAX_SHIFT_HOURS = 12

ROLE_OT_PROHIBITED = ['Branch Manager']

MAX_DAYS_PER_WEEK = 6

MAX_SHIFTS_PER_DAY = 1

# in ms
SOLVE_TIME_LIMIT = 65_000

SOLVER = 'SCIP'

DEBUG = True

RELATIVE_MIP_GAP = 0.01

# obj function weight for WDC
W1 = 0.75