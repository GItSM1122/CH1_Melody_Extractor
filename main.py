
# main.py

import tkinter as tk
from tkinter import messagebox

from gui import MainWindow


def main():

    try:

        app = MainWindow()

        app.mainloop()

    except Exception as e:

        root = tk.Tk()
        root.withdraw()

        messagebox.showerror(
            "CH1 Melody Extractor",
            f"起動エラー\n\n{e}"
        )

        raise


if __name__ == "__main__":
    main()