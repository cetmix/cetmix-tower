**Take a backup**

1. Open **Cetmix Tower**.
2. Click **Jets**.
3. Click **Jets** in that menu.
4. Open the source Jet.
5. Click **Back Up**.
6. Select **Backup Template**.
7. Optionally click **Add a line** under **Custom Values**.
8. Select **Variable** from the template's available variables.
9. Enter **Value**, or select **Option** for an option variable.
10. Click **Back Up** in the dialog.
11. Wait for **Running** to become **Done** or **Failed**.
12. Open **Metadata** to inspect the stored recovery details.
13. Open **Plan Logs** to inspect the plan result.

**Restore into a new Jet**

1. Open **Cetmix Tower**.
2. Click **Tools**.
3. Click **Backups**.
4. Open a **Done** backup.
5. Click **Restore**.
6. Select **Server**.
7. Optionally enter **Name**; leave it blank to generate one.
8. Optionally select **State**.
9. Select **Environment** if the destination template requires it.
10. Optionally click **Add a line** under **Custom Values**.
11. Select **Variable** from the template's available variables.
12. Enter **Value**, or select **Option** for an option variable.
13. Click **Restore**.
14. Inspect the new Jet's flight plan log. If Restore fails immediately, the dialog opens the failed log and keeps the new Jet.

| Recovery behavior | Result |
| --- | --- |
| Destination | A new Jet; the original Jet is not restored in place |
| Repeated restore | The backup remains Done and can be restored again |
| Variable values | Only the source Jet's own values were captured; template, server and global values and Jet secrets were not frozen |
| Default environment | Captured environment, then the Jet Template's default |
| Git bridge | Restores captured Git configuration into fresh records; source references and aggregator source directories can differ |

**Delete a backup**

1. Open **Cetmix Tower**.
2. Click **Tools**.
3. Click **Backups**.
4. Open the backup.
5. Click **Delete**.
6. Wait for the Delete plan to finish; success removes the record.
7. If **Deletion Failed** appears, inspect **Plan Logs**.
8. Resolve the reported cause.
9. Click **Delete** again to retry.
10. For a backup owned by a waypoint, delete the waypoint instead.

| Deletion condition | Result |
| --- | --- |
| Running backup, deletion or Restore | Deletion is blocked |
| Busy Jet or Delete plan | Delete shows an error and leaves the backup unchanged; retry later |
| Neither source Jet nor captured server remains | Form warns that only the record can be removed; stored data stays |
| No Delete plan | Record is removed immediately |
| Source Jet deleted | Completed backups survive; their waypoint links are removed |

**Check automatic clean-up**

1. Open **Cetmix Tower**.
2. Click **Tools**.
3. Click **Backups**.
4. Inspect the remaining records after the daily clean-up.

| Records | Daily clean-up behavior |
| --- | --- |
| Unlinked Failed backups | Removed regardless of Keep Last |
| Excess Done backups per Jet | Removed through the Delete plan when configured; otherwise only the record is removed and stored backup data remains |
| Backup being restored | Counts toward retention and stays until a later clean-up |
| Waypoint-linked backups | Kept for the waypoint's lifecycle |
| Deletion Failed backups | Kept for manual investigation and retry |
| Orphaned Done backups | Kept |
| Busy or locked Jet / Delete plan | Deferred until a later clean-up; other backups can still be processed |

**Inspect backup size**

1. Open **Cetmix Tower**.
2. Click **Tools**.
3. Click **Backups**.
4. Read **Backup Size (MB)** in the list.
5. Open a backup to read **Backup Size (MB)** on its form.

| Size value | Meaning |
| --- | --- |
| Backup Size (MB) | Stored Float supplied by a Tower command using 1 MB = 1,048,576 bytes; fractional values are retained and the value starts at 0 until supplied |

**Open the backup URL**

1. Open **Cetmix Tower**.
2. Click **Tools**.
3. Click **Backups**.
4. Open a backup.
5. Click **URL** when the backup command has supplied one.

| List state pill | Color |
| --- | --- |
| Done | Green |
| Running | Blue |
| Deleting | Orange |
| Failed or Deletion Failed | Red |

| Wizard custom values | Behavior |
| --- | --- |
| Corresponding Available Variables list empty | No custom values accepted in that dialog |
| Backup dialog values | Stored with the backup and replayed to its plans |
| Restore dialog values | Override matching stored custom values for that restore; leave the stored backup values unchanged |
| Invalid or repeated variable | Confirmation is refused; no operation is started |
