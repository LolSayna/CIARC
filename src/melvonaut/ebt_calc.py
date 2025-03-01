import sys
import math
from loguru import logger

import shared.constants as con

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level=con.RIFT_LOG_LEVEL, backtrace=True, diagnose=True)


class ping:
    def __init__(self, x, y, d, mind, maxd):
        self.x = x
        self.y = y
        self.d = d
        self.mind = mind
        self.maxd = maxd

    def __str__(self):
        return f"Ping: x={self.x}, y={self.y}, d={self.d}, mind={self.mind}, maxd={self.maxd}"


# [CONSTANTS]
scaling_factor = 10
x_0 = 0
y_0 = 0
x_max = int(con.WORLD_X / scaling_factor)
y_max = int(con.WORLD_Y / scaling_factor)
max_offset = 325

# [DATA] x, y, distance
data = [(4097, 7652, 2041), (5758, 8357, 688), (6220, 8553, 1075), (7245, 8989, 1669)]
# data = [(1000, 1000, 100)]

# [PREPROCESSING]
processed = []
print(f"World is ({x_0},{y_0}) to ({x_max},{y_max}).")
for d in data:
    s = ping(
        x=int(d[0] / scaling_factor),
        y=int(d[1] / scaling_factor),
        d=d[2] / scaling_factor,
        mind=int((d[2] - max_offset) / scaling_factor),
        maxd=int((d[2] + max_offset) / scaling_factor),
    )
    processed.append(s)
    print(f"Added: {s}")

print("Done parsing")


def distance(x1, x2, y1, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


# [CALC]
# midpoint circle algorithm? -> not used for now

# Procssed first point
res = []
d = min(processed, key=lambda p: p.maxd)
for x in range(d.x - d.maxd, d.x + d.maxd):
    for y in range(d.y - d.maxd, d.y + d.maxd):
        if x > x_0 and x < x_max and y > y_0 and y < y_max:
            dist = distance(d.x, x, d.y, y)
            if dist > d.mind and dist < d.maxd:
                # print(f"Found: {dist} for ({x},{y}) with possible d: ({d.mind},{d.maxd}")
                res.append((x, y))

print(f"Found {len(res)} possible points on first circle")

# Only keep the ones that are in all circles
filtered_res = []
for x, y in res:
    # print(f"x: {x}, y: {y}")
    is_valid = True
    for d in processed:
        dist = distance(d.x, x, d.y, y)
        if dist < d.mind or dist > d.maxd:
            # print(f"Found: {dist} for ({x},{y}) with possible d: ({d.mind},{d.maxd})")
            is_valid = False
            break

    if is_valid:
        filtered_res.append((x, y))

print(filtered_res)
print(f"{len(filtered_res)} many matched over all points")
