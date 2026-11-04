## From a Git project

Go to **Cetmix Tower > Tools > Git Projects**. Open a project.

On **Sources**, click **Add a line** and open the source.

On **Remotes**, click **Add a line**.

Set **Head Type** to Branch, Pull/Merge Request, or Commit. Click **Head** and choose a row.

## From a Jet

Go to **Cetmix Tower > Jets > Jets**. Open a Jet.

On **Git Project**, click **Add a line**. Set **Head Type**, then click **Head** and choose a row.

## What is stored

A branch name that contains `/`, such as `feat/2233`, is stored whole. A pasted `https://` link keeps its last path segment.

A pull request row shows the number and the title, such as `510 [18.0][ADD] cetmix_tower_git_github: add module`. **Head** stores `510`.

A commit row in the list shows the first 7 characters of the SHA and the subject, such as `6e427eb [IMP] cetmix_tower_git: autocomplete git heads`. **Head** stores the full SHA.

When no secret resolves, an error is shown and the list is empty. A typed value can still be saved.
