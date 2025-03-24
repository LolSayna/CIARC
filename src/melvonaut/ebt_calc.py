import os
import sys
import math
from loguru import logger

import shared.constants as con
from melvonaut.settings import settings
from shared.models import Event, Ping

import matplotlib.pyplot as plt
import matplotlib.patches as patches

##### LOGGING #####
logger.remove()
logger.add(
    sink=sys.stderr, level=settings.FILE_LOGGING_LEVEL, backtrace=True, diagnose=True
)

# [CONSTANTS]
scaling_factor = 1
x_0 = 0
y_0 = 0
x_max = int(con.WORLD_X / scaling_factor)
y_max = int(con.WORLD_Y / scaling_factor)
max_offset = 325


# [HELPER]
def f(d: float) -> float:
    res = 225 + ((0.4 * (d + 1)) / 4)
    return float(res)


def distance(x1: int, x2: int, y1: int, y2: int) -> float:
    if x1 > con.WORLD_X:
        x1 = x1 % con.WORLD_X
    while x1 < 0:
        x1 += con.WORLD_X
    if y1 > con.WORLD_Y:
        y1 = y1 % con.WORLD_Y
    while y1 < 0:
        y1 += con.WORLD_Y
    if x2 > con.WORLD_X:
        x2 = x2 % con.WORLD_X
    while x2 < 0:
        x2 += con.WORLD_X
    if y2 > con.WORLD_Y:
        y2 = y2 % con.WORLD_Y
    while y2 < 0:
        y2 += con.WORLD_Y
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def parse_pings(id: int, events: list[Event]) -> list[Ping]:
    processed = []
    for event in events:
        if f"GALILEO_MSG_EB,ID_{id},DISTANCE_" in event.event:
            (d, x, y) = event.easy_parse()
            s = Ping(
                x=int(x / scaling_factor),
                y=int(y / scaling_factor),
                d=d / scaling_factor,
                mind=int((d - f(d)) / scaling_factor),
                maxd=int((d + f(d)) / scaling_factor),
            )
            processed.append(s)
    return processed


def find_matches(pings: list[Ping]) -> list[tuple[int, int]]:
    # Procssed first point
    res = []
    p1 = min(pings, key=lambda p: p.maxd)
    for x in range(p1.x - p1.maxd, p1.x + p1.maxd):
        for y in range(p1.y - p1.maxd, p1.y + p1.maxd):
            if x > x_0 and x < x_max and y > y_0 and y < y_max:
                dist = distance(p1.x, x, p1.y, y)
                if dist > p1.mind and dist < p1.maxd:
                    res.append((x, y))
    logger.info(f"Found {len(res)} possible points on first circle.")

    # Only keep the ones that are in all circles
    filtered_res = []
    for x, y in res:
        is_valid = True
        for pn in pings:
            dist = distance(pn.x, x, pn.y, y)
            if dist < pn.mind or dist > pn.maxd:
                is_valid = False
                break
        if is_valid:
            filtered_res.append((x, y))

    logger.info(f"Found {len(filtered_res)} points that match all pings.")
    return filtered_res


def draw_res(
    id: int, res: list[tuple[int, int]], pings: list[Ping], show: bool = False
) -> tuple[int, int]:
    def find_centroid(points: list[tuple[int, int]]) -> tuple[float, float]:
        xs, ys = zip(*points)
        centroid_x = sum(xs) / len(xs)
        centroid_y = sum(ys) / len(ys)
        return (centroid_x, centroid_y)

    x_list, y_list = [], []
    for x, y in res:
        x_list.append(x)
        y_list.append(y)

    centroid = find_centroid(res)

    plt.style.use("bmh")
    _, ax = plt.subplots()
    plt.title(f"Emergency Beacon Tracker {id} - {len(pings)} pings")
    plt.xlabel("Width")
    plt.ylabel("Height")
    ax.set_xlim(0, x_max)
    ax.set_ylim(0, y_max)

    # plot matched area
    ax.plot(x_list, y_list, "ro", zorder=4)
    legend_area = patches.Patch(edgecolor="red", facecolor="red", linewidth=1, label='Matched area')

    # plot pings
    for p in pings:
        ax.plot(p.x, p.y, 'x', color='grey', markersize=5, zorder=3)
        circle_inner = patches.Circle(
            (p.x, p.y), p.mind, edgecolor="green", facecolor="none", linewidth=0.2, zorder=2
        )
        circle_outer = patches.Circle(
            (p.x, p.y), p.maxd, edgecolor="blue", facecolor="none", linewidth=0.2, zorder=2
        )
        ax.add_patch(circle_inner)
        ax.add_patch(circle_outer)
    legend_point = plt.Line2D([0], [0], linestyle='None', marker='x', markerfacecolor='grey', markeredgecolor='grey', markersize=6, label='Ping Location')
    legend_inner = patches.Patch(edgecolor="green", facecolor="none", linewidth=1, label='Minimum Distance')
    legend_outer = patches.Patch(edgecolor="blue", facecolor="none", linewidth=1, label='Maximum Distance')


    # plot centroid
    circle_guess = patches.Circle(
        (centroid[0], centroid[1]), 75, edgecolor="violet", facecolor="violet", linewidth=1, zorder=5
    )
    ax.add_patch(circle_guess)
    legend_guess = patches.Patch(edgecolor="violet", facecolor="violet", linewidth=1, label=f'Best guess\n({int(centroid[0])}, {int(centroid[1])})')

    ax.legend(handles=[legend_point, legend_inner, legend_outer, legend_guess, legend_area], loc='best')
    if show:
        logger.info(f"Centroid is: ({int(centroid[0])},{int(centroid[1])})")
        plt.show()
    else:
        space = ""
        count = 0
        path = (
            con.CONSOLE_EBT_PATH + f"EBT_{id}_{len(pings)}.png"
        )
        while os.path.isfile(path):
            count += 1
            space = "_" + str(count)
            path = con.CONSOLE_EBT_PATH + f"EBT_{id}_{len(pings)}{space}.png"
        plt.savefig(path, dpi=1000)

    return (int(centroid[0]), int(centroid[1]))


if __name__ == "__main__":
    # Open idea: use midpoint circle algorithm? -> not used for now
    logger.info("Running from cli.")

    id = 102
    path: str = con.CONSOLE_FROM_MELVONAUT_PATH + "MelvonautEvents.csv"
    events = Event.load_events_from_csv(path=path)

    # Example data
    """
    processed = []
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
    """

    processed = parse_pings(id=id, events=events)
    logger.info(f"Done parsing of {len(processed)} pings.")

    res = find_matches(pings=processed)

    if len(res) == 0:
        logger.error("No Matches Found!")
        exit()

    draw_res(id=id, res=res, pings=processed, show=True)
