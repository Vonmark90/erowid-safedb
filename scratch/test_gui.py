import tkinter
print("Creating root...")
try:
    root = tkinter.Tk()
    print("Root created successfully!")
    root.withdraw()
    print("Root withdrawn successfully!")
    root.destroy()
    print("Root destroyed cleanly!")
except Exception as e:
    print("Error:", e)
