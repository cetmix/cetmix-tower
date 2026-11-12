Go to **Cetmix Tower > Settings > General Settings > Cetmix Tower > GitHub**.

**Root** can see that section. When it is missing, open **Settings > Users & Companies > Users** and set the user's Cetmix Tower access to **Root**.

Set **GitHub API Secret** and save.

On the repository, set **Secret** when that repository has its own token. When **Secret** is empty, Tower uses the **Secret** on the repository owner. When both are empty, Tower uses **GitHub API Secret** from General Settings.

Tower resolves a secret in that order for Head autocomplete and for reading the GitHub repository id. Head autocomplete still uses server and partner values when they are known. Reading the GitHub id uses only a **global** value of the chosen secret; server-specific or partner-specific values are not used for that read.

Be careful about the scope of the token. Any token that can read the repository is enough.
