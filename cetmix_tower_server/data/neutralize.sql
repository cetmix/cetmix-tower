-- deactivate scheduled tasks
UPDATE cx_tower_scheduled_task
   SET active = false;
