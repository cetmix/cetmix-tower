Some work takes minutes or hours: long deployments, large transfers, builds. Running it inside Odoo holds an Odoo worker for the whole time and ties the work to the limits of that worker and of any cron that assumes the work happens inside Odoo.

This module moves such work out of Odoo. Odoo hands a payload to an external worker, keeps a job record, and is called back when the worker is done.

It is a generic job layer only and ships no skills of its own. Skills are whatever a controller reports. This module does not define them.

Drones are not Odoo records. Tower only talks to drone controllers, and each controller runs the work on its own drones.
