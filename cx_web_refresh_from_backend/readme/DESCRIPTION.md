# Refresh UI views from backend

This is a **technical module** that allows triggering a **UI reload** from the backend.
It enables triggering the reload action for selected users and record IDs.

---

## 🔧 Helper Function: `reload_views`

A special helper function `reload_views` is added to the `res.users` model.

### **Arguments**

| Argument | Type | Description |
|-----------|------|-------------|
| **model** | `Char` | Model name, e.g. `'res.partner'` |
| **view_types** | `List of Char` *(optional)* | View types to reload, e.g. `["form", "kanban"]`. Leave blank to reload all views. |
| **rec_ids** | `List of Integer` *(optional)* | The view will be reloaded only if a record with an ID from this list is present in the view. |

---

## ⚠️ Important Notes

Use this function **wisely**.

When reloading **form views**, be aware that if a user is currently editing a record,
**their unsaved updates may be lost** when the form reloads from the server (no confirmation
dialog is shown).
