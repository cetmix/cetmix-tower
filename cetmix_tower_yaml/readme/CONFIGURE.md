Please refer to the [official documentation](https://cetmix.com/tower) for detailed configuration instructions.

| Permission | Behavior |
| --- | --- |
| YAML Import: Allow | Imports respect the user’s field and record permissions. Root-only fields require Root membership, including when their supplied values are empty. |
| YAML Export: Allow | Ordinary record access still applies. Empty Root-only fields are omitted; populated fields require Root membership. |
