# PR requirements

## Commit message

### Title (subject line)

Short and descriptive. Please try to keep it under 50 characters
Written in the imperative mood (e.g., "Fix bug", "Add feature" **not** "Fixed" or "Added").

Use tags listen in the [Odoo Guidelines](https://www.odoo.com/documentation/16.0/contributing/development/git_guidelines.html#tag-and-module-name).

### ​Description (mandatory)

- Must be separated from the title with a blank line.
- Wrap at 72 characters per line for readability.
- Must explain **why** and **what** of the change (if not self-explanatory).
- Can mention **how** **only if necessary** for clarification.
- Must have a line with related task number. Eg "Task: 2302"

Commit message example

```txt
[ADD] cetmix_tower_server: Doge memes

Implement Doge memes in order to make the server more fun.

Add new models to allow more flexible meme configuration:

- Doge
- Meme
- DogeMeme

```

## PR description

Provide Odoo version number tag together with the primary tag. Example:

```txt
[18.0][ADD] cetmix_tower_server: Doge memes
```

PR description should contain context and description of the changes:

```txt
Implement Doge memes in order to make the server more fun.
Add new models to allow more flexible meme configuration:

- Doge
- Meme
- DogeMeme
```

NB: Please ensure that you have signed the CLA. There will be a message in the PR review if you have not.
