Cetmix Tower Base provides the shared core used by Cetmix Tower modules:
access groups, the Cetmix Tower menu, General Settings, tags, the secret
vault, and the mixins that other Tower modules inherit.

It is a dependency of `cetmix_tower_server` and of any future Tower module
that needs this core without installing Servers, Jets or Flight Plans.

Access groups
-------------

Users are assigned a Cetmix Tower access level (Settings → Users & Companies
→ Users):

- **User** — basic actions for selected servers.
- **Manager** — create and modify selected servers.
- **Root** — full control over all servers.

Manager includes User. Root includes Manager.

Menus
-----

The **Cetmix Tower** root menu is visible to User (and above). Under
**Settings** (Manager and above):

- **General Settings** — opens the Cetmix Tower settings page. Other Tower
  modules add their options there.
- **Tags** — list of tags.

Tags
----

Tags group Tower records. The form and list show:

- **Name**
- **Color** — for better visualization in views
- **Reference** — can contain English letters, digits and `_`. Leave blank
  to autogenerate.

A manager can delete a tag they created only when it is not used on related
records. Root can delete a tag even when it is in use.
