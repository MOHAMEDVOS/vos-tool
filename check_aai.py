import assemblyai as aai
import inspect

print("AssemblyAI Version:", aai.__version__ if hasattr(aai, "__version__") else "Unknown")
print("Transcriber methods:")
for name, _ in inspect.getmembers(aai.Transcriber, predicate=inspect.isfunction):
    print(f" - {name}")

t = aai.Transcriber()
print("\nInstance methods:")
for name in dir(t):
    if not name.startswith("_"):
        print(f" - {name}")
