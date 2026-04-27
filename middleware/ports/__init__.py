"""middleware/ports/ — vendor-neutral Protocol contracts.

Each port file declares exactly one ``Protocol`` consumed by the
composition root. Adapters under ``middleware/adapters/<family>/``
implement these ports without leaking SDK types past the boundary
(rule **F-R8** / **A4**).
"""
