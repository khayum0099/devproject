import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{func.__name__}() took {elapsed:.2f} ms")
        return result
    return wrapper

# Usage
@timer
def sum_squares(n):
    return sum(i * i for i in range(n))

print(sum_squares(1_000_000))

