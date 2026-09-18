# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Drone skill code
SKILL_SSH = "ssh"

# Returned when no drone controller took the command
NO_DRONE_CONTROLLER = -209

# What to do when no drone controller can take an SSH command
NO_CONTROLLER_POLICY_PARAM = "cetmix_tower_drone_ssh.no_controller_policy"
NO_CONTROLLER_POLICY_FAIL = "fail"
NO_CONTROLLER_POLICY_FALLBACK = "fallback"
