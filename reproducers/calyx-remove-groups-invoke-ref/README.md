# Calyx `remove-groups` Invoke/Reference Reproducer

This is a memory-free reduction of the `--calyx-remove-groups` assertion. It
uses `calyx.invoke` with a referenced register cell, showing that the crash is
caused by invoke/reference handling and not by memories specifically.

Current observed failure:

```text
Assertion `BaseT::wrapped() != End && "Cannot dereference end iterator!"' failed.
```
