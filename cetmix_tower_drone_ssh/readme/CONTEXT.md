An SSH command run by Cetmix Tower holds an Odoo worker until the remote command ends. Long commands therefore run against the time limits of that worker, and they are also ended by the zombie command cron once they run longer than the "Command Timeout" setting. The two limits are independent of each other.

This module moves SSH commands out of Odoo to external drones. SSH is the first skill built on the "Cetmix Tower Drone" job layer. It uses the command deferral hooks of "Cetmix Tower Server" and does not change how commands are rendered, logged or chained in flight plans.
