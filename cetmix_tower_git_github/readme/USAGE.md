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

## Read from GitHub

Go to **Cetmix Tower > Settings > Git Projects > Repositories**. Open a github.com repository.

**Read from GitHub** is on the form. The same action is on the repository list. Both are limited to managers.

Saving a github.com repository reads GitHub as well. When that read fails, the repository is still saved.

When the stored GitHub owner id differs from GitHub, choose **Overwrite** to replace it or **Cancel** to keep it. The repository id and the private flag are already updated either way.
