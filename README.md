# CH1 Melody Extractor

Studio Oneで書き出したCH1のMIDIから、以下の2ファイルを生成するPythonツールです。

- `Song.mid` : その時点で鳴っている最高音
- `Harmony.mid` : それ以外の音

Python 3.10以上を推奨します。

## 使い方

```bash
python3 /home/runner/work/CH1_Melody_Extractor/CH1_Melody_Extractor/ch1_melody_extractor.py /path/to/input.mid
```

デフォルトでは入力ファイルと同じフォルダに以下を出力します。

- `Song.mid`
- `Harmony.mid`

出力先を変える場合:

```bash
python3 /home/runner/work/CH1_Melody_Extractor/CH1_Melody_Extractor/ch1_melody_extractor.py /path/to/input.mid --output-dir /path/to/output
```

対象チャンネルを変える場合:

```bash
python3 /home/runner/work/CH1_Melody_Extractor/CH1_Melody_Extractor/ch1_melody_extractor.py /path/to/input.mid --channel 1
```
