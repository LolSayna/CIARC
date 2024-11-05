import tkinter as tk
import tkinter.ttk as ttk
from console import create_console
from ciarc import Sat

# main window
window = tk.Tk()
window.title("ESA Ciarc dashboard")
# window.geometry("500x300")

# MAP
map_frame = tk.Frame(master=window)
map_label = tk.Label(master=map_frame, text="POSITION")
map_canvas = tk.Canvas(master=map_frame, width=200, height=100, bg="red")
sat = map_canvas.create_rectangle(20,20,40,40, fill="green")
map_label.pack(side="top")
map_canvas.pack(side="bottom")

# Control
control_frame = tk.Frame(relief=tk.RAISED, borderwidth=5)
## State
state_frame = tk.Frame(master=control_frame)
state_label = tk.Label(master=state_frame, text="State", fg="black", bg="white")
state_bar_label = tk.Label(master=state_frame, text="Deploying")
state_label.pack(side="top")
state_bar_label.pack(side="top")
state_frame.pack(side="top")

## FUEL
fuel_frame = tk.Frame(master=control_frame)
fuel_label = tk.Label(master=fuel_frame, text="Fuel", fg="black", bg="violet")
progressbar = ttk.Progressbar(master=fuel_frame)
progressbar.step(95)
fuel_bar_label = tk.Label(master=fuel_frame, text="95%")
fuel_label.pack(side="top")
progressbar.pack(side="top")
fuel_bar_label.pack(side="top")
fuel_frame.pack(side="top")

## Power
power_frame = tk.Frame(master=control_frame)
power_label = tk.Label(master=power_frame, text="Power", fg="black", bg="yellow")
progressbar = ttk.Progressbar(master=power_frame)
progressbar.step(80)
power_bar_label = tk.Label(master=power_frame, text="80%")
power_label.pack(side="top")
progressbar.pack(side="top")
power_bar_label.pack(side="top")
power_frame.pack(side="top")


def dec(event):
    progressbar.step(-10)

def quit(event):
    window.destroy()



button = tk.Button(text="Decrease Power")
button.bind("<Button-1>", dec)
button.pack(side="top")

button = tk.Button(text="Quit")
button.bind("<Button-1>", quit)
button.pack(side="top")


current_sat = Sat(42,42)
create_console().pack(side="right")

control_frame.pack(side="left")
map_frame.pack(side="left")

# event loop
window.mainloop()