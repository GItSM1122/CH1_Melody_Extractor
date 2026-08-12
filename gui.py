import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

from pathlib import Path

from engine import MelodyExtractor


class MainWindow(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title("CH1 Melody Extractor V1.0")

        self.geometry("700x520")

        self.resizable(False, False)

        self.engine = MelodyExtractor()

        self.create_widgets()

    # ----------------------------
    # GUI作成
    # ----------------------------
    def create_widgets(self):

        pad = 8

        # ------------------------
        # Input
        # ------------------------

        ttk.Label(
            self,
            text="入力MID"
        ).grid(row=0, column=0, padx=pad, pady=pad, sticky="w")

        self.input_var = tk.StringVar()

        ttk.Entry(
            self,
            width=60,
            textvariable=self.input_var
        ).grid(row=0, column=1)

        ttk.Button(
            self,
            text="参照",
            command=self.select_input
        ).grid(row=0, column=2)

        # ------------------------
        # Output
        # ------------------------

        ttk.Label(
            self,
            text="出力フォルダ"
        ).grid(row=1, column=0, padx=pad, pady=pad, sticky="w")

        self.output_var = tk.StringVar()

        ttk.Entry(
            self,
            width=60,
            textvariable=self.output_var
        ).grid(row=1, column=1)

        ttk.Button(
            self,
            text="参照",
            command=self.select_output
        ).grid(row=1, column=2)

        # ------------------------
        # Tick
        # ------------------------

        ttk.Label(
            self,
            text="和音判定Tick"
        ).grid(row=2, column=0, padx=pad, pady=pad, sticky="w")

        self.tick_var = tk.IntVar(value=10)

        ttk.Spinbox(
            self,
            from_=0,
            to=50,
            width=8,
            textvariable=self.tick_var
        ).grid(row=2, column=1, sticky="w")

        # ------------------------
        # Button
        # ------------------------

        ttk.Button(
            self,
            text="解析",
            command=self.analyze
        ).grid(row=3, column=0, pady=10)

        ttk.Button(
            self,
            text="Song + Harmony 作成",
            command=self.create_mid
        ).grid(row=3, column=1, sticky="w")

        # ------------------------
        # Log
        # ------------------------

        self.log = tk.Text(
            self,
            width=82,
            height=18
        )

        self.log.grid(
            row=4,
            column=0,
            columnspan=3,
            padx=10,
            pady=10
        )
        
            # ----------------------------
    # 入力MID選択
    # ----------------------------
    def select_input(self):

        filename = filedialog.askopenfilename(

            title="MIDI選択",

            filetypes=[
                ("MIDI", "*.mid"),
                ("All", "*.*")
            ]
        )

        if filename:

            self.input_var.set(filename)

            if self.output_var.get() == "":

                self.output_var.set(
                    str(Path(filename).parent)
                )

    # ----------------------------
    # 出力フォルダ
    # ----------------------------
    def select_output(self):

        folder = filedialog.askdirectory()

        if folder:

            self.output_var.set(folder)

    # ----------------------------
    # ログ
    # ----------------------------
    def write_log(self, text):

        self.log.insert(tk.END, text + "\n")

        self.log.see(tk.END)

    # ----------------------------
    # 解析
    # ----------------------------
    def analyze(self):

        try:

            self.engine.tick_tolerance = self.tick_var.get()

            self.engine.load(
                self.input_var.get()
            )

            self.engine.collect_events()

            self.engine.group_chords()

            result = self.engine.analyze()

            self.log.delete("1.0", tk.END)

            self.write_log("===== 解析結果 =====")
            self.write_log("")
            self.write_log(
                f"ノート数 : {result['note_count']}"
            )
            self.write_log(
                f"和音数 : {result['chord_count']}"
            )
            self.write_log(
                f"最大和音 : {result['max_polyphony']}"
            )
            self.write_log(
                f"平均和音 : {result['average_polyphony']}"
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )

    # ----------------------------
    # Song/Harmony生成
    # ----------------------------
    def create_mid(self):

        try:

            self.engine.tick_tolerance = self.tick_var.get()

            self.engine.load(
                self.input_var.get()
            )

            self.engine.collect_events()

            self.engine.group_chords()

            out = Path(
                self.output_var.get()
            )

            stem = Path(
                self.input_var.get()
            ).stem

            song_file = out / f"{stem}_Song.mid"

            harmony_file = out / f"{stem}_Harmony.mid"

            self.engine.save_song(song_file)

            self.engine.save_harmony(harmony_file)

            self.write_log("")
            self.write_log("保存完了")
            self.write_log(song_file.name)
            self.write_log(harmony_file.name)

            messagebox.showinfo(
                "完了",
                "Song.mid と Harmony.mid を保存しました。"
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )