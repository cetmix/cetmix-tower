Go to **Cetmix Tower > Settings > General Settings > Cetmix Tower > GitHub**.

**Root** can see that section. When it is missing, open **Settings > Users & Companies > Users** and set the user's Cetmix Tower access to **Root**.

Set **GitHub API Secret** and save.

On the repository, set **Secret** when that repository has its own token. Leave **Secret** empty to use the globally configured GitHub API Secret.

Be careful about the scope of the token. Any token that can read the repository is enough.

**Use another token for one Jet**

Head suggestions on a Jet first use the value of the secret that belongs to that Jet. **Manager** and **Root** can see the **Secrets** tab.

1. Go to **Cetmix Tower > Jets > Jets**. Open the Jet.
2. On **Secrets**, click **Add a line**.
3. In **Key**, select the secret used for the GitHub API.
4. In **Secret Value**, type the token for this Jet.
5. Click **Save**.

On a Git project, the Jet's token is used only when the project is linked to one Jet.
