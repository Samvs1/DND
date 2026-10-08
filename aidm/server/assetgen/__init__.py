"""AI asset generator core (Addendum B): providers, price table, budget guard, priority, plan, run.

Lives in the top `server` layer because it does network I/O (OpenAI images) and reads the data
registries and the asset manifest. `scripts/gen_assets.py` is the command-line entry point.
"""
