
from ._parser import load, loads, Struct

import importlib.resources
import os

def open_example_file():
	"""
	Open the bundled example.tyco file and print its physical path.
	Usage:
		with tyco.open_example_file() as f:
			context = tyco.load(f)
	"""
	# importlib.resources.files is available in Python 3.9+
	try:
		resource = importlib.resources.files(__package__).joinpath("example.tyco")
		path = str(resource)
		print(f"[tyco] Loading example.tyco from: {path}")
		return resource.open("r")
	except AttributeError:
		# Fallback for Python <3.9
		with importlib.resources.path(__package__, "example.tyco") as p:
			print(f"[tyco] Loading example.tyco from: {p}")
			return open(p, "r")
