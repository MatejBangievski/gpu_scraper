import Sites

for name in dir(Sites):
    if name.startswith("__"):
        continue
    module = getattr(Sites, name)
    if hasattr(module, 'run') and callable(module.run):
        print(f"Scraping {name}.")
        module.run()
        print(f"Finished {name}.")
