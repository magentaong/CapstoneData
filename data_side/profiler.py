import sys

from profiling.profiler import write_profile

if __name__ == "__main__":
    print(write_profile(sys.argv[1]) or "no profile built")