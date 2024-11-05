import tkinter as tk
import tkinter.ttk as ttk

def parse(command, text_area):
    
    # TODO do some processing    
    print(f"Parsing: {command}")    

    words = command.split()
    
    match words[0]:
        case ">>>energy":
            text_area.insert("end", "\nChanging enery")
        case ">>>power":
            text_area.insert("end", "\nChanging power")
        case _:
            text_area.insert("end", "\nUnkown cmd")
    return
            

def extract(event,text_area):
    current_content = text_area.get("1.0", "end-1c")
    lines = current_content.split('\n')

    parse(lines[-1], text_area)

    text_area.insert("end", "\nDone!\n>>>")
    text_area.see("end")

    # prevent another newline
    return "break"

def create_console():

    frame = tk.Frame()
    console_label = tk.Label(master=frame, text="Enter cmd here:")
    text_area = tk.Text(master=frame, width=20, height=7, borderwidth=5)
    text_area.bind("<Return>", lambda event: extract(event, text_area))   # ki did stuffs for me :)

    text_area.insert(1.0, ">>>")

    console_label.pack()
    text_area.pack()
    return frame
