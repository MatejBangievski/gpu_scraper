import os
import importlib

package_dir = os.path.dirname(__file__) # Current Dir

for filename in os.listdir(package_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = filename[:-3]
        module = importlib.import_module(f".{module_name}", package=__name__) # Ex: ".anhoch", package="Sites"
        globals()[module_name] = module