**Create a Backup Template**

1. Sign in as a Tower **Root** user.
2. Open **Cetmix Tower**.
3. Click **Commands**.
4. Click **Flight Plans**.
5. Create a Backup flight plan that writes backup data to your chosen destination.
6. Set its **Access Level** to **Root**.
7. Set every command and every Plan-action sub-plan it uses to **Root** too.
8. Create a Root Restore plan that reads the stored data into a new Jet.
9. Optionally create a Root Delete plan that removes the stored data.
10. Click **Jets**.
11. Click **Templates**.
12. Open the source Jet Template.
13. Open **Backups**.
14. Add a Backup Template.
15. Enter **Name**.
16. Select **Backup Flight Plan**.
17. Select **Restore Flight Plan**.
18. Select **Delete Flight Plan** when stored data needs explicit removal.
19. Enter **Keep Last**: `0` keeps all successful backups; a positive number limits them per source Jet.
20. Save the Backup Template.
21. Save the Jet Template.

**Configure a scheduled trigger**

1. Open **Cetmix Tower**.
2. Click **Automation**.
3. Click **Scheduled Tasks**.
4. Create a task.
5. Set **Action** to **Backup**.
6. Select **Backup Template**.
7. Select target **Jets** from its Jet Template; leave **Servers** empty.
8. Set the interval.
9. Optionally add custom variable values.
10. Save.

**Configure a command trigger**

1. Open **Cetmix Tower**.
2. Click **Commands**.
3. Click **Commands** in that menu.
4. Create a command.
5. Set **Action** to **Create Backup**.
6. Select **Backup Template**.
7. Save.
8. Add the command to a flight plan running on a Jet, or select it in a scheduled **Command** task targeting a Jet.

**Configure a waypoint trigger**

1. Open the source Jet Template.
2. Open **Waypoints**.
3. Open a waypoint template.
4. Select **Backup Template** from the same Jet Template.
5. Leave **Create Flight Plan** empty.
6. Leave **Delete Flight Plan** empty.
7. Optionally select a Root **Arrive Flight Plan**.
8. Optionally select a Root **Leave Flight Plan**.
9. Set every command and Plan-action sub-plan in those plans to **Root**.
10. Save.

**Author the plans**

1. Store object names, paths and recovery metadata with `backup.update_metadata({...})` in a Python command.
2. Pass non-secret destination parameters as trigger custom values.
3. Keep credentials in Tower keys, not custom values or metadata.
4. Keep the plans and commands at Root level; protected logs block lowering their access level, even after a plan leaves its Backup Template.
5. Use in-process Python `restore(..., variable_values=...)` when Restore needs custom-value overrides; pass Odoo server, state and environment records rather than integer IDs. RPC calls to `restore()` are rejected.

| Plan value or object | Contract |
| --- | --- |
| Trigger custom values | Stored and replayed to Backup, Restore and Delete |
| Restore `variable_values` | Override the stored custom values |
| `__backup_<key>` | Metadata value; overrides a custom value with the same name |
| `__backup` | Backup reference, applied after metadata |
| `__backup_template` | Backup Template reference, applied after metadata |
| `__requested_jet_state__` | Requested Jet state during Restore; the Restore plan handles the transition |
| Python `backup` | Current backup on operation lines; empty outside a backup run |
| Python `tower_backups` | Backup model shortcut |
| Sub-plans | Receive custom values; do not automatically receive the `backup` object |
| Waypoint Arrive/Leave | Receive backup values while the waypoint template retains its Backup Template; waypoint values win on collisions |

**Access boundary**

| Actor | Access |
| --- | --- |
| Root | Can read and configure backups and templates, and use the backup dialogs |
| Manager | Can trigger configured backups through waypoints, plans and schedules without seeing backup fields |
| User able to execute Tower Python | Can call `sudo()`; Root-only ACLs, field groups and UI do not isolate backups from that code |
