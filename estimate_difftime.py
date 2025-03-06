from scipy.spatial.distance import cosine
import time
import random

def generate_random_vector(dimensions):
    """Generate a vector of specified dimensions with pseudo random values."""
    return [random.uniform(-1.0, 1.0) for _ in range(dimensions)]


dimensions=512
batch_count=1
i=1

sum_time = 0.0

while i <= batch_count:
    vector1 = generate_random_vector(dimensions)
    vector2 = generate_random_vector(dimensions)


    #print(f"Vector 1 ({dimensions} Dimensions): {vector1}")
    print(f"Vector 2 ({dimensions} Dimensions): {vector2}")

    start_time = time.time()
    distance = cosine(vector1, vector2)
    end_time = time.time()

    sum_time += (end_time - start_time)
    i+=1

print(f"Processed cosine_diffs for {batch_count} vector pairs.")
print("Time taken:", sum_time, "seconds")

average_time = sum_time / batch_count
print(f"Average time per pair: {average_time} seconds ")

# reid's results on 9/23/2024
# calculating the average time to calculate cosine diff between vector pairs
# average time over 1,000,000 iterations
# 256 dimensions - 0.000015 seconds per pair
# 512 dimensions - 0.000028 seconds per pair <-- i'm going to use this 
# 1536 dimensions (max for openai text-embedding-3-small) - 0.000070 seconds per pair 
