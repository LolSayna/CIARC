import sys
import math
from loguru import logger

import shared.constants as con
from melvonaut.settings import settings
from shared.models import Event

import matplotlib.pyplot as plt
import matplotlib.patches as patches

##### LOGGING #####
logger.remove()
logger.add(
    sink=sys.stderr, level=settings.FILE_LOGGING_LEVEL, backtrace=True, diagnose=True
)


class ping:
    def __init__(self, x: int, y: int, d: float, mind: int, maxd: int):
        self.x = x
        self.y = y
        self.d = d
        self.mind = mind
        self.maxd = maxd

    def __str__(self) -> str:
        return f"Ping: x={self.x}, y={self.y}, d={self.d}, mind={self.mind}, maxd={self.maxd}"


# [CONSTANTS]
scaling_factor = 1
# ( 20400, 1400)

x_0 = 0

y_0 = 0
x_max = int(con.WORLD_X / scaling_factor)
y_max = int(con.WORLD_Y / scaling_factor)
max_offset = 325

path: str = con.CONSOLE_FROM_MELVONAUT_PATH + "Events.csv"
id = 125
identifyer: str = f"GALILEO_MSG_EB,ID_{id},DISTANCE_"

events = Event.load_events_from_csv(path=path)

# [DATA] x, y, distance
# data = [(4097, 7652, 2041), (5758, 8357, 688), (6220, 8553, 1075), (7245, 8989, 1669)]
data = [
    (19972.3165561, 113.5243816, 1454.48),
    (20486.232864, 331.337984, 930.35),
    (20998.9861724, 548.6578144, 787.93),
    (21510.18207954, 766.74099024, 1093.99),
    (18882.99334624, 2295.73420544, 1947.67),
    (19394.53293776, 2512.96329856, 1450.01),
    (19908.73421827, 2730.89789112, 1442.63),
    (20421.30728271, 2948.14119576, 1828.68),
    (20926.46189231, 3163.05597336, 1651.83),
]
# data = [(1000, 1000, 100)]

# [PREPROCESSING]
processed = []
print(f"World is ({x_0},{y_0}) to ({x_max},{y_max}).")
# for d in data:
#     s = ping(
#         x=int(d[0] / scaling_factor),
#         y=int(d[1] / scaling_factor),
#         d=d[2] / scaling_factor,
#         mind=int((d[2] - max_offset) / scaling_factor),
#         maxd=int((d[2] + max_offset) / scaling_factor),
#     )
#     processed.append(s)
#     print(f"Added: {s}")


def f(d: float) -> float:
    res = 225 + ((0.4 * (d + 1)) / 4)
    return float(res)


for event in events:
    if identifyer in event.event:
        (d, x, y) = event.easy_parse()
        s = ping(
            x=int(x / scaling_factor),
            y=int(y / scaling_factor),
            d=d / scaling_factor,
            mind=int((d - f(d)) / scaling_factor),
            maxd=int((d + f(d)) / scaling_factor),
        )
        processed.append(s)


print("Done parsing")


def distance(x1: int, x2: int, y1: int, y2: int) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


# [CALC]
# midpoint circle algorithm? -> not used for now

# Procssed first point
res = []
p1 = min(processed, key=lambda p: p.maxd)
for x in range(p1.x - p1.maxd, p1.x + p1.maxd):
    for y in range(p1.y - p1.maxd, p1.y + p1.maxd):
        if x > x_0 and x < x_max and y > y_0 and y < y_max:
            dist = distance(p1.x, x, p1.y, y)
            if dist > p1.mind and dist < p1.maxd:
                # print(f"Found: {dist} for ({x},{y}) with possible p1: ({p1.mind},{p1.maxd}")
                res.append((x, y))

print(f"Found {len(res)} possible points on first circle")

# Only keep the ones that are in all circles
filtered_res = []
for x, y in res:
    # print(f"x: {x}, y: {y}")
    is_valid = True
    for p2 in processed:
        dist = distance(p2.x, x, p2.y, y)
        if dist < p2.mind or dist > p2.maxd:
            # print(f"Found: {dist} for ({x},{y}) with possible d: ({p2.mind},{p2.maxd})")
            is_valid = False
            break

    if is_valid:
        filtered_res.append((x, y))

# print(filtered_res)
print(f"{len(filtered_res)} many matched over all points")

x_list, y_list = [], []
for x, y in filtered_res:
    x_list.append(x)
    y_list.append(y)


def find_centroid(points: list[tuple[int, int]]) -> tuple[float, float]:
    # Unpack the list of points into two lists: xs and ys
    xs, ys = zip(*points)

    # Calculate the centroid coordinates
    centroid_x = sum(xs) / len(xs)
    centroid_y = sum(ys) / len(ys)

    return (centroid_x, centroid_y)


# Example usage:
centroid = find_centroid(filtered_res)
print("The centroid of the points is:", int(centroid[0]), int(centroid[1]))


fig = plt.figure()
plt.xlabel("Width")
plt.ylabel("Height")
ax = fig.gca()
for p in processed:
    circle_inner = patches.Circle(
        (p.x, p.y), p.mind, edgecolor="green", facecolor="none", linewidth=0.1
    )
    circle_outer = patches.Circle(
        (p.x, p.y), p.maxd, edgecolor="blue", facecolor="none", linewidth=0.1
    )
    ax.add_patch(circle_inner)
    ax.add_patch(circle_outer)
circle_guess = patches.Circle(
    (centroid[0], centroid[1]), 75, edgecolor="yellow", linewidth=1
)
ax.add_patch(circle_guess)
ax.plot(x_list, y_list, "ro")
# ax.plot(centroid[0], centroid[1], color='yellow', marker='o')
# ax.set_xlim(0,x_max)
# ax.set_ylim(0, y_max)
plt.show()
