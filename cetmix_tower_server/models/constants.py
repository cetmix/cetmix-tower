# ***
# This file is used to define commonly used constants
# ***

# Returned when trying to execute another instance of a command on the same server
# and this command doesn't allow parallel run
ANOTHER_COMMAND_RUNNING = -5

# Returned when no runner is found for command action
NO_COMMAND_RUNNER_FOUND = -6

# Returned when trying to execute another instance of a flightplan on the same server
# and this flightplan doesn't allow parallel run
ANOTHER_PLAN_RUNNING = -7

# Returned when a plan tries to parse a command log record which doesn't have
# a valid plan reference in it
PLAN_NOT_ASSIGNED = -10

# Returned when a plan tries to parse a command log record which doesn't have
# a valid plan line reference in it
PLAN_LINE_NOT_ASSIGNED = -11

# Returned when trying to star plan without lines
PLAN_IS_EMPTY = -1

# Returned when the file could not be created on the server
FILE_CREATION_FAILED = -12
